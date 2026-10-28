"""Pfade, Schlüsselquellen und gemeinsame Fehlerklassen. Nur Standardbibliothek."""
import os
import socket
from pathlib import Path
from urllib.parse import urlparse

# lib/omni-agent/konfig.py -> Repo- bzw. Plugin-Ordner
WURZEL = Path(__file__).resolve().parents[2]

EXIT_OK = 0
EXIT_LAUF = 1
EXIT_KONFIG = 2
EXIT_ENDPUNKT = 3
EXIT_ZEIT = 124


class KonfigFehler(Exception):
    """Etwas fehlt oder ist falsch eingestellt (Exit 2)."""

    exit_code = EXIT_KONFIG


class EndpunktFehler(KonfigFehler):
    """Der Anbieter ist nicht erreichbar (Exit 3)."""

    exit_code = EXIT_ENDPUNKT


def home() -> Path:
    return Path(os.environ.get("OMNI_AGENT_HOME") or Path.home() / ".omni-agent")


def env_datei() -> Path:
    return home() / "env"


def laeufe_ordner() -> Path:
    return home() / "laeufe"


def _entquote(wert: str) -> str:
    wert = wert.strip()
    if len(wert) >= 2 and wert[0] == wert[-1] and wert[0] in "\"'":
        return wert[1:-1]
    return wert


def lese_schluesseldatei() -> dict:
    """Liest NAME=wert aus ~/.omni-agent/env. Die Datei wird nie als Shell-Code ausgeführt.

    Verweigert die Datei, wenn Gruppe oder andere sie lesen können.
    """
    pfad = env_datei()
    if not pfad.exists():
        return {}
    if pfad.stat().st_mode & 0o077:
        raise KonfigFehler(f"Rechte von {pfad} zu offen. Bitte: chmod 600 {pfad}")
    werte = {}
    for zeile in pfad.read_text(encoding="utf-8").splitlines():
        zeile = zeile.strip()
        if not zeile or zeile.startswith("#") or "=" not in zeile:
            continue
        if zeile.startswith("export "):
            zeile = zeile[len("export "):]
        name, _, wert = zeile.partition("=")
        wert = _entquote(wert)
        if name.strip() and wert:
            werte[name.strip()] = wert
    return werte


def hole_schluessel(name: str, datei: dict | None = None) -> str | None:
    """Umgebung vor Datei. Leere Werte zählen als nicht gesetzt."""
    wert = os.environ.get(name)
    if wert:
        return wert
    if datei is None:
        datei = lese_schluesseldatei()
    return datei.get(name) or None


def pruefe_erreichbar(base_url: str, zeit: float = 5.0) -> None:
    """TCP-Verbindung zum Endpunkt. Schlägt bei Fehler mit EndpunktFehler fehl."""
    if os.environ.get("OMNI_AGENT_OHNE_NETZPRUEFUNG") == "1":
        return
    teile = urlparse(base_url)
    host = teile.hostname
    port = teile.port or (443 if teile.scheme == "https" else 80)
    try:
        with socket.create_connection((host, port), timeout=zeit):
            return
    except OSError as fehler:
        raise EndpunktFehler(f"{host}:{port} nicht erreichbar ({fehler.__class__.__name__}: {fehler})") from fehler
