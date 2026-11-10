"""Benannte Claude-Konten: beliebig viele, jedes mit eigenem Namen und eigenem Schlüssel.

Ein Konto ist ein Anbieter-Eintrag unter ~/.omni-agent/providers.d/konto-<name>.json (ohne Geheimnis)
plus eine Zeile OMNI_AGENT_KONTO_<NAME>=… in ~/.omni-agent/env. Aufruf: --anbieter claude-<name>.
"""
from __future__ import annotations

import json
import os
import re
import tempfile
from pathlib import Path

from .konfig import KonfigFehler, env_datei, home, lese_schluesseldatei

NAME_MUSTER = re.compile(r"^[a-z0-9][a-z0-9-]{0,30}$")
ARTEN = {
    "api": ("ANTHROPIC_API_KEY", "API-Schlüssel (empfohlen)"),
    "token": ("CLAUDE_CODE_OAUTH_TOKEN", "Abo-Token"),
}
HINWEIS_TOKEN = (
    "Abo-Token (CLAUDE_CODE_OAUTH_TOKEN): ob ein unbeaufsichtigter Lauf damit nach Anthropics Bedingungen "
    "zulässig ist, ist nicht belegt. Omni-Agent legt den Token nur in der Schlüsseldatei ab."
)


def pruefe_name(name: str) -> str:
    if not NAME_MUSTER.match(name or ""):
        raise KonfigFehler(
            f"Kontoname '{name}' ungültig. Erlaubt: Kleinbuchstaben, Ziffern, Bindestrich, höchstens 31 Zeichen, "
            "Beginn mit Buchstabe oder Ziffer (z. B. felipe, fps)."
        )
    return name


def konto_id(name: str) -> str:
    return f"claude-{pruefe_name(name)}"


def konto_env(name: str) -> str:
    return "OMNI_AGENT_KONTO_" + pruefe_name(name).upper().replace("-", "_")


def konto_datei(name: str) -> Path:
    return home() / "providers.d" / f"konto-{pruefe_name(name)}.json"


def _eintrag(name: str, art: str, titel: str | None) -> dict:
    hinweis = (
        "Eigenes Kontingent dieses Kontos. "
        + (HINWEIS_TOKEN if art == "token" else "Abrechnung über den API-Schlüssel dieses Kontos.")
    )
    return {
        "id": konto_id(name),
        "name": titel or f"Claude-Konto {name}",
        "protokolle": ["anthropic"],
        "base_url": None,
        "key_envs": [konto_env(name)],
        "konto_art": art,
        "modelle": {"standard": "sonnet", "klein": "haiku", "stark": "opus"},
        "alle_stufen": False,
        "region": "Anthropic",
        "geprueft": False,
        "hinweis": hinweis,
    }


