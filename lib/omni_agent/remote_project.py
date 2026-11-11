"""Projects on a remote host: send the files, let the agent work there, fetch the changes back.

`omni-agent run --host mini --project` copies the project to the host with rsync (only files git would track
plus new ones, never `.git`, never secrets), runs the agent on that copy and leaves the result there.
`omni-agent apply --host mini` shows what changed and, with --yes, writes it into your project.
Nothing flows back without you asking, and nothing the host sends can leave the project folder.

Needs on both sides: ssh, rsync, python3 (3.9+). Tailscale is nothing special: any address ssh reaches works.
"""
from __future__ import annotations

import difflib
import fnmatch
import hashlib
import json
import os
import shlex
import shutil
import subprocess
import sys
import time
from pathlib import Path

from .config import ConfigError, home

REMOTE_BASE = ".omni-agent/remote"  # relative to the host's home
MAX_FILES = 50_000
MAX_BYTES = 500 * 1024 * 1024
SKIP_DIRS = {".git", "node_modules", ".next", ".venv", "venv", "__pycache__", ".mypy_cache", ".pytest_cache", "dist", "build", ".turbo", ".cache"}
# Secrets stay home unless you say --with-env (env files) — keys and certificates never travel.
ENV_PATTERNS = (".env", ".env.*", "*.env")
ENV_SAFE = (".env.example", ".env.sample", ".env.template", ".env.dist")
SECRET_PATTERNS = ("*.pem", "*.key", "*.p12", "*.pfx", "id_rsa*", "id_ed25519*", "id_ecdsa*", ".npmrc", ".netrc", ".pgpass", "*.keystore")

# Runs on the host (python3 from stdin of `python3 -c`). No omni-agent needed there.
_HASH_SCRIPT = r"""
import hashlib, json, os, sys
root = sys.argv[1]
out = {}
for d, dirs, names in os.walk(root):
    for n in names:
        p = os.path.join(d, n)
        if os.path.islink(p) or not os.path.isfile(p):
            continue
        h = hashlib.sha256()
        with open(p, "rb") as f:
            for chunk in iter(lambda: f.read(1 << 20), b""):
                h.update(chunk)
        out[os.path.relpath(p, root).replace(os.sep, "/")] = h.hexdigest()
print(json.dumps(out))
"""
_PRUNE_SCRIPT = r"""
import os, sys
root = os.path.abspath(sys.argv[1])
keep = set(x for x in sys.stdin.buffer.read().decode("utf-8").split("\n") if x)
for d, dirs, names in os.walk(root, topdown=False):
    for n in names:
        p = os.path.join(d, n)
        if os.path.relpath(p, root).replace(os.sep, "/") not in keep:
            os.remove(p)
    if d != root and not os.listdir(d):
        os.rmdir(d)
"""


# ---------- which files travel ----------

def _is_secret(rel: str, with_env: bool) -> bool:
    name = rel.rsplit("/", 1)[-1]
    if not with_env and name not in ENV_SAFE and any(fnmatch.fnmatch(name, p) for p in ENV_PATTERNS):
        return True
    return any(fnmatch.fnmatch(name, p) for p in SECRET_PATTERNS)


def local_files(root: Path, with_env: bool = False) -> tuple:
    """(files, skipped_secrets): relative paths with '/', regular files only."""
    found = []
    try:
        res = subprocess.run(["git", "ls-files", "-z", "--cached", "--others", "--exclude-standard"], cwd=root, capture_output=True, timeout=60)
        if res.returncode == 0:
            found = [x for x in res.stdout.decode("utf-8", "surrogateescape").split("\0") if x]
    except (OSError, subprocess.SubprocessError):
        pass
    if not found:
        for d, dirs, names in os.walk(root):
            dirs[:] = [x for x in dirs if x not in SKIP_DIRS]
            for n in names:
                found.append(os.path.relpath(os.path.join(d, n), root).replace(os.sep, "/"))
    files, secrets = [], []
    for rel in sorted(set(found)):
        p = root / rel
        if "\n" in rel or rel.startswith("/") or ".." in rel.split("/") or ".git" in rel.split("/"):
            continue
        if p.is_symlink() or not p.is_file():
            continue
        if _is_secret(rel, with_env):
            secrets.append(rel)
            continue
        files.append(rel)
    if len(files) > MAX_FILES:
        raise ConfigError(f"{len(files)} files are too many to send (limit {MAX_FILES}). Pick a smaller folder with --project DIR.")
    total = sum((root / f).stat().st_size for f in files)
    if total > MAX_BYTES:
        raise ConfigError(f"The project is {total // (1024 * 1024)} MB, the limit is {MAX_BYTES // (1024 * 1024)} MB. Pick a smaller folder with --project DIR.")
    return files, secrets


