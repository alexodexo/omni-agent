"""Code review by another model: collect the git diff, check it, hand it to a run as files."""
from __future__ import annotations

import argparse
import re
import subprocess
import tempfile
from pathlib import Path

from .config import ConfigError

MAX_CHARS = 400_000
EXCLUDED = [":(exclude)*.lock", ":(exclude)package-lock.json", ":(exclude)pnpm-lock.yaml", ":(exclude)*.min.js", ":(exclude)*.map"]
# Rough warning threshold, not protection: finds the most common key shapes in the diff
SECRET_PATTERNS = re.compile(
    r"(sk-ant-[A-Za-z0-9_-]{20,}|sk-[A-Za-z0-9]{32,}|AKIA[0-9A-Z]{16}|-----BEGIN [A-Z ]*PRIVATE KEY-----"
    r"|(?i:api[_-]?key|secret|token|passwor[dt])\s*[:=]\s*['\"]?[A-Za-z0-9_\-./+]{24,})"
)

REVIEW_TASK = """Review the code changes in the file changes.patch (git diff). The list of changed files is in changed_files.txt.

<goal>
{scope}
</goal>

<finding_bar>
Report only material findings: bugs, data loss, security holes, wrong permissions, misbehaviour under load or on partial failure. No style points, no naming points, no cleanup wishes, no guesses without a hint in the diff.
Each finding answers: What can go wrong? Why is this spot vulnerable? What impact is likely? Which concrete change lowers the risk?
</finding_bar>

<limits_of_view>
You only see the diff, not the rest of the code. Mark anything that depends on invisible context explicitly as conjecture and keep the confidence low accordingly. Do not invent files, lines, flows or incidents. Do not change the code and do not write finished patches; describe fixes in words.
</limits_of_view>

<report_structure>
Write report.md in exactly this structure, in the language of the task:

# Review: <short title>

## Verdict
`approve` or `needs-work`, plus one sentence like a terse ship/no-ship verdict, not a neutral retelling.

## Findings
Ordered by severity. For each finding a heading of the form `### [critical|high|medium|low] Title`, followed by:
- Location: `file:line_from-line_to`
- Confidence: a number from 0 to 1 (honest, low for conjecture)
- Problem and impact: one to three sentences
- Recommendation: concrete

If there is nothing solid: `No findings.` and the residual risk in one sentence. One strong finding beats several weak ones.

## Next steps
At most three items, or `none`.

## Assumptions and open points
</report_structure>
"""

ADVERSARIAL = """
<stance>
Review adversarially. Your job is to shake confidence in the change, not to confirm it. Start from skepticism: assume the change can fail in subtle, costly or visible ways until the diff shows otherwise. Give no credit for good intent, partial solutions or later follow-up work. If something only works in the good case, that is a real weakness.
</stance>

<attack-surface>
Weigh what is costly, dangerous or hard to notice:
- Permissions, tenant separation, trust boundaries
- Data loss, corruption, duplicates, irreversible states
- Rollback, retries, partial failures, idempotency
- Race conditions, ordering assumptions, stale state
- Empty state, null, timeouts, failed dependencies
- Version differences, schema and migration risks, compatibility breaks
- Gaps in observability that hide failures
</attack-surface>

<approach>
Actively try to refute the change: violated invariants, missing guards, unhandled error paths, assumptions that no longer hold under load. Follow how bad input, retries, concurrent actions or half-finished flows travel through the code. Name the strongest two to three objections. If the change looks safe, say so plainly.
</approach>
"""


def _git(args: list, cwd: str | None = None) -> str:
    try:
        res = subprocess.run(["git", *args], capture_output=True, text=True, cwd=cwd, timeout=60)
    except (OSError, subprocess.SubprocessError) as exc:
        raise ConfigError(f"git cannot be run: {exc}") from exc
    if res.returncode != 0:
        raise ConfigError(f"git {' '.join(args[:2])} failed: {res.stderr.strip() or res.stdout.strip()}")
    return res.stdout


