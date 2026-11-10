"""Code-Review durch ein anderes Modell: Git-Diff sammeln, prüfen, als Material in einen Lauf geben."""
from __future__ import annotations

import argparse
import re
import subprocess
import tempfile
from pathlib import Path

from .konfig import KonfigFehler

MAX_ZEICHEN = 400_000
AUSGENOMMEN = [":(exclude)*.lock", ":(exclude)package-lock.json", ":(exclude)pnpm-lock.yaml", ":(exclude)*.min.js", ":(exclude)*.map"]
# Grobe Warnschwelle, kein Schutz: findet die häufigsten Schlüsselformen im Diff
GEHEIMNIS_MUSTER = re.compile(
    r"(sk-ant-[A-Za-z0-9_-]{20,}|sk-[A-Za-z0-9]{32,}|AKIA[0-9A-Z]{16}|-----BEGIN [A-Z ]*PRIVATE KEY-----"
    r"|(?i:api[_-]?key|secret|token|passwor[dt])\s*[:=]\s*['\"]?[A-Za-z0-9_\-./+]{24,})"
)

AUFTRAG = """Prüfe die Codeänderungen in der Datei aenderungen.patch (Git-Diff). Die Liste der geänderten Dateien steht in geaenderte_dateien.txt.

<ziel>
{ziel}
</ziel>

<befundlatte>
Melde nur wesentliche Befunde: Fehler, Datenverlust, Sicherheitslücken, falsche Rechte, Fehlverhalten unter Last oder bei Teilfehlern. Keine Stilfragen, keine Namensfragen, keine Aufräumwünsche, keine Vermutungen ohne Anhaltspunkt im Diff.
Jeder Befund beantwortet: Was kann schiefgehen? Warum ist diese Stelle anfällig? Welche Wirkung ist wahrscheinlich? Welche konkrete Änderung senkt das Risiko?
</befundlatte>

<grenzen_der_sicht>
Du siehst nur den Diff, nicht den übrigen Code. Was vom unsichtbaren Kontext abhängt, kennzeichnest du ausdrücklich als Vermutung und hältst die Sicherheit entsprechend niedrig. Erfinde keine Dateien, Zeilen, Abläufe oder Vorfälle. Ändere nichts am Code und schreibe keine fertigen Patches; beschreibe Korrekturen in Worten.
</grenzen_der_sicht>

<aufbau_bericht>
Schreibe bericht.md genau in dieser Gliederung:

## Urteil
`freigeben` oder `nacharbeiten`, dazu ein Satz wie ein knappes Ship/No-Ship-Urteil, keine neutrale Nacherzählung.

## Befunde
Nach Schwere geordnet. Je Befund eine Überschrift der Form `### [kritisch|hoch|mittel|niedrig] Titel`, darunter:
- Stelle: `datei:zeile_von-zeile_bis`
- Sicherheit: Zahl von 0 bis 1 (ehrlich, bei Vermutung niedrig)
- Problem und Wirkung: ein bis drei Sätze
- Empfehlung: konkret

Gibt es nichts Belastbares: `Keine Befunde.` und das Restrisiko in einem Satz. Lieber ein starker Befund als mehrere schwache.

## Nächste Schritte
Höchstens drei Punkte, oder `keine`.
</aufbau_bericht>
"""

ADVERSARIAL = """
<haltung>
Prüfe gegnerisch. Deine Aufgabe ist, das Vertrauen in die Änderung zu erschüttern, nicht sie zu bestätigen. Geh von Skepsis aus: Nimm an, die Änderung kann auf subtile, teure oder sichtbare Weise scheitern, bis der Diff etwas anderes belegt. Gib keinen Kredit für gute Absicht, Teillösungen oder spätere Nacharbeit. Funktioniert etwas nur im Gutfall, ist das eine echte Schwäche.
</haltung>

<angriffsflaeche>
Gewichte, was teuer, gefährlich oder schwer zu bemerken ist:
- Rechte, Mandantentrennung, Vertrauensgrenzen
- Datenverlust, Verfälschung, Doppelungen, nicht umkehrbare Zustände
- Rückgängigmachen, Wiederholungen, Teilausfälle, Idempotenz
- Wettlaufsituationen, Reihenfolgeannahmen, veralteter Zustand
- Leerzustand, Null, Zeitüberschreitung, ausgefallene Abhängigkeiten
- Versionsunterschiede, Schema- und Migrationsrisiken, Kompatibilitätsbrüche
- Lücken in der Beobachtbarkeit, die Fehler verstecken
</angriffsflaeche>

<vorgehen>
Versuche aktiv, die Änderung zu widerlegen: verletzte Invarianten, fehlende Wächter, unbehandelte Fehlerpfade, Annahmen, die unter Last nicht mehr gelten. Verfolge, wie schlechte Eingaben, Wiederholungen, gleichzeitige Aktionen oder halb fertige Abläufe durch den Code wandern. Nenne die stärksten zwei bis drei Einwände. Wirkt die Änderung sicher, sage das offen.
</vorgehen>
"""


def _git(args: list, cwd: str | None = None) -> str:
    try:
        erg = subprocess.run(["git", *args], capture_output=True, text=True, cwd=cwd, timeout=60)
    except (OSError, subprocess.SubprocessError) as fehler:
        raise KonfigFehler(f"git nicht ausführbar: {fehler}") from fehler
    if erg.returncode != 0:
        raise KonfigFehler(f"git {' '.join(args[:2])} fehlgeschlagen: {erg.stderr.strip() or erg.stdout.strip()}")
    return erg.stdout


