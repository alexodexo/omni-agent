"""Extra LiteLLM: lokaler Übersetzer von Anthropic-Format nach OpenAI-Chat. Optional, nie Pflicht.

Lieferkette: Die Version ist fest gepinnt und per Hash-Sperre (extras/litellm/requirements.lock) installiert,
in einer eigenen virtuellen Umgebung. Der Proxy lauscht nur auf 127.0.0.1 und bekommt nur EINEN Anbieter-Schlüssel.
Hintergrund: litellm 1.107.0 war am 21.10.2026 kompromittiert (PyPI und Docker-Images). Vor jedem Pin-Wechsel
die Vorfallsseite des Herstellers lesen.
"""
import json
import os
import re
import secrets
import signal
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

from .konfig import WURZEL, KonfigFehler, home

SPERRDATEI = WURZEL / "extras" / "litellm" / "requirements.lock"
SPERRPYTHON = (3, 14)  # Version, für die die Sperrdatei gebaut wurde
BEKANNT_SCHLECHT = ("litellm_init.pth",)  # Merkmal des Angriffs vom März 2026


def ordner():
    return home() / "extras" / "litellm"


def port() -> int:
    return int(os.environ.get("OMNI_AGENT_LITELLM_PORT", "4000"))


def gepinnte_version() -> str:
    treffer = re.search(r"^litellm==([\w.\-]+)", SPERRDATEI.read_text(encoding="utf-8"), re.M)
    return treffer.group(1) if treffer else "unbekannt"


def venv_python():
    return ordner() / "venv" / "bin" / "python"


def installiert() -> bool:
    return (ordner() / "venv" / "bin" / "litellm").exists()


def installieren(trotzdem: bool = False) -> None:
    if sys.version_info[:2] != SPERRPYTHON and not trotzdem:
        raise KonfigFehler(
            f"Die Sperrdatei ist für Python {SPERRPYTHON[0]}.{SPERRPYTHON[1]} gebaut, hier läuft "
            f"{sys.version_info[0]}.{sys.version_info[1]}. Mit --trotzdem auf eigenes Risiko versuchen "
            f"oder statt des Übersetzers --runner opencode nehmen."
        )
    ziel = ordner()
    ziel.mkdir(parents=True, exist_ok=True)
    os.chmod(home(), 0o700)
    venv = ziel / "venv"
    print(f"Lege isolierte Umgebung an: {venv}", flush=True)
    subprocess.run([sys.executable, "-m", "venv", str(venv)], check=True)
    print(f"Installiere litellm=={gepinnte_version()} mit Hash-Prüfung ...", flush=True)
    erg = subprocess.run(
        [str(venv_python()), "-m", "pip", "install", "--require-hashes", "--no-deps", "--disable-pip-version-check",
         "-r", str(SPERRDATEI)],
    )
    if erg.returncode != 0:
        raise KonfigFehler("Installation fehlgeschlagen (Hash-Prüfung oder Netz). Nichts wurde freigegeben.")
    for name in BEKANNT_SCHLECHT:
        if any(venv.rglob(name)):
            raise KonfigFehler(f"WARNUNG: {name} gefunden. Umgebung {venv} löschen und alle Schlüssel rotieren!")
    ausgabe = subprocess.run(
        [str(venv_python()), "-c", "import importlib.metadata as m; print(m.version('litellm'))"],
        capture_output=True, text=True,
    ).stdout.strip()
    print(f"Fertig: litellm {ausgabe}. Starten mit: omni-agent extras litellm start <anbieter>", flush=True)


def _zustandsdatei():
    return ordner() / "laeuft.json"


def _zustand() -> dict | None:
    try:
        z = json.loads(_zustandsdatei().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    try:
        os.kill(z["pid"], 0)
    except (OSError, KeyError):
        return None
    return z


def _gesund() -> bool:
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port()}/health/liveliness", timeout=3) as r:
            return r.status == 200
    except (urllib.error.URLError, OSError):
        return False