def sha256_of(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


# ---------- talking to the host ----------

def _ssh_command_text(entry: dict) -> str:
    return "ssh -o BatchMode=yes -o ConnectTimeout=10 -o ServerAliveInterval=30"


def _need_rsync() -> str:
    exe = shutil.which("rsync")
    if not exe:
        raise ConfigError("rsync is not installed (command 'rsync' not on PATH). It is needed to send project files to a host.")
    return exe


def _remote_run(entry: dict, remote: str, input_bytes: bytes | None = None, timeout: int = 300):
    from .hosts import ssh_argv
    res = subprocess.run(ssh_argv(entry, remote), input=input_bytes, capture_output=True, timeout=timeout)
    if res.returncode == 255:
        raise ConfigError(f"ssh to {entry['ssh']} failed: " + (res.stderr.decode("utf-8", "replace").strip().splitlines() or ["no message"])[-1])
    return res


def _rsync(entry: dict, source: str, dest: str, file_list: list, timeout: int = 1800) -> None:
    argv = [_need_rsync(), "-a", "--files-from=-", "-e", _ssh_command_text(entry), source, dest]
    res = subprocess.run(argv, input=("\n".join(file_list) + "\n").encode("utf-8"), capture_output=True, timeout=timeout)
    if res.returncode != 0:
        text = res.stderr.decode("utf-8", "replace").strip().splitlines()
        hint = " Is rsync installed on the host?" if any("rsync" in z and ("not found" in z or "command" in z) for z in text) else ""
        raise ConfigError("rsync failed: " + (text[-1] if text else f"exit code {res.returncode}") + hint)


def remote_dir_for(kind: str, root: Path) -> str:
    key = hashlib.sha1(str(root).encode("utf-8")).hexdigest()[:8]
    slug = "".join(c if c.isalnum() or c in "-_" else "-" for c in root.name)[:40] or "project"
    return f"{REMOTE_BASE}/{kind}/{slug}-{key}"


def _state_file(host: str, root: Path) -> Path:
    key = hashlib.sha1(str(root).encode("utf-8")).hexdigest()[:10]
    return home() / "remote-sync" / f"{host}-{key}.json"


def _load_state(host: str, root: Path) -> dict | None:
    try:
        return json.loads(_state_file(host, root).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def _save_state(host: str, root: Path, state: dict) -> None:
    f = _state_file(host, root)
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(json.dumps(state, indent=1) + "\n", encoding="utf-8")


def sync(host: str, root: Path, kind: str = "projects", with_env: bool = False) -> str:
    """Copies the project (or a folder) to the host and returns the folder there (relative to its home).
    Files that are gone here are removed there, so the copy is exactly your current state."""
    from .hosts import lookup
    entry = lookup(host)
    root = root.resolve()
    files, secrets = local_files(root, with_env)
    if not files:
        raise ConfigError(f"No files to send in {root}")
    remote = remote_dir_for(kind, root)
    res = _remote_run(entry, f"mkdir -p {shlex.quote(remote)}")
    if res.returncode != 0:
        raise ConfigError("Could not create the folder on the host: " + res.stderr.decode("utf-8", "replace").strip())
    print(f"Sending {len(files)} files to {host}:{remote} ...", flush=True)
    _rsync(entry, str(root) + "/", f"{entry['ssh']}:{remote}/", files)
    res = _remote_run(entry, "python3 -c " + shlex.quote(_PRUNE_SCRIPT) + " " + shlex.quote(remote), ("\n".join(files) + "\n").encode("utf-8"))
    if res.returncode != 0:
        raise ConfigError("Cleaning the copy on the host failed (python3 there?): " + res.stderr.decode("utf-8", "replace").strip()[-300:])
    if secrets:
        shown = ", ".join(secrets[:4]) + (" ..." if len(secrets) > 4 else "")
        print(f"Kept at home ({len(secrets)}): {shown}  (env files travel only with --with-env)", flush=True)
    if kind == "projects":
        _save_state(host, root, {
            "host": host, "project": str(root), "remote_dir": remote, "synced_at": int(time.time()),
            "files": {f: sha256_of(root / f) for f in files},
        })
    return remote


# ---------- rewrite the arguments for the host ----------

def rewrite_run_argv(host: str, argv: list, args) -> list:
    """Sends project/files to the host and returns the arguments for the remote command."""
    out = []
    i = 0
    project_given = getattr(args, "project", None) is not None
    files_given = bool(getattr(args, "files", None))
    while i < len(argv):
        a = argv[i]
        if a == "--project":
            i += 2 if getattr(args, "project", None) else 1
            continue
        if a.startswith("--project="):
            i += 1
            continue
        if files_given and a == "--files":
            i += 2
            continue
        if files_given and a.startswith("--files="):
            i += 1
            continue
        if a == "--with-env":
            i += 1
            continue
        out.append(a)
        i += 1

    if getattr(args, "resume", None) is not None:
        return out  # the run on the host remembers its folder
    if project_given:
        root = Path(args.project or os.getcwd()).expanduser()
        if not root.is_dir():
            raise ConfigError(f"Project folder not found: {root}")
        remote = sync(host, root, "projects", bool(getattr(args, "with_env", False)))
        out += ["--project", remote]
    elif files_given:
        folder = Path(args.files).expanduser()
        if not folder.is_dir():
            raise ConfigError(f"Files folder not found: {folder}")
        out += ["--files", sync(host, folder, "files", False)]
    return out


# ---------- fetch the changes back ----------

def _remote_manifest(entry: dict, remote: str) -> dict:
    res = _remote_run(entry, "python3 -c " + shlex.quote(_HASH_SCRIPT) + " " + shlex.quote(remote))
    if res.returncode != 0:
        raise ConfigError("Could not read the copy on the host: " + res.stderr.decode("utf-8", "replace").strip()[-300:])
    try:
        doc = json.loads(res.stdout.decode("utf-8"))
    except ValueError as exc:
        raise ConfigError("Unexpected answer from the host while listing the copy") from exc
    clean = {}
    for rel, digest in doc.items():
        parts = rel.split("/")
        if rel.startswith("/") or "\0" in rel or "\n" in rel or ".." in parts or "" in parts or ".git" in parts:
            print(f"Ignored suspicious path from the host: {rel!r}", file=sys.stderr)
            continue
        clean[rel] = digest
    return clean


def _find_state(host: str | None, root: Path) -> dict:
    if host:
        state = _load_state(host, root)
        if not state:
            raise ConfigError(f"Nothing was sent from {root} to '{host}' yet. Start with: omni-agent run --host {host} --project ...")
        return state
    found = []
    d = home() / "remote-sync"
    if d.is_dir():
        for f in sorted(d.glob("*.json")):
            try:
                s = json.loads(f.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                continue
            if s.get("project") == str(root):
                found.append(s)
    if not found:
        raise ConfigError(f"Nothing was sent from {root} to a host yet. Start with: omni-agent run --host NAME --project ...")
    if len(found) > 1:
        raise ConfigError("Several hosts hold a copy of this project: " + ", ".join(s["host"] for s in found) + ". Say which: --host NAME")
    return found[0]


def _text(path: Path) -> list | None:
    try:
        data = path.read_bytes()
    except OSError:
        return []
    if b"\0" in data[:8192]:
        return None
    return data.decode("utf-8", "replace").splitlines(keepends=True)


def apply_changes(host: str | None, project: str | None, confirm: bool, force: bool) -> int:
    from .hosts import lookup
    root = Path(project or os.getcwd()).expanduser().resolve()
    state = _find_state(host, root)
    host = state["host"]
    entry = lookup(host)
    remote = state["remote_dir"]
    base = state["files"]
    now = _remote_manifest(entry, remote)

    added = sorted(f for f in now if f not in base)
    modified = sorted(f for f in now if f in base and now[f] != base[f])
    deleted = sorted(f for f in base if f not in now)
    if not (added or modified or deleted):
        print(f"No changes on {host} compared with what was sent.")
        return 0

    staging = home() / "remote-sync" / f"{host}-{hashlib.sha1(str(root).encode()).hexdigest()[:10]}-staging"
    shutil.rmtree(staging, ignore_errors=True)
    staging.mkdir(parents=True)
    fetch = added + modified
    if fetch:
        _rsync(entry, f"{entry['ssh']}:{remote}/", str(staging) + "/", fetch)

    plan, skipped = [], []
    for rel in added + modified + deleted:
        target = root / rel
        if not (target.resolve().parent == root or root in target.resolve().parents):
            skipped.append((rel, "outside the project"))
            continue
        local_now = sha256_of(target) if target.is_file() else None
        if rel in added:
            kind = "added"
            clash = local_now is not None and local_now != now[rel]
        elif rel in modified:
            kind = "changed"
            clash = local_now != base[rel]
        else:
            kind = "deleted"
            clash = local_now is not None and local_now != base[rel]
        if clash and not force:
            skipped.append((rel, "changed here since it was sent"))
            continue
        plan.append((kind, rel))

    print(f"Changes on {host} ({remote}): {len(added)} added, {len(modified)} changed, {len(deleted)} deleted")
    shown = 0
    for kind, rel in plan:
        print(f"  {kind:<8} {rel}")
        if kind in ("changed", "added") and shown < 400:
            old = _text(root / rel) if kind == "changed" else []
            new = _text(staging / rel)
            if old is None or new is None:
                print("           (binary file)")
                continue
            for line in difflib.unified_diff(old, new, f"a/{rel}", f"b/{rel}", n=2):
                if shown >= 400:
                    print("           ... diff cut off")
                    break
                print("           " + line.rstrip("\n"))
                shown += 1
    for rel, why in skipped:
        print(f"  SKIPPED  {rel}  ({why}; --force overwrites)")

    if not confirm:
        print(f"\nNothing written. To apply to {root}: omni-agent apply --host {host} --yes")
        return 0

    for kind, rel in plan:
        target = root / rel
        if kind == "deleted":
            if target.is_file():
                target.unlink()
            base.pop(rel, None)
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(staging / rel, target)
            base[rel] = now[rel]
    state["files"] = base
    _save_state(host, root, state)
    shutil.rmtree(staging, ignore_errors=True)
    print(f"\nApplied {len(plan)} changes to {root}." + (f" {len(skipped)} skipped." if skipped else ""))
    return 0 if not skipped else 1
