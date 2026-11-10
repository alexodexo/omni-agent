"""Nutzung und Guthaben je Anbieter: so viel anzeigen, wie der Anbieter hergibt.

- Codex: Auslastung der Zeitfenster, Plan, Guthaben und Reset-Gutschriften über `codex app-server`
  (Methode `account/rateLimits/read`, die Anmeldung der Codex-CLI selbst; Omni-Agent speichert nichts).
- DeepSeek, Kimi (Moonshot), OpenRouter, EUrouter: Guthaben über die Abfrage-Adresse des Anbieters.
  Der Schlüssel geht nur an den Anbieter, dem er gehört.
- Claude-Konten: siehe konten.py (Rate-Limit-Header).
- Alle anderen (Ollama, Nvidia, eigene Anbieter): keine Angabe, das steht dann auch so da.

Jede Abfrage macht aus einem Fehler einen Text, nie eine Ausnahme.
"""
from __future__ import annotations

import json
import select
import subprocess
import time
import urllib.request

from .konfig import KonfigFehler
from .konten import _in, _zeit


def _fenster_name(minuten) -> str:
    try:
        m = int(minuten)
    except (TypeError, ValueError):
        return "Fenster"
    if m % 10080 == 0:
        return "7 Tage" if m == 10080 else f"{m // 10080} Wochen"
    if m % 1440 == 0:
        return f"{m // 1440} Tage"
    if m % 60 == 0:
        return f"{m // 60} Std"
    return f"{m} Min"


def codex_text(antwort: dict) -> str:
    """Aus der Antwort von account/rateLimits/read eine Zeile machen."""
    r = antwort.get("rateLimits") or {}
    teile = []
    plan = r.get("planType")
    if plan and plan != "unknown":
        teile.append(f"Plan {plan}")
    for schluessel in ("primary", "secondary"):
        f = r.get(schluessel)
        if not f:
            continue
        zeile = f"{_fenster_name(f.get('windowDurationMins'))} {f.get('usedPercent', '?')}% genutzt"
        if f.get("resetsAt"):
            zeile += f", Reset {_zeit(str(f['resetsAt']))} (in {_in(str(f['resetsAt']))})"
        teile.append(zeile)
    if not any(r.get(k) for k in ("primary", "secondary")):
        teile.append("keine Zeitfenster gemeldet")
    credits = r.get("credits") or {}
    if credits.get("unlimited"):
        teile.append("Guthaben unbegrenzt")
    elif credits.get("balance") not in (None, "", "0", "0.0"):
        teile.append(f"Guthaben {credits['balance']}")
    gutschriften = (antwort.get("rateLimitResetCredits") or {}).get("availableCount")
    if gutschriften:
        teile.append(f"{gutschriften} Reset-Gutschrift{'en' if gutschriften != 1 else ''} verfügbar")
    status = []
    if antwort.get("ordinaryUsageAllowed") is False:
        status.append("normale Nutzung gesperrt")
    if r.get("rateLimitReachedType"):
        status.append(f"Limit erreicht ({r['rateLimitReachedType']})")
    if status:
        teile.append("STATUS: " + ", ".join(status))
    return "  |  ".join(teile)


def _app_server_abfrage(exe: str, timeout: int = 25) -> dict:
    """Fragt `codex app-server` (JSON-Zeilen über stdin/stdout) nach den Limits des angemeldeten Kontos."""
    try:
        p = subprocess.Popen([exe, "app-server"], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                             stderr=subprocess.DEVNULL, text=True)
    except OSError as fehler:
        raise KonfigFehler(f"codex nicht startbar ({type(fehler).__name__})") from None

    def senden(o):
        p.stdin.write(json.dumps(o) + "\n")
        p.stdin.flush()

    def lesen(nummer):
        ende = time.time() + timeout
        while time.time() < ende:
            bereit, _, _ = select.select([p.stdout], [], [], 1)
            if not bereit:
                continue
            zeile = p.stdout.readline()
            if not zeile:
                break
            try:
                o = json.loads(zeile)
            except ValueError:
                continue
            if o.get("id") == nummer:
                return o
        raise KonfigFehler("keine Antwort von codex app-server")

    try:
        senden({"id": 1, "method": "initialize", "params": {"clientInfo": {"name": "omni-agent", "title": "Omni-Agent", "version": "1"}}})
        lesen(1)
        senden({"method": "initialized"})
        senden({"id": 2, "method": "account/rateLimits/read"})
        antwort = lesen(2)
    except (BrokenPipeError, OSError):
        raise KonfigFehler("codex app-server hat die Verbindung beendet") from None
    finally:
        p.terminate()
    if antwort.get("error"):
        raise KonfigFehler(str((antwort["error"] or {}).get("message") or "Fehler von codex"))
    return antwort.get("result") or {}