def hauptzweig(wurzel: str) -> str | None:
    """main oder master (origin bevorzugt), falls es ihn gibt und wir nicht selbst darauf stehen."""
    aktuell = _git(["rev-parse", "--abbrev-ref", "HEAD"], wurzel).strip()
    for kandidat in ("origin/main", "origin/master", "main", "master"):
        if kandidat.split("/")[-1] == aktuell:
            continue
        try:
            _git(["rev-parse", "--verify", "--quiet", kandidat], wurzel)
            return kandidat
        except KonfigFehler:
            continue
    return None


def sammle(base: str | None, nur_arbeitsbaum: bool = False) -> dict:
    """Diff und Dateiliste. Ohne base: alle Änderungen gegen HEAD (gestaged und ungestaged);
    ist der Arbeitsbaum sauber, der Branch gegen den Hauptzweig."""
    wurzel = _git(["rev-parse", "--show-toplevel"]).strip()
    if not base and not nur_arbeitsbaum and not _git(["status", "--porcelain", "--untracked-files=no"], wurzel).strip():
        base = hauptzweig(wurzel)
    if base:
        diff = _git(["diff", "--no-color", "-U8", f"{base}...HEAD", "--", ".", *AUSGENOMMEN], wurzel)
        namen = _git(["diff", "--name-status", f"{base}...HEAD", "--", ".", *AUSGENOMMEN], wurzel)
        ziel = f"Branch gegen {base}"
    else:
        diff = _git(["diff", "--no-color", "-U8", "HEAD", "--", ".", *AUSGENOMMEN], wurzel)
        namen = _git(["diff", "--name-status", "HEAD", "--", ".", *AUSGENOMMEN], wurzel)
        ziel = "aktuelle Änderungen gegen HEAD"
    neu = [z for z in _git(["ls-files", "--others", "--exclude-standard"], wurzel).splitlines() if z]
    return {"wurzel": wurzel, "diff": diff, "namen": namen, "ziel": ziel, "neu": neu}


def pruefe(daten: dict, trotzdem: bool) -> list:
    """Hinweise für die Ausgabe; wirft bei leerem, zu großem oder verdächtigem Diff."""
    if not daten["diff"].strip():
        hinweis = f" Neue, nicht hinzugefügte Dateien ({len(daten['neu'])}) fehlen im Diff: erst `git add -N`." if daten["neu"] else ""
        raise KonfigFehler(f"Keine Änderungen zu prüfen ({daten['ziel']}).{hinweis}")
    if len(daten["diff"]) > MAX_ZEICHEN:
        raise KonfigFehler(
            f"Der Diff ist zu groß ({len(daten['diff']) // 1000} KB, erlaubt {MAX_ZEICHEN // 1000} KB). "
            "Einen kleineren Bereich wählen (--base mit näherem Stand) oder in Teilen prüfen."
        )
    hinweise = []
    if daten["neu"]:
        hinweise.append(f"{len(daten['neu'])} neue Dateien sind nicht im Git-Index und werden NICHT mitgeprüft (git add -N).")
    verdacht = [z for z in daten["diff"].splitlines() if z.startswith("+") and GEHEIMNIS_MUSTER.search(z)]
    env_dateien = [z.split()[-1] for z in daten["namen"].splitlines() if Path(z.split()[-1]).name.startswith(".env")]
    if (verdacht or env_dateien) and not trotzdem:
        raise KonfigFehler(
            f"Der Diff enthält mögliche Geheimnisse ({len(verdacht)} Zeilen"
            + (f", Dateien {', '.join(env_dateien)}" if env_dateien else "")
            + "). Nichts wurde gesendet. Entfernen oder mit --trotzdem bewusst senden."
        )
    return hinweise


def fuehre_review_aus(args) -> int:
    from .lauf import fuehre_aus
    daten = sammle(args.base)
    hinweise = pruefe(daten, args.trotzdem)
    zeilen = daten["diff"].count("\n")
    dateien = len([z for z in daten["namen"].splitlines() if z.strip()])
    print(f"Review: {daten['ziel']}, {dateien} Dateien, {zeilen} Diff-Zeilen, {len(daten['diff']) // 1000} KB")
    for h in hinweise:
        print(f"Hinweis: {h}")
    if args.vorschau:
        print("Vorschau: nichts gesendet. Dateien:\n" + daten["namen"])
        return 0

    auftrag = AUFTRAG.format(ziel=f"Prüfziel: {daten['ziel']}.") + (ADVERSARIAL if args.adversarial else "")
    if args.fokus:
        auftrag += f"\nSchwerpunkt der Nutzerin: {' '.join(args.fokus)}\n"
    with tempfile.TemporaryDirectory() as material:
        (Path(material) / "aenderungen.patch").write_text(daten["diff"], encoding="utf-8")
        (Path(material) / "geaenderte_dateien.txt").write_text(daten["namen"], encoding="utf-8")
        lauf_args = argparse.Namespace(
            auftrag=None, text=auftrag, anbieter=args.anbieter, modell=args.modell, runner=args.runner,
            werkzeuge="lesen,schreiben", max_runden=args.max_runden, zeit=args.zeit, ordner=None,
            material=material, ueber_litellm=False, fortsetzen=None, aufwand=args.aufwand,
            projekt=None, schreibend=False, art="review",
        )
        return fuehre_aus(lauf_args)