def lege_an(name: str, art: str, titel: str | None = None, ersetzen: bool = False) -> Path:
    if art not in ARTEN:
        raise KonfigFehler(f"Art '{art}' unbekannt. Erlaubt: {', '.join(ARTEN)}")
    pfad = konto_datei(name)
    if pfad.exists() and not ersetzen:
        raise KonfigFehler(f"Konto '{name}' gibt es schon ({pfad}). Mit --ersetzen überschreiben oder anderen Namen wählen.")
    pfad.parent.mkdir(parents=True, exist_ok=True)
    os.chmod(home(), 0o700)
    pfad.write_text(json.dumps({"anbieter": [_eintrag(name, art, titel)]}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return pfad


def liste() -> list:
    """Alle benannten Konten: name, art, titel, schluessel (gesetzt/fehlt)."""
    ordner = home() / "providers.d"
    if not ordner.is_dir():
        return []
    datei = lese_schluesseldatei()
    ergebnis = []
    for pfad in sorted(ordner.glob("konto-*.json")):
        try:
            e = json.loads(pfad.read_text(encoding="utf-8"))["anbieter"][0]
        except (OSError, ValueError, KeyError, IndexError):
            continue
        env = e["key_envs"][0]
        ergebnis.append({
            "name": pfad.stem[len("konto-"):],
            "id": e["id"],
            "art": e.get("konto_art", "api"),
            "titel": e.get("name", ""),
            "schluessel": "gesetzt" if (os.environ.get(env) or datei.get(env)) else "fehlt",
            "env": env,
        })
    return ergebnis


def _schreibe_env(zeilen: list) -> None:
    """Atomar und mit Rechten 600; die Schlüsseldatei ist nie halb geschrieben."""
    ziel = env_datei()
    fd, tmp = tempfile.mkstemp(dir=ziel.parent, prefix=".env-")
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write("\n".join(zeilen).rstrip("\n") + "\n")
        os.replace(tmp, ziel)
    except BaseException:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise


def _zeilen() -> list:
    pfad = env_datei()
    if not pfad.exists():
        return []
    lese_schluesseldatei()  # verweigert zu offene Rechte
    return pfad.read_text(encoding="utf-8").splitlines()


def _name_der_zeile(zeile: str) -> str:
    z = zeile.strip()
    if not z or z.startswith("#") or "=" not in z:
        return ""
    if z.startswith("export "):
        z = z[len("export "):]
    return z.partition("=")[0].strip()


def setze_schluessel(env_name: str, wert: str) -> None:
    zeilen = _zeilen()
    neu, gesetzt = [], False
    for z in zeilen:
        if _name_der_zeile(z) == env_name:
            if not gesetzt:
                neu.append(f"{env_name}={wert}")
                gesetzt = True
            continue
        neu.append(z)
    if not gesetzt:
        neu.append(f"{env_name}={wert}")
    _schreibe_env(neu)


def benenne_schluessel_um(alt: str, neu: str) -> None:
    """Übernimmt einen vorhandenen Eintrag unter neuem Namen, ohne den Wert anzufassen."""
    zeilen = _zeilen()
    if not any(_name_der_zeile(z) == alt for z in zeilen):
        raise KonfigFehler(f"In {env_datei()} steht keine Zeile {alt}=…")
    if any(_name_der_zeile(z) == neu for z in zeilen):
        raise KonfigFehler(f"In {env_datei()} gibt es {neu} schon.")
    ergebnis = []
    for z in zeilen:
        if _name_der_zeile(z) == alt:
            roh = z.strip()
            roh = roh[len("export "):] if roh.startswith("export ") else roh
            ergebnis.append(neu + "=" + roh.partition("=")[2])
        else:
            ergebnis.append(z)
    _schreibe_env(ergebnis)


def entferne(name: str, mit_schluessel: bool = False) -> None:
    pfad = konto_datei(name)
    if not pfad.exists():
        raise KonfigFehler(f"Konto '{name}' gibt es nicht. Vorhandene: omni-agent konto list")
    pfad.unlink()
    if mit_schluessel:
        env = konto_env(name)
        zeilen = _zeilen()
        rest = [z for z in zeilen if _name_der_zeile(z) != env]
        if len(rest) != len(zeilen):
            _schreibe_env(rest)


# ---------- Nutzung / Limits ----------

NUTZUNG_MODELL = "claude-haiku-5-5"
MESSAGES_URL = "https://api.anthropic.com/v1/messages"


def _hole_header(env_name: str, art: str, schluessel: str) -> dict:
    """Eine Ein-Token-Anfrage an das kleinste Modell; die Antwort trägt die Limits als Header.

    Verbraucht praktisch nichts, zählt aber als eine Anfrage. Der Schlüssel geht nur an api.anthropic.com.
    """
    import urllib.request
    kopf = {"anthropic-version": "2023-06-01", "content-type": "application/json", "User-Agent": "omni-agent"}
    system = None
    if art == "token":
        kopf["Authorization"] = f"Bearer {schluessel}"
        kopf["anthropic-beta"] = "oauth-2025-04-20"
        system = "You are Claude Code, Anthropic's official CLI for Claude."
    else:
        kopf["x-api-key"] = schluessel
    koerper = {"model": NUTZUNG_MODELL, "max_tokens": 1, "messages": [{"role": "user", "content": "."}]}
    if system:
        koerper["system"] = system
    anfrage = urllib.request.Request(MESSAGES_URL, data=json.dumps(koerper).encode(), headers=kopf)
    try:
        with urllib.request.urlopen(anfrage, timeout=20) as antwort:
            return {k.lower(): v for k, v in antwort.headers.items()}
    except Exception as fehler:  # HTTPError trägt Header und Status, Netzfehler nicht
        kopfzeilen = getattr(fehler, "headers", None)
        code = getattr(fehler, "code", None)
        if kopfzeilen is not None and code == 429:
            return {k.lower(): v for k, v in kopfzeilen.items()} | {"_status": "429"}
        raise KonfigFehler(f"HTTP {code}" if code else f"nicht erreichbar ({type(fehler).__name__})") from None


def _zeit(epoch: str) -> str:
    from datetime import datetime
    try:
        t = datetime.fromtimestamp(int(epoch))
        return f"{('Mo','Di','Mi','Do','Fr','Sa','So')[t.weekday()]} {t:%d.%m. %H:%M}"
    except (ValueError, OSError):
        return "?"


def _in(epoch: str) -> str:
    import time
    try:
        rest = int(epoch) - int(time.time())
    except ValueError:
        return ""
    if rest <= 0:
        return "jetzt"
    tage, std, minuten = rest // 86400, rest % 86400 // 3600, rest % 3600 // 60
    return f"{tage} Tg {std} Std" if tage else (f"{std} Std {minuten} Min" if std else f"{minuten} Min")


def _prozent(wert: str | None) -> str:
    try:
        return f"{round(float(wert) * 100)}%"
    except (TypeError, ValueError):
        return "–"


def nutzung_text(header: dict, art: str) -> str:
    """Aus den Rate-Limit-Headern eine Zeile machen. Fehlendes Fenster heißt: dort läuft gerade keins."""
    if art == "token":
        teile = []
        for fenster, name in (("5h", "5 Std"), ("7d", "7 Tage")):
            u = header.get(f"anthropic-ratelimit-unified-{fenster}-utilization")
            r = header.get(f"anthropic-ratelimit-unified-{fenster}-reset")
            teile.append(f"{name} {_prozent(u)}" + (f", Reset {_zeit(r)} (in {_in(r)})" if u is not None and r else ""))
        status = header.get("anthropic-ratelimit-unified-status", "")
        zusatz = "" if status in ("", "allowed") else f"   STATUS: {status}"
        return "  |  ".join(teile) + zusatz
    teile = []
    for schluessel, name in (("requests", "Anfragen"), ("tokens", "Tokens")):
        rest = header.get(f"anthropic-ratelimit-{schluessel}-remaining")
        grenze = header.get(f"anthropic-ratelimit-{schluessel}-limit")
        if rest is not None and grenze is not None:
            teile.append(f"{name} frei {rest}/{grenze}")
    return "   ".join(teile) or "keine Limit-Angaben in der Antwort"


def nutzung(konto: dict, abruf=_hole_header) -> str:
    """Nutzungszeile für ein Konto aus liste(). Fehler werden Text, nie eine Ausnahme."""
    if konto["schluessel"] != "gesetzt":
        return "Schlüssel fehlt"
    datei = lese_schluesseldatei()
    wert = os.environ.get(konto["env"]) or datei.get(konto["env"])
    try:
        return nutzung_text(abruf(konto["env"], konto["art"], wert), konto["art"])
    except KonfigFehler as fehler:
        return f"Abfrage fehlgeschlagen: {fehler}"