def main_branch(root_path: str) -> str | None:
    """main or master (origin preferred), if it exists and we are not on it ourselves."""
    current = _git(["rev-parse", "--abbrev-ref", "HEAD"], root_path).strip()
    for candidate in ("origin/main", "origin/master", "main", "master"):
        if candidate.split("/")[-1] == current:
            continue
        try:
            _git(["rev-parse", "--verify", "--quiet", candidate], root_path)
            return candidate
        except ConfigError:
            continue
    return None


def collect(base: str | None, worktree_only: bool = False) -> dict:
    """Diff and file list. Without base: all changes against HEAD (staged and unstaged);
    if the working tree is clean, the branch against the main branch."""
    root_path = _git(["rev-parse", "--show-toplevel"]).strip()
    if not base and not worktree_only and not _git(["status", "--porcelain", "--untracked-files=no"], root_path).strip():
        base = main_branch(root_path)
    if base:
        diff = _git(["diff", "--no-color", "-U8", f"{base}...HEAD", "--", ".", *EXCLUDED], root_path)
        names = _git(["diff", "--name-status", f"{base}...HEAD", "--", ".", *EXCLUDED], root_path)
        scope = f"branch against {base}"
    else:
        diff = _git(["diff", "--no-color", "-U8", "HEAD", "--", ".", *EXCLUDED], root_path)
        names = _git(["diff", "--name-status", "HEAD", "--", ".", *EXCLUDED], root_path)
        scope = "current changes against HEAD"
    new = [z for z in _git(["ls-files", "--others", "--exclude-standard"], root_path).splitlines() if z]
    return {"root_path": root_path, "diff": diff, "names": names, "scope": scope, "new": new}


def verify(doc: dict, force: bool) -> list:
    """Notes for the output; raises on an empty, too large or suspicious diff."""
    if not doc["diff"].strip():
        note = f" New, untracked files ({len(doc['new'])}) are missing from the diff: run `git add -N` first." if doc["new"] else ""
        raise ConfigError(f"No changes to review ({doc['scope']}).{note}")
    if len(doc["diff"]) > MAX_CHARS:
        raise ConfigError(
            f"The diff is too large ({len(doc['diff']) // 1000} KB, allowed {MAX_CHARS // 1000} KB). "
            "Pick a smaller range (--base with a closer state) or review in parts."
        )
    hints = []
    if doc["new"]:
        hints.append(f"{len(doc['new'])} new files are not in the git index and will NOT be reviewed (git add -N).")
    suspects = [z for z in doc["diff"].splitlines() if z.startswith("+") and SECRET_PATTERNS.search(z)]
    env_files = [z.split()[-1] for z in doc["names"].splitlines() if Path(z.split()[-1]).name.startswith(".env")]
    if (suspects or env_files) and not force:
        raise ConfigError(
            f"The diff contains possible secrets ({len(suspects)} lines"
            + (f", files {', '.join(env_files)}" if env_files else "")
            + "). Nothing was sent. Remove them or send deliberately with --force."
        )
    return hints


def run_review(args) -> int:
    from .engine import execute
    doc = collect(args.base)
    hints = verify(doc, args.force)
    lines = doc["diff"].count("\n")
    file_list = len([z for z in doc["names"].splitlines() if z.strip()])
    print(f"Review: {doc['scope']}, {file_list} files, {lines} diff lines, {len(doc['diff']) // 1000} KB")
    for h in hints:
        print(f"Note: {h}")
    if args.preview:
        print("Preview: nothing sent. Files:\n" + doc["names"])
        return 0

    task = REVIEW_TASK.format(scope=f"Review target: {doc['scope']}.") + (ADVERSARIAL if args.adversarial else "")
    if args.focus:
        task += f"\nFocus requested by the user: {' '.join(args.focus)}\n"
    with tempfile.TemporaryDirectory() as files:
        (Path(files) / "changes.patch").write_text(doc["diff"], encoding="utf-8")
        (Path(files) / "changed_files.txt").write_text(doc["names"], encoding="utf-8")
        run_args = argparse.Namespace(
            task=None, text=task, provider=args.provider, model=args.model, runner=args.runner,
            tool_list="read,write", max_turns=args.max_turns, time_limit=args.time_limit, folder=None,
            files=files, via_litellm=False, resume=None, effort=args.effort,
            project=None, writable=False, kind="review",
        )
        return execute(run_args)