def codex_nutzung(abruf=_app_server_abfrage) -> str:
    from .runner import RUNNER
    exe = RUNNER["codex"].pfad()
    if not exe:
        return "codex nicht installiert"
    try:
        return codex_text(abruf(exe))
    except KonfigFehler as fehler:
        return f"Abfrage fehlgeschlagen: {fehler}"


# ---------- Guthaben der Fremdanbieter ----------

def _hole_json(url: str, schluessel: str) -> dict:
    anfrage = urllib.request.Request(url, headers={"Authorization": f"Bearer {schluessel}", "Accept": "application/json", "User-Agent": "omni-agent"})
    try:
        with urllib.request.urlopen(anfrage, timeout=15) as antwort:
            return json.loads(antwort.read().decode("utf-8"))
    except Exception as fehler:
        code = getattr(fehler, "code", None)
        raise KonfigFehler(f"HTTP {code}" if code else f"nicht erreichbar ({type(fehler).__name__})") from None


def _betrag(wert) -> str:
    try:
        return f"{float(wert):.2f}"
    except (TypeError, ValueError):
        return str(wert)


def _deepseek(schluessel: str, hole=_hole_json) -> str:
    d = hole("https://api.deepseek.com/user/balance", schluessel)
    teile = []
    for b in d.get("balance_infos") or []:
        zeile = f"Guthaben {_betrag(b.get('total_balance'))} {b.get('currency', '')}".strip()
        extra = []
        if b.get("granted_balance") not in (None, "0.00", "0"):
            extra.append(f"geschenkt {_betrag(b['granted_balance'])}")
        if b.get("topped_up_balance") not in (None, "0.00", "0"):
            extra.append(f"aufgeladen {_betrag(b['topped_up_balance'])}")
        teile.append(zeile + (f" ({', '.join(extra)})" if extra else ""))
    if d.get("is_available") is False:
        teile.append("STATUS: Guthaben reicht nicht für Anfragen")
    return "  |  ".join(teile) or "keine Angaben"


def _kimi(schluessel: str, hole=_hole_json) -> str:
    d = (hole("https://api.moonshot.ai/v1/users/me/balance", schluessel).get("data")) or {}
    teile = [f"verfügbar {_betrag(d.get('available_balance'))}"]
    if d.get("voucher_balance") not in (None, 0, "0"):
        teile.append(f"Gutscheine {_betrag(d['voucher_balance'])}")
    if d.get("cash_balance") not in (None, 0, "0"):
        teile.append(f"bar {_betrag(d['cash_balance'])}")
    return "Guthaben " + ", ".join(teile)


def _credits(basis: str, einheit: str):
    def abfrage(schluessel: str, hole=_hole_json) -> str:
        d = (hole(f"{basis}/credits", schluessel).get("data")) or {}
        gesamt, verbraucht = d.get("total_credits"), d.get("total_usage")
        if gesamt is None:
            return "keine Angaben"
        try:
            rest = float(gesamt) - float(verbraucht or 0)
            return f"Guthaben {rest:.2f} {einheit} (geladen {float(gesamt):.2f}, verbraucht {float(verbraucht or 0):.2f})"
        except (TypeError, ValueError):
            return f"Guthaben geladen {gesamt}, verbraucht {verbraucht}"
    return abfrage


ABFRAGEN = {
    "deepseek": _deepseek,
    "kimi": _kimi,
    "openrouter": _credits("https://openrouter.ai/api/v1", "USD"),
    "eurouter": _credits("https://api.eurouter.ai/api/v1", "EUR"),
}


def guthaben(anbieter_id: str, schluessel: str | None, abfragen=None) -> str:
    """Eine Zeile Guthaben oder ein ehrlicher Satz, warum es keine gibt."""
    abfragen = ABFRAGEN if abfragen is None else abfragen
    if anbieter_id == "ollama":
        return "läuft lokal, kein Guthaben"
    if anbieter_id not in abfragen:
        return "keine Abfrage bekannt"
    if not schluessel:
        return "Schlüssel fehlt"
    try:
        return abfragen[anbieter_id](schluessel)
    except KonfigFehler as fehler:
        return f"Abfrage fehlgeschlagen: {fehler}"
