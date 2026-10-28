"""Vertrag zwischen Kern und Runner (Agent-CLI)."""
import os
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

# Neutrale Werkzeuge. Jeder Adapter übersetzt sie in seine eigene Sprache.
WERKZEUGE = ("lesen", "schreiben", "web_suche", "web_laden", "shell")
STANDARD_WERKZEUGE = ("lesen", "schreiben", "web_suche", "web_laden")

# Variablen, die kein Geheimnis sind und hinter Firmen-Proxys gebraucht werden.
DURCHREICHEN = (
    "HTTP_PROXY", "HTTPS_PROXY", "NO_PROXY", "ALL_PROXY",
    "http_proxy", "https_proxy", "no_proxy", "all_proxy",
    "SSL_CERT_FILE", "SSL_CERT_DIR", "NODE_EXTRA_CA_CERTS", "REQUESTS_CA_BUNDLE",
    "LANG", "LC_ALL",
)


@dataclass
class LaufKontext:
    prompt: str                      # Rahmen + Auftrag
    ordner: Path                     # leerer Arbeitsordner
    anbieter: object                 # anbieter.Anbieter
    modell: str
    base_url: str | None             # wirksame Adresse (bei LiteLLM die lokale)
    protokoll: str                   # wirksames Protokoll
    schluessel: dict                 # nur die Schlüssel, die dieser Lauf braucht: Name -> Wert
    werkzeuge: tuple
    max_runden: int
    extra: dict = field(default_factory=dict)


@dataclass
class Befehl:
    argv: list
    env: dict
    stdin_text: str | None = None


def grundumgebung() -> dict:
    """Das Nötigste. Nichts von der Orchestrator-Sitzung (Anmeldung, Base-URL) rutscht durch."""
    env = {
        "HOME": str(Path.home()),
        "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
        "TERM": "dumb",
    }
    for name in DURCHREICHEN:
        if os.environ.get(name):
            env[name] = os.environ[name]
    return env


class Runner:
    name = ""
    binary = ""
    protokolle: tuple = ()
    kann: frozenset = frozenset()            # welche neutralen Werkzeuge er steuern kann
    nicht_verbietbar: frozenset = frozenset()  # Werkzeuge, die er immer hat
    experimentell = False
    hinweis = ""

    def pfad(self) -> str | None:
        return shutil.which(self.binary)

    def version(self) -> str | None:
        pfad = self.pfad()
        if not pfad:
            return None
        try:
            erg = subprocess.run([pfad, "--version"], capture_output=True, text=True, timeout=15)
        except (OSError, subprocess.SubprocessError):
            return "unbekannt"
        text = (erg.stdout or erg.stderr).strip().splitlines()
        return text[0] if text else "unbekannt"

    def spricht(self, protokoll: str) -> bool:
        return protokoll in self.protokolle

    def baue(self, ctx: LaufKontext) -> Befehl:  # pragma: no cover - Schnittstelle
        raise NotImplementedError

    def fortschritt(self, zeile: str, zustand: dict) -> list:
        """Übersetzt eine Ausgabezeile in lesbare Fortschrittszeilen. Zählt zustand['runden']."""
        return [zeile.rstrip()] if zeile.strip() else []


def kurz(text, n: int = 110) -> str:
    text = " ".join(str(text).split())
    return text if len(text) <= n else text[: n - 1] + "…"