def erzeuge_konfig(anbieter, modell: str) -> str:
    """config.yaml ohne Geheimnisse: der Schlüssel kommt aus der Umgebung des Proxys."""
    lt = anbieter.litellm or {}
    praefix = lt.get("praefix", "openai")
    key_env = lt.get("key_env") or (anbieter.key_envs[0] if anbieter.key_envs else "OMNI_AGENT_PROVIDER_KEY")
    api_base = lt["api_base"] if "api_base" in lt else anbieter.base_url
    zeilen = [
        "model_list:",
        f"  - model_name: {json.dumps(modell)}",
        "    litellm_params:",
        f"      model: {json.dumps(f'{praefix}/{modell}')}",
        f"      api_key: os.environ/{key_env}",
    ]
    if api_base:
        zeilen.append(f"      api_base: {json.dumps(api_base)}")
    zeilen += ["litellm_settings:", "  telemetry: false", "  drop_params: true"]
    return "\n".join(zeilen) + "\n"


def starte_proxy(anbieter, modell: str, anbieter_key: str):
    """Startet (oder nutzt) den Proxy für genau diesen Anbieter und dieses Modell. Gibt (base_url, Zugangsschlüssel) zurück."""
    if not installiert():
        raise KonfigFehler("Extra LiteLLM ist nicht installiert. Zuerst: omni-agent extras litellm install")
    ziel = ordner()
    schluesseldatei = ziel / "masterkey"
    if not schluesseldatei.exists():
        fd = os.open(schluesseldatei, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "w") as f:
            f.write("sk-lokal-" + secrets.token_hex(16))
    master = schluesseldatei.read_text(encoding="utf-8").strip()
    adresse = f"http://127.0.0.1:{port()}"

    z = _zustand()
    if z and z.get("anbieter") == anbieter.id and z.get("modell") == modell and _gesund():
        return adresse, master
    if z:
        stoppe_proxy()

    (ziel / "config.yaml").write_text(erzeuge_konfig(anbieter, modell), encoding="utf-8")
    lt = anbieter.litellm or {}
    key_env = lt.get("key_env") or anbieter.key_envs[0]
    env = {
        "HOME": str(Path.home()), "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
        key_env: anbieter_key, "LITELLM_MASTER_KEY": master,
    }
    logdatei = open(ziel / "proxy.log", "ab")
    proc = subprocess.Popen(
        [str(ziel / "venv" / "bin" / "litellm"), "--config", str(ziel / "config.yaml"),
         "--host", "127.0.0.1", "--port", str(port())],
        env=env, stdout=logdatei, stderr=logdatei, stdin=subprocess.DEVNULL, start_new_session=True,
    )
    _zustandsdatei().write_text(json.dumps({"pid": proc.pid, "anbieter": anbieter.id, "modell": modell}), encoding="utf-8")
    for _ in range(90):
        if _gesund():
            return adresse, master
        if proc.poll() is not None:
            break
        time.sleep(1)
    raise KonfigFehler(f"LiteLLM-Proxy startet nicht. Siehe {ziel / 'proxy.log'}")


def stoppe_proxy() -> bool:
    z = _zustand()
    if not z:
        return False
    try:
        os.killpg(z["pid"], signal.SIGTERM)
    except (ProcessLookupError, PermissionError):
        pass
    try:
        _zustandsdatei().unlink()
    except OSError:
        pass
    return True


def status_text() -> str:
    if not installiert():
        return "LiteLLM: nicht installiert (optional). Installieren: omni-agent extras litellm install"
    z = _zustand()
    basis = f"LiteLLM {gepinnte_version()} installiert"
    if z and _gesund():
        return f"{basis}, läuft auf 127.0.0.1:{port()} für {z['anbieter']} / {z['modell']}"
    return f"{basis}, läuft nicht"
