"""Anbieter: Wer liefert das Modell, in welchem Format, mit welchem Schlüssel."""
import json
from dataclasses import dataclass, field

from .konfig import WURZEL, KonfigFehler, home

PROTOKOLLE = ("anthropic", "openai-chat", "openai-responses")


@dataclass
class Anbieter:
    id: str
    name: str
    protokolle: tuple
    base_url: str | None
    key_envs: tuple
    modelle: dict
    region: str = "nicht belegt"
    hinweis: str = ""
    geprueft: bool = False
    leere_vars: tuple = ()
    key_platzhalter: str | None = None
    alle_stufen: bool = True
    modell_pflicht: bool = False
    litellm: dict = field(default_factory=dict)

    @property
    def lokal(self) -> bool:
        return bool(self.base_url) and ("localhost" in self.base_url or "127.0.0.1" in self.base_url)

    @property
    def braucht_schluessel(self) -> bool:
        return bool(self.key_envs)

    def modell_waehlen(self, wunsch: str | None) -> str:
        if wunsch:
            # Kurzname aus der Anbieter-Tabelle (standard/stark/klein) oder freier Modellname
            return self.modelle.get(wunsch, wunsch)
        if self.modell_pflicht or "standard" not in self.modelle:
            raise KonfigFehler(f"{self.id}: bitte ein Modell mit --modell angeben (Name aus dem Katalog des Anbieters)")
        return self.modelle["standard"]


def _aus_dict(d: dict, quelle: str) -> Anbieter:
    for pflicht in ("id", "protokolle", "key_envs", "modelle"):
        if pflicht not in d:
            raise KonfigFehler(f"{quelle}: Feld '{pflicht}' fehlt")
    unbekannt = [p for p in d["protokolle"] if p not in PROTOKOLLE]
    if unbekannt:
        raise KonfigFehler(f"{quelle}: unbekanntes Protokoll {unbekannt} (erlaubt: {', '.join(PROTOKOLLE)})")
    if not d.get("modell_pflicht") and "standard" not in d["modelle"]:
        raise KonfigFehler(f"{quelle}: 'modelle.standard' fehlt (oder 'modell_pflicht': true setzen)")
    return Anbieter(
        id=d["id"],
        name=d.get("name", d["id"]),
        protokolle=tuple(d["protokolle"]),
        base_url=d.get("base_url"),
        key_envs=tuple(d["key_envs"]),
        modelle=dict(d["modelle"]),
        region=d.get("region", "nicht belegt"),
        hinweis=d.get("hinweis", ""),
        geprueft=bool(d.get("geprueft", False)),
        leere_vars=tuple(d.get("leere_vars", ())),
        key_platzhalter=d.get("key_platzhalter"),
        alle_stufen=bool(d.get("alle_stufen", True)),
        modell_pflicht=bool(d.get("modell_pflicht", False)),
        litellm=dict(d.get("litellm", {})),
    )


def _lade_datei(pfad) -> list:
    try:
        daten = json.loads(pfad.read_text(encoding="utf-8"))
    except (OSError, ValueError) as fehler:
        raise KonfigFehler(f"{pfad}: nicht lesbar ({fehler})") from fehler
    eintraege = daten["anbieter"] if isinstance(daten, dict) else daten
    return [_aus_dict(e, str(pfad)) for e in eintraege]


def lade_anbieter() -> dict:
    """providers.json aus dem Repo, danach eigene Einträge aus ~/.omni-agent/providers.d/*.json (überschreiben gleiche IDs)."""
    ergebnis = {}
    for a in _lade_datei(WURZEL / "providers.json"):
        ergebnis[a.id] = a
    eigene = home() / "providers.d"
    if eigene.is_dir():
        for pfad in sorted(eigene.glob("*.json")):
            for a in _lade_datei(pfad):
                ergebnis[a.id] = a
    return ergebnis


def hole_anbieter(anbieter_id: str) -> Anbieter:
    alle = lade_anbieter()
    if anbieter_id not in alle:
        raise KonfigFehler(f"Unbekannter Anbieter '{anbieter_id}'. Bekannt: {', '.join(sorted(alle))}")
    return alle[anbieter_id]
