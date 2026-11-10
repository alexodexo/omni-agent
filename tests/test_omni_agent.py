"""Tests für den Omni-Agent-Kern. Nur Standardbibliothek: python3 -m unittest discover -s tests -v

Kein Test spricht mit einem echten Anbieter. Der Ende-zu-Ende-Test nutzt ein vorgetäuschtes `claude`.
"""
import json
import os
import stat
import subprocess
import sys
import tempfile
import time
import textwrap
import unittest
from pathlib import Path

WURZEL = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WURZEL / "lib"))

from omni_agent import extras  # noqa: E402
from omni_agent.anbieter import Anbieter, hole_anbieter, lade_anbieter  # noqa: E402
from omni_agent.konfig import KonfigFehler, lese_schluesseldatei  # noqa: E402
from omni_agent.runner import RUNNER, loese_werkzeuge, passt, waehle_runner, wirksames_protokoll  # noqa: E402
from omni_agent.runner.basis import LaufKontext  # noqa: E402

BIN = WURZEL / "bin" / "omni-agent"
FAKE_KEY = "sk-test-12345678-nur-fuer-tests"


class MitHome(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.home = Path(self.tmp.name) / "oa"
        self._alt = os.environ.get("OMNI_AGENT_HOME")
        os.environ["OMNI_AGENT_HOME"] = str(self.home)
        self.addCleanup(self._zurueck)

    def _zurueck(self):
        if self._alt is None:
            os.environ.pop("OMNI_AGENT_HOME", None)
        else:
            os.environ["OMNI_AGENT_HOME"] = self._alt


class Anbieter_(unittest.TestCase):
    def test_alle_eintraege_gueltig(self):
        alle = lade_anbieter()
        for erwartet in ("deepseek", "openrouter", "kimi", "ollama", "eurouter", "nvidia", "claude-konto"):
            self.assertIn(erwartet, alle)

    def test_modellpflicht(self):
        with self.assertRaises(KonfigFehler):
            hole_anbieter("openrouter").modell_waehlen(None)
        self.assertEqual(hole_anbieter("openrouter").modell_waehlen("x/y"), "x/y")

    def test_kurzname(self):
        self.assertEqual(hole_anbieter("deepseek").modell_waehlen("stark"), "deepseek-v4-pro")

    def test_unbekanntes_protokoll_wird_abgelehnt(self):
        from omni_agent.anbieter import _aus_dict
        with self.assertRaises(KonfigFehler):
            _aus_dict({"id": "x", "protokolle": ["soap"], "key_envs": [], "modelle": {"standard": "m"}}, "test")

    def test_eigene_anbieter_ueberschreiben(self):
        with tempfile.TemporaryDirectory() as t:
            os.environ["OMNI_AGENT_HOME"] = t
            try:
                (Path(t) / "providers.d").mkdir()
                (Path(t) / "providers.d" / "meiner.json").write_text(json.dumps([
                    {"id": "meiner", "protokolle": ["anthropic"], "base_url": "http://x", "key_envs": ["K"], "modelle": {"standard": "m"}}
                ]))
                self.assertIn("meiner", lade_anbieter())
            finally:
                os.environ.pop("OMNI_AGENT_HOME", None)


class Passung(unittest.TestCase):
    def test_matrix(self):
        d, n, e, k = (hole_anbieter(x) for x in ("deepseek", "nvidia", "eurouter", "claude-konto"))
        self.assertTrue(passt(d, RUNNER["claude"]))
        self.assertFalse(passt(n, RUNNER["claude"]))
        self.assertTrue(passt(n, RUNNER["claude"], ueber_litellm=True))
        self.assertTrue(passt(n, RUNNER["opencode"]))
        self.assertFalse(passt(n, RUNNER["codex"]))
        self.assertTrue(passt(e, RUNNER["codex"]))
        self.assertFalse(passt(e, RUNNER["claude"]))
        self.assertTrue(passt(k, RUNNER["claude"]))
        self.assertFalse(passt(k, RUNNER["opencode"]))

    def test_dsh_nur_deepseek_und_nie_automatisch(self):
        self.assertTrue(passt(hole_anbieter("deepseek"), RUNNER["dsh"]))
        self.assertFalse(passt(hole_anbieter("kimi"), RUNNER["dsh"]))

    def test_wirksames_protokoll_ueber_litellm(self):
        self.assertEqual(wirksames_protokoll(hole_anbieter("nvidia"), RUNNER["claude"], True), "anthropic")
        self.assertIsNone(wirksames_protokoll(hole_anbieter("eurouter"), RUNNER["claude"], False))

    def test_unpassender_wunsch_nennt_ausweg(self):
        if not RUNNER["claude"].pfad():
            self.skipTest("claude nicht installiert")
        with self.assertRaises(KonfigFehler) as ctx:
            waehle_runner(hole_anbieter("nvidia"), "claude")
        self.assertIn("--ueber-litellm", str(ctx.exception))


class Werkzeuge(unittest.TestCase):
    def test_standard_ohne_shell(self):
        w = loese_werkzeuge(None, RUNNER["claude"])
        self.assertNotIn("shell", w)
        self.assertEqual(set(w), {"lesen", "schreiben", "web_suche", "web_laden"})

    def test_plus_minus(self):
        w = loese_werkzeuge("+shell -web_suche", RUNNER["claude"])
        self.assertIn("shell", w)
        self.assertNotIn("web_suche", w)

    def test_ersetzen(self):
        self.assertEqual(set(loese_werkzeuge("lesen,schreiben", RUNNER["claude"])), {"lesen", "schreiben"})

    def test_unbekanntes_werkzeug(self):
        with self.assertRaises(KonfigFehler):
            loese_werkzeuge("zaubern", RUNNER["claude"])

    def test_runner_ohne_sandbox_verlangt_shell_ausdruecklich(self):
        with self.assertRaises(KonfigFehler) as ctx:
            loese_werkzeuge(None, RUNNER["dsh"])
        self.assertIn("+shell", str(ctx.exception))
        self.assertIn("shell", loese_werkzeuge("+shell", RUNNER["dsh"]))

    def test_codex_shell_laeuft_in_der_sandbox_und_ist_sichtbar(self):
        w = loese_werkzeuge(None, RUNNER["codex"])
        self.assertIn("shell", w)  # immer da, aber nur im Sandkasten (Schreiben im Ordner, kein Netz)
        self.assertNotIn("web_suche", w)  # Standard schrumpft still, weil nicht verlangt

    def test_verlangtes_unmoegliches_wird_verweigert(self):
        with self.assertRaises(KonfigFehler):
            loese_werkzeuge("+web_suche,+shell", RUNNER["codex"])


class Schluesseldatei(MitHome):
    def test_rechte_zu_offen(self):
        self.home.mkdir()
        datei = self.home / "env"
        datei.write_text("A=bbbbbbbb\n")
        os.chmod(datei, 0o644)
        with self.assertRaises(KonfigFehler):
            lese_schluesseldatei()

    def test_parsen(self):
        self.home.mkdir()
        datei = self.home / "env"
        datei.write_text("# Kommentar\nexport A=eins\nB='zwei'\nC=\"drei\"\nLEER=\nohne gleich\n")
        os.chmod(datei, 0o600)
        self.assertEqual(lese_schluesseldatei(), {"A": "eins", "B": "zwei", "C": "drei"})

    def test_fehlt_ist_leer(self):
        self.assertEqual(lese_schluesseldatei(), {})


class ClaudeBefehl(unittest.TestCase):
    def _ctx(self, anbieter_id="deepseek", modell=None, base_url="auto", schluessel=None, werkzeuge=("lesen", "schreiben", "web_suche", "web_laden")):
        a = hole_anbieter(anbieter_id)
        return LaufKontext(
            prompt="auftrag", ordner=Path("/tmp/x"), anbieter=a, modell=modell or a.modelle["standard"],
            base_url=a.base_url if base_url == "auto" else base_url, protokoll="anthropic",
            schluessel=schluessel if schluessel is not None else {"DEEPSEEK_API_KEY": FAKE_KEY},
            werkzeuge=tuple(werkzeuge), max_runden=12,
        )

    def test_umgebung_ist_minimal_und_komplett(self):
        os.environ["ANTHROPIC_API_KEY"] = "darf-nicht-durchrutschen"
        os.environ["ANTHROPIC_BASE_URL"] = "http://falsch"
        try:
            b = RUNNER["claude"].baue(self._ctx())
        finally:
            os.environ.pop("ANTHROPIC_API_KEY")
            os.environ.pop("ANTHROPIC_BASE_URL")
        env = b.env
        self.assertEqual(env["ANTHROPIC_BASE_URL"], "https://api.deepseek.com/anthropic")
        self.assertEqual(env["ANTHROPIC_AUTH_TOKEN"], FAKE_KEY)
        for name in ("ANTHROPIC_MODEL", "ANTHROPIC_DEFAULT_OPUS_MODEL", "ANTHROPIC_DEFAULT_SONNET_MODEL",
                     "ANTHROPIC_DEFAULT_HAIKU_MODEL", "CLAUDE_CODE_SUBAGENT_MODEL"):
            self.assertEqual(env[name], "deepseek-flash", name)
        self.assertNotIn("darf-nicht-durchrutschen", json.dumps(env))
        self.assertNotIn("ANTHROPIC_API_KEY", env)

    def test_flags(self):
        argv = RUNNER["claude"].baue(self._ctx()).argv
        for flag in ("--strict-mcp-config", "--allowed-tools"):
            self.assertIn(flag, argv)
        self.assertEqual(argv[argv.index("--setting-sources") + 1], "project")
        self.assertEqual(argv[argv.index("--permission-mode") + 1], "dontAsk")
        self.assertNotIn("Bash", argv)
        self.assertNotIn("--no-session-persistence", argv)  # Sitzung bleibt, damit --fortsetzen geht

    def test_shell_nur_wenn_verlangt(self):
        argv = RUNNER["claude"].baue(self._ctx(werkzeuge=("lesen", "shell"))).argv
        self.assertIn("Bash", argv)

    def test_openrouter_gibt_leeren_anthropic_key(self):
        env = RUNNER["claude"].baue(self._ctx("openrouter", modell="x/y", schluessel={"OPENROUTER_API_KEY": FAKE_KEY})).env
        self.assertEqual(env["ANTHROPIC_API_KEY"], "")

    def test_kimi_haiku_stufe_nur_beim_standardmodell(self):
        a = hole_anbieter("kimi")
        env = RUNNER["claude"].baue(self._ctx("kimi", schluessel={"MOONSHOT_API_KEY": FAKE_KEY})).env
        self.assertEqual(env["ANTHROPIC_DEFAULT_HAIKU_MODEL"], a.modelle["klein"])
        env2 = RUNNER["claude"].baue(self._ctx("kimi", modell="eigenes", schluessel={"MOONSHOT_API_KEY": FAKE_KEY})).env
        self.assertEqual(env2["ANTHROPIC_DEFAULT_HAIKU_MODEL"], "eigenes")

    def test_ollama_platzhalter_statt_schluessel(self):
        env = RUNNER["claude"].baue(self._ctx("ollama", schluessel={})).env
        self.assertEqual(env["ANTHROPIC_AUTH_TOKEN"], "ollama")

    def test_claude_konto_setzt_keine_base_url(self):
        env = RUNNER["claude"].baue(self._ctx("claude-konto", modell="sonnet", base_url=None, schluessel={"ANTHROPIC_API_KEY": FAKE_KEY})).env
        self.assertNotIn("ANTHROPIC_BASE_URL", env)
        self.assertEqual(env["ANTHROPIC_API_KEY"], FAKE_KEY)

    def test_fortschritt_zaehlt_runden(self):
        zustand = {"runden": 0}
        zeile = json.dumps({"type": "assistant", "message": {"content": [{"type": "tool_use", "name": "WebSearch", "input": {"query": "x"}}]}})
        aus = RUNNER["claude"].fortschritt(zeile, zustand)
        self.assertEqual(zustand["runden"], 1)
        self.assertIn("WebSearch", aus[0])
        self.assertEqual(RUNNER["claude"].fortschritt("kein json", zustand), [])


class Konten(MitHome):
    def _cli(self, *argv, eingabe=None):
        env = {"PATH": os.environ["PATH"], "HOME": self.tmp.name, "OMNI_AGENT_HOME": str(self.home)}
        return subprocess.run([sys.executable, str(BIN), *argv], capture_output=True, text=True, env=env, input=eingabe)

    def _env_schreiben(self, text):
        self.home.mkdir(parents=True, exist_ok=True)
        os.chmod(self.home, 0o700)
        d = self.home / "env"
        d.write_text(text, encoding="utf-8")
        os.chmod(d, 0o600)
        return d

    def test_beliebig_viele_konten_nebeneinander(self):
        from omni_agent import konten
        for n, art in (("felipe", "token"), ("fps", "api"), ("dritte-firma", "api")):
            konten.lege_an(n, art)
        self.assertEqual({k["name"] for k in konten.liste()}, {"felipe", "fps", "dritte-firma"})
        self.assertEqual(hole_anbieter("claude-fps").key_envs, ("OMNI_AGENT_KONTO_FPS",))
        self.assertEqual(hole_anbieter("claude-dritte-firma").key_envs, ("OMNI_AGENT_KONTO_DRITTE_FIRMA",))

    def test_ungueltige_namen_abgelehnt(self):
        from omni_agent import konten
        for n in ("", "Felipe", "../x", "a b", "-x", "x" * 40):
            with self.assertRaises(KonfigFehler, msg=n):
                konten.lege_an(n, "api")

    def test_doppelter_name_nur_mit_ersetzen(self):
        from omni_agent import konten
        konten.lege_an("fps", "api")
        with self.assertRaises(KonfigFehler):
            konten.lege_an("fps", "api")
        konten.lege_an("fps", "token", ersetzen=True)
        self.assertEqual(hole_anbieter("claude-fps").konto_art, "token")

    def test_konto_nur_mit_claude_runner(self):
        from omni_agent import konten
        konten.lege_an("fps", "api")
        a = hole_anbieter("claude-fps")
        self.assertTrue(passt(a, RUNNER["claude"]))
        self.assertFalse(passt(a, RUNNER["opencode"]))

    def test_art_waehlt_den_richtigen_claude_schluessel(self):
        from omni_agent import konten
        konten.lege_an("tok", "token")
        konten.lege_an("api", "api")
        for name, erwartet, anderer in (("tok", "CLAUDE_CODE_OAUTH_TOKEN", "ANTHROPIC_API_KEY"), ("api", "ANTHROPIC_API_KEY", "CLAUDE_CODE_OAUTH_TOKEN")):
            a = hole_anbieter(f"claude-{name}")
            env = RUNNER["claude"].baue(ClaudeBefehl._ctx(self, f"claude-{name}", modell="sonnet", base_url=None, schluessel={a.key_envs[0]: FAKE_KEY})).env
            self.assertEqual(env[erwartet], FAKE_KEY)
            self.assertNotIn(anderer, env)
            self.assertNotIn("ANTHROPIC_BASE_URL", env)

    def test_add_uebernimmt_vorhandene_zeile_ohne_wert_zu_zeigen(self):
        d = self._env_schreiben(f"DEEPSEEK_API_KEY=abc\nCLAUDE_CODE_OAUTH_TOKEN={FAKE_KEY}\n")
        erg = self._cli("konto", "add", "felipe", "--art", "token", "--uebernehme", "CLAUDE_CODE_OAUTH_TOKEN")
        self.assertEqual(erg.returncode, 0, erg.stderr)
        self.assertNotIn(FAKE_KEY, erg.stdout + erg.stderr)
        inhalt = d.read_text()
        self.assertIn(f"OMNI_AGENT_KONTO_FELIPE={FAKE_KEY}", inhalt)
        self.assertNotIn("CLAUDE_CODE_OAUTH_TOKEN=", inhalt)
        self.assertIn("DEEPSEEK_API_KEY=abc", inhalt)
        self.assertEqual(stat.S_IMODE(d.stat().st_mode), 0o600)

    def test_add_ohne_terminal_gibt_anleitung_und_nie_schluessel(self):
        self._env_schreiben("")
        erg = self._cli("konto", "add", "fps", "--art", "api")
        self.assertEqual(erg.returncode, 0, erg.stderr)
        self.assertIn("Schlüssel fehlt noch", erg.stdout)
        self.assertIn("OMNI_AGENT_KONTO_FPS", erg.stdout)

    def test_uebernehme_fehlende_zeile_scheitert_sauber(self):
        self._env_schreiben("DEEPSEEK_API_KEY=abc\n")
        erg = self._cli("konto", "add", "felipe", "--art", "token", "--uebernehme", "GIBT_ES_NICHT")
        self.assertEqual(erg.returncode, 2)

    def test_list_und_remove(self):
        d = self._env_schreiben(f"OMNI_AGENT_KONTO_FPS={FAKE_KEY}\n")
        self._cli("konto", "add", "fps", "--art", "api")
        liste = self._cli("konto", "list", "--ohne-nutzung")
        self.assertIn("claude-fps", liste.stdout)
        self.assertIn("gesetzt", liste.stdout)
        self.assertNotIn(FAKE_KEY, liste.stdout)
        self._cli("konto", "remove", "fps", "--mit-schluessel")
        self.assertNotIn("OMNI_AGENT_KONTO_FPS", d.read_text())
        self.assertIn("Noch kein", self._cli("konto", "list", "--ohne-nutzung").stdout)

    def test_nutzung_abo_aus_headern(self):
        from omni_agent import konten
        h = {"anthropic-ratelimit-unified-5h-utilization": "0.04", "anthropic-ratelimit-unified-5h-reset": "1793977200",
             "anthropic-ratelimit-unified-7d-utilization": "0.29", "anthropic-ratelimit-unified-7d-reset": "1794499200",
             "anthropic-ratelimit-unified-status": "allowed"}
        text = konten.nutzung_text(h, "token")
        self.assertIn("5 Std 4%", text)
        self.assertIn("7 Tage 29%, Reset", text)
        self.assertIn("(in ", text)
        self.assertNotIn("STATUS", text)
        h["anthropic-ratelimit-unified-status"] = "rejected"
        self.assertIn("STATUS: rejected", konten.nutzung_text(h, "token"))

    def test_nutzung_fehlendes_fenster_ist_strich(self):
        from omni_agent import konten
        self.assertIn("5 Std –", konten.nutzung_text({"anthropic-ratelimit-unified-7d-utilization": "0.1"}, "token"))

    def test_nutzung_api_schluessel_aus_headern(self):
        from omni_agent import konten
        h = {"anthropic-ratelimit-requests-remaining": "49", "anthropic-ratelimit-requests-limit": "50",
             "anthropic-ratelimit-tokens-remaining": "39000", "anthropic-ratelimit-tokens-limit": "40000"}
        text = konten.nutzung_text(h, "api")
        self.assertIn("Anfragen frei 49/50", text)
        self.assertIn("Tokens frei 39000/40000", text)

    def test_nutzung_fehler_wird_text_und_gibt_schluessel_nicht_preis(self):
        from omni_agent import konten
        konten.lege_an("fps", "api")
        self._env_schreiben(f"OMNI_AGENT_KONTO_FPS={FAKE_KEY}\n")
        def kaputt(env, art, schluessel):
            raise KonfigFehler("HTTP 401")
        text = konten.nutzung(konten.liste()[0], abruf=kaputt)
        self.assertIn("Abfrage fehlgeschlagen", text)
        self.assertNotIn(FAKE_KEY, text)

    def test_standard_konto_setzen_lesen_loeschen(self):
        self._cli("konto", "add", "fbs", "--art", "token")
        self.assertIn("keiner", self._cli("konto", "standard").stdout)
        self.assertEqual(self._cli("konto", "standard", "fbs").returncode, 0)
        self.assertIn("claude-fbs", self._cli("konto", "standard").stdout)
        self.assertIn("[STANDARD]", self._cli("konto", "list", "--ohne-nutzung").stdout)
        self._cli("konto", "standard", "--loeschen")
        self.assertIn("keiner", self._cli("konto", "standard").stdout)

    def test_standard_nur_fuer_vorhandenes_konto(self):
        self.assertEqual(self._cli("konto", "standard", "gibtsnicht").returncode, 2)

    def test_run_ohne_anbieter_und_ohne_standard_scheitert_klar(self):
        erg = self._cli("run", "--text", "x")
        self.assertEqual(erg.returncode, 2)
        self.assertIn("Standard", erg.stderr + erg.stdout)

    def test_run_konto_und_anbieter_schliessen_sich_aus(self):
        erg = self._cli("run", "--text", "x", "--konto", "fbs", "--anbieter", "deepseek")
        self.assertEqual(erg.returncode, 2)

    def test_run_ohne_anbieter_nimmt_standard_konto(self):
        self._cli("konto", "add", "fbs", "--art", "token")
        self._cli("konto", "standard", "fbs")
        erg = self._cli("run", "--text", "x")  # Schlüssel fehlt: scheitert, nennt aber den Standard
        self.assertIn("Standard: claude-fbs", erg.stdout)
        self.assertEqual(erg.returncode, 2)

    def test_konto_im_anbieter_befehl_sichtbar(self):
        self._cli("konto", "add", "fps", "--art", "api")
        self.assertIn("claude-fps", self._cli("anbieter").stdout)


class OpencodeCodex(unittest.TestCase):
    def _ctx(self, anbieter_id, protokoll, werkzeuge):
        a = hole_anbieter(anbieter_id)
        return LaufKontext(prompt="p", ordner=Path("/tmp/x"), anbieter=a, modell="m", base_url=a.base_url,
                           protokoll=protokoll, schluessel={a.key_envs[0]: FAKE_KEY}, werkzeuge=werkzeuge, max_runden=5)

    def test_opencode_konfig_ohne_schluesselwert(self):
        b = RUNNER["opencode"].baue(self._ctx("nvidia", "openai-chat", ("lesen", "schreiben")))
        konfig = json.loads(b.env["OPENCODE_CONFIG_CONTENT"])
        self.assertNotIn(FAKE_KEY, b.env["OPENCODE_CONFIG_CONTENT"])
        self.assertEqual(konfig["permission"]["bash"], "deny")
        self.assertEqual(konfig["permission"]["edit"], "allow")
        self.assertEqual(b.env["NVIDIA_API_KEY"], FAKE_KEY)

    def test_codex_argumente(self):
        b = RUNNER["codex"].baue(self._ctx("eurouter", "openai-responses", ("lesen", "schreiben", "shell")))
        self.assertIn("workspace-write", b.argv)
        self.assertTrue(any("wire_api = \"responses\"" in x for x in b.argv))
        self.assertNotIn(FAKE_KEY, " ".join(b.argv))


class CodexUndFortsetzen(unittest.TestCase):
    def _ctx(self, anbieter_id, **extra):
        a = hole_anbieter(anbieter_id)
        return LaufKontext(prompt="p", ordner=Path("/tmp/x"), anbieter=a, modell="gpt-x", base_url=a.base_url,
                           protokoll="openai-responses", schluessel={}, werkzeuge=("lesen", "schreiben", "shell"),
                           max_runden=5, extra=extra)

    def test_codex_anmeldung_nutzt_nur_login_nicht_die_nutzerkonfiguration(self):
        b = RUNNER["codex"].baue(self._ctx("codex", aufwand="low"))
        self.assertIn("--ignore-user-config", b.argv)
        self.assertIn("--ignore-rules", b.argv)
        self.assertEqual(b.argv[b.argv.index("--model") + 1], "gpt-x")
        self.assertIn('model_reasoning_effort="low"', b.argv)
        self.assertFalse(any("model_provider" in x for x in b.argv))
        self.assertNotIn("OPENAI_API_KEY", b.env)

    def test_anbieter_codex_laeuft_nur_ueber_codex(self):
        a = hole_anbieter("codex")
        self.assertTrue(passt(a, RUNNER["codex"]))
        self.assertFalse(passt(a, RUNNER["claude"]))
        self.assertFalse(passt(hole_anbieter("claude-konto"), RUNNER["codex"]))

    def test_codex_fortsetzen_nutzt_resume(self):
        b = RUNNER["codex"].baue(self._ctx("codex", fortsetzen="thread-1"))
        self.assertEqual(b.argv[1:3], ["exec", "resume"])
        self.assertIn("thread-1", b.argv)
        self.assertNotIn("--cd", b.argv)

    def test_codex_merkt_sich_die_sitzung(self):
        z = {}
        RUNNER["codex"].fortschritt(json.dumps({"type": "thread.started", "thread_id": "t-9"}), z)
        self.assertEqual(z["sitzung"], "t-9")

    def test_claude_fortsetzen_nutzt_resume(self):
        a = hole_anbieter("claude-konto")
        ctx = LaufKontext(prompt="p", ordner=Path("/tmp/x"), anbieter=a, modell="sonnet", base_url=None, protokoll="anthropic",
                          schluessel={"ANTHROPIC_API_KEY": FAKE_KEY}, werkzeuge=("lesen",), max_runden=5, extra={"fortsetzen": "sess-7"})
        argv = RUNNER["claude"].baue(ctx).argv
        self.assertEqual(argv[argv.index("--resume") + 1], "sess-7")


class Plugin(unittest.TestCase):
    def test_version_in_plugin_json_gleich_kern(self):
        from omni_agent import VERSION
        manifest = json.loads((WURZEL / ".claude-plugin" / "plugin.json").read_text())
        self.assertEqual(manifest["version"], VERSION)

    def test_skills_haben_beschreibung(self):
        for ordner in sorted((WURZEL / "skills").iterdir()):
            kopf = (ordner / "SKILL.md").read_text().split("---")[1]
            self.assertIn("description:", kopf, ordner.name)

    def test_agent_ist_fuer_claude_selbst_rufbar_auch_im_goal(self):
        # /goal und Hauptfaden dürfen keine gesperrten Befehle rufen. Sie delegieren über den Agent-Typ omni-agent:lauf,
        # dessen Beschreibung Omni-Agent und die Anbieter nennt, ohne dass die Nutzerin einen Befehl tippen muss.
        beschreibung = (WURZEL / "agents" / "lauf.md").read_text().split("---")[1]
        for wort in ("Omni-Agent", "Codex", "fbs, felipe, llc", "Proaktiv", "Nie einen Fremdanbieter"):
            self.assertIn(wort, beschreibung)


class Extras(unittest.TestCase):
    def test_litellm_konfig_ohne_geheimnis(self):
        text = extras.erzeuge_konfig(hole_anbieter("nvidia"), "z-ai/glm-5.3-flash")
        self.assertIn("nvidia_nim/z-ai/glm-5.3-flash", text)
        self.assertIn("os.environ/NVIDIA_NIM_API_KEY", text)
        self.assertNotIn("api_base", text)
        self.assertIn("telemetry: false", text)

    def test_litellm_generisch_nutzt_openai_und_base(self):
        text = extras.erzeuge_konfig(hole_anbieter("eurouter"), "gpt-x")
        self.assertIn('"openai/gpt-x"', text)
        self.assertIn("api.eurouter.ai", text)

    def test_sperrdatei_gepinnt_mit_hashes(self):
        inhalt = extras.SPERRDATEI.read_text()
        self.assertEqual(extras.gepinnte_version(), "1.106.3")
        self.assertNotIn("1.107.0", inhalt.split("litellm==")[1][:12])
        self.assertGreater(inhalt.count("--hash=sha256:"), 100)


FAKE_CLAUDE = textwrap.dedent("""\
    #!/usr/bin/env python3
    import json, os, sys, time
    modus = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "modus")).read().strip()
    if "--version" in sys.argv:
        print("0.0.0 (Fake)"); sys.exit(0)
    with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "argv.log"), "a") as f:
        f.write(json.dumps(sys.argv[1:]) + "\\n")
    with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "cwd.log"), "a") as f:
        f.write(os.getcwd() + "\\n")
    print(json.dumps({"type": "system", "subtype": "init", "model": os.environ.get("ANTHROPIC_MODEL"), "session_id": "sess-1"}), flush=True)
    print(json.dumps({"type": "assistant", "message": {"content": [{"type": "tool_use", "name": "WebSearch", "input": {"query": "test"}}]}}), flush=True)
    print("Zeile mit Geheimnis: " + os.environ.get("ANTHROPIC_AUTH_TOKEN", ""), flush=True)
    sys.stderr.write("stderr mit Geheimnis: " + os.environ.get("ANTHROPIC_AUTH_TOKEN", "") + "\\n")
    if modus == "haengt":
        time.sleep(60)
    if modus == "ok":
        open("bericht.md", "w").write("# Bericht\\nFertig\\n" + sys.argv[2][-80:] + "\\n")
    if modus in ("block", "allow"):
        open("bericht.md", "w").write(("BLOCK: Datei m.py Zeile 1 ist kaputt" if modus == "block" else "ALLOW: sieht gut aus") + "\\nDetails\\n")
    if modus == "kurz":
        time.sleep(2)
        open("bericht.md", "w").write("# Bericht\\nSpaet fertig\\n")
    print(json.dumps({"type": "result", "subtype": "success", "num_turns": 1, "duration_ms": 10, "total_cost_usd": 0,
                      "result": "Schlussantwort des Agenten" if modus == "antwort" else "ok"}), flush=True)
""")


class Farm(MitHome):
    def setUp(self):
        super().setUp()
        self.bin = Path(self.tmp.name) / "bin"
        self.bin.mkdir()
        fake = self.bin / "claude"
        fake.write_text(FAKE_CLAUDE)
        fake.chmod(fake.stat().st_mode | stat.S_IXUSR)
        self.env = {
            "PATH": f"{self.bin}{os.pathsep}/usr/bin:/bin:{Path(sys.executable).parent}",
            "HOME": self.tmp.name, "OMNI_AGENT_HOME": str(self.home),
            "OMNI_AGENT_OHNE_NETZPRUEFUNG": "1", "DEEPSEEK_API_KEY": FAKE_KEY,
        }

    def lauf(self, *args, modus="ok"):
        (self.bin / "modus").write_text(modus)  # Umgebungsvariablen erreichen den Runner absichtlich nicht
        return subprocess.run([sys.executable, str(BIN), *args], env=dict(self.env), capture_output=True, text=True, timeout=60)

    def letzter_lauf(self) -> Path:
        return sorted((self.home / "laeufe").iterdir())[-1]

    def _repo(self, inhalt="a = 1\n"):
        repo = Path(self.tmp.name) / "repo"
        repo.mkdir()
        git = lambda *a: subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@t", *a], cwd=repo, check=True, capture_output=True)
        git("init", "-q", ".")
        (repo / "m.py").write_text(inhalt)
        git("add", ".")
        git("commit", "-qm", "init")
        return repo, git

    def _review(self, repo, *args, modus="ok"):
        (self.bin / "modus").write_text(modus)
        return subprocess.run([sys.executable, str(BIN), "review", *args], env=dict(self.env), cwd=repo,
                              capture_output=True, text=True, timeout=60)


class EndeZuEnde(Farm):
    def test_lauf_mit_bericht(self):
        erg = self.lauf("run", "--text", "Sag hallo", "--anbieter", "deepseek", "--runner", "claude")
        self.assertEqual(erg.returncode, 0, erg.stderr)
        ordner = self.letzter_lauf()
        status = json.loads((ordner / "status.json").read_text())
        self.assertEqual(status["zustand"], "fertig")
        self.assertEqual(status["runden"], 1)
        self.assertEqual(status["anbieter"], "deepseek")
        self.assertTrue((ordner / "bericht.md").exists())
        self.assertIn("Sag hallo", (ordner / "auftrag.md").read_text())
        self.assertIn("Werkzeug 1: WebSearch", erg.stdout)

    def test_geheimnisse_werden_geschwaerzt(self):
        self.lauf("run", "--text", "x", "--anbieter", "deepseek")
        ordner = self.letzter_lauf()
        for datei in ("log.jsonl", "fehler.log"):
            inhalt = (ordner / datei).read_text()
            self.assertNotIn(FAKE_KEY, inhalt, datei)
            self.assertIn("***", inhalt, datei)

    def test_ohne_bericht_ist_fehler(self):
        erg = self.lauf("run", "--text", "x", "--anbieter", "deepseek", modus="ohne")
        self.assertEqual(erg.returncode, 1)
        self.assertEqual(json.loads((self.letzter_lauf() / "status.json").read_text())["zustand"], "fehler")

    def test_zeitlimit(self):
        erg = self.lauf("run", "--text", "x", "--anbieter", "deepseek", "--zeit", "3", modus="haengt")
        self.assertEqual(erg.returncode, 124)
        status = json.loads((self.letzter_lauf() / "status.json").read_text())
        self.assertEqual(status["zustand"], "fehler")
        self.assertIn("Zeitlimit", status["bemerkung"])

    def test_fehlender_schluessel_exit_2(self):
        self.env.pop("DEEPSEEK_API_KEY")
        erg = self.lauf("run", "--text", "x", "--anbieter", "deepseek")
        self.assertEqual(erg.returncode, 2)
        self.assertIn("DEEPSEEK_API_KEY", erg.stderr)
        self.assertNotIn(FAKE_KEY, erg.stderr)

    def test_unbekannter_anbieter_exit_2(self):
        self.assertEqual(self.lauf("run", "--text", "x", "--anbieter", "gibtsnicht").returncode, 2)

    def test_nicht_erreichbar_exit_3(self):
        self.env.pop("OMNI_AGENT_OHNE_NETZPRUEFUNG")
        (self.home / "providers.d").mkdir(parents=True)
        (self.home / "providers.d" / "tot.json").write_text(json.dumps([
            {"id": "tot", "protokolle": ["anthropic"], "base_url": "http://127.0.0.1:9", "key_envs": [], "key_platzhalter": "x", "modelle": {"standard": "m"}}
        ]))
        erg = self.lauf("run", "--text", "x", "--anbieter", "tot", "--runner", "claude")
        self.assertEqual(erg.returncode, 3, erg.stderr)

    def test_fortsetzen_nutzt_gleiche_sitzung_und_aktualisiert_bericht(self):
        self.lauf("run", "--text", "Erstauftrag", "--anbieter", "deepseek")
        ordner = self.letzter_lauf()
        self.assertEqual(json.loads((ordner / "status.json").read_text())["sitzung"], "sess-1")
        erg = self.lauf("run", "--fortsetzen", "--text", "Nachfrage eins")
        self.assertEqual(erg.returncode, 0, erg.stderr)
        self.assertEqual(len(list((self.home / "laeufe").iterdir())), 1)  # gleicher Ordner, kein neuer
        aufrufe = [json.loads(z) for z in (self.bin / "argv.log").read_text().splitlines()]
        self.assertEqual(aufrufe[1][aufrufe[1].index("--resume") + 1], "sess-1")
        self.assertNotIn("--resume", aufrufe[0])
        self.assertIn("Nachfrage eins", (ordner / "auftrag.md").read_text())
        status = json.loads((ordner / "status.json").read_text())
        self.assertEqual((status["zustand"], status["nachfragen"], status["anbieter"]), ("fertig", 1, "deepseek"))

    def test_fortsetzen_mit_altem_bericht_zaehlt_nicht_als_fertig(self):
        self.lauf("run", "--text", "Erstauftrag", "--anbieter", "deepseek")
        ordner = self.letzter_lauf()
        os.utime(ordner / "bericht.md", (1_000_000, 1_000_000))
        erg = self.lauf("run", "--fortsetzen", "--text", "Nachfrage", modus="ohne")
        self.assertEqual(erg.returncode, 1)
        self.assertEqual(json.loads((ordner / "status.json").read_text())["zustand"], "fehler")

    def test_fortsetzen_ohne_nachfrage_oder_sitzung_scheitert_sauber(self):
        self.lauf("run", "--text", "x", "--anbieter", "deepseek")
        self.assertEqual(self.lauf("run", "--fortsetzen").returncode, 2)
        ordner = self.letzter_lauf()
        status = json.loads((ordner / "status.json").read_text())
        status.pop("sitzung")
        (ordner / "status.json").write_text(json.dumps(status))
        self.assertEqual(self.lauf("run", "--fortsetzen", "--text", "y").returncode, 2)

    def test_fortsetzen_anderer_anbieter_wird_verweigert(self):
        self.lauf("run", "--text", "x", "--anbieter", "deepseek")
        self.assertEqual(self.lauf("run", "--fortsetzen", "--anbieter", "kimi", "--text", "y").returncode, 2)

    def test_result_zeigt_bericht_und_pfad(self):
        self.lauf("run", "--text", "Ergebnisfrage", "--anbieter", "deepseek")
        erg = self.lauf("result")
        self.assertIn("# Bericht", erg.stdout)
        self.assertIn("--fortsetzen", erg.stdout)
        self.assertTrue(self.lauf("result", "--pfad").stdout.strip().endswith("bericht.md"))

    def test_result_ohne_laeufe_scheitert_klar(self):
        self.assertEqual(self.lauf("result").returncode, 2)

    def test_cancel_bricht_laufenden_lauf_ab(self):
        (self.bin / "modus").write_text("haengt")
        proc = subprocess.Popen([sys.executable, str(BIN), "run", "--text", "x", "--anbieter", "deepseek", "--zeit", "60"],
                                env=dict(self.env), stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        try:
            for _ in range(60):
                time.sleep(0.25)
                laeufe = list((self.home / "laeufe").iterdir()) if (self.home / "laeufe").exists() else []
                if laeufe and (laeufe[0] / "log.jsonl").exists() and (laeufe[0] / "log.jsonl").stat().st_size > 0:
                    break  # der Runner läuft und hängt
            erg = subprocess.run([sys.executable, str(BIN), "cancel"], env=dict(self.env), capture_output=True, text=True, timeout=60)
            self.assertEqual(erg.returncode, 0, erg.stderr)
            self.assertIn("abgebrochen", erg.stdout)
            proc.wait(timeout=20)
            self.assertEqual(json.loads((self.letzter_lauf() / "status.json").read_text())["zustand"], "abgebrochen")
        finally:
            if proc.poll() is None:
                proc.kill()

    def test_cancel_ohne_laufenden_lauf(self):
        self.assertIn("Kein Lauf arbeitet", self.lauf("cancel").stdout)

    def test_cancel_raeumt_toten_lauf_auf(self):
        ordner = self.home / "laeufe" / "20260101-000000-tot"
        ordner.mkdir(parents=True)
        (ordner / "status.json").write_text(json.dumps({"zustand": "arbeitet", "pid": 999999, "lauf": str(ordner)}))
        self.assertIn("schon weg", self.lauf("cancel").stdout)
        self.assertEqual(json.loads((ordner / "status.json").read_text())["zustand"], "fehler")

    # ---- review ----
    def test_review_gibt_diff_als_material_und_nur_lesen_schreiben(self):
        repo, _ = self._repo()
        (repo / "m.py").write_text("a = 2\n")
        erg = self._review(repo, "--anbieter", "deepseek", "--adversarial", "Rechte prüfen")
        self.assertEqual(erg.returncode, 0, erg.stderr)
        ordner = self.letzter_lauf()
        self.assertIn("+a = 2", (ordner / "aenderungen.patch").read_text())
        self.assertIn("M\tm.py", (ordner / "geaenderte_dateien.txt").read_text())
        auftrag = (ordner / "auftrag.md").read_text()
        self.assertIn("gegnerisch", auftrag)
        self.assertIn("Rechte prüfen", auftrag)
        self.assertIn("lesen, schreiben", erg.stdout)
        self.assertNotIn("shell", erg.stdout.split("Werkzeuge:")[1].splitlines()[0])

    def test_review_vorschau_sendet_nichts(self):
        repo, _ = self._repo()
        (repo / "m.py").write_text("a = 2\n")
        erg = self._review(repo, "--anbieter", "deepseek", "--vorschau")
        self.assertEqual(erg.returncode, 0, erg.stderr)
        self.assertIn("nichts gesendet", erg.stdout)
        self.assertFalse((self.home / "laeufe").exists())

    def test_review_ohne_aenderungen(self):
        repo, _ = self._repo()
        erg = self._review(repo, "--anbieter", "deepseek")
        self.assertEqual(erg.returncode, 2)
        self.assertIn("Keine Änderungen", erg.stderr)

    def test_review_sperrt_diff_mit_geheimnis(self):
        repo, git = self._repo()
        (repo / "k.py").write_text('API_KEY = "sk-ant-api03-abcdefghijklmnopqrstuvwxyz0123456789ABCDEFG"\n')
        git("add", "-N", "k.py")
        erg = self._review(repo, "--anbieter", "deepseek")
        self.assertEqual(erg.returncode, 2)
        self.assertIn("Geheimnisse", erg.stderr)
        self.assertNotIn("sk-ant-api03-abcdefghij", erg.stdout + erg.stderr)
        self.assertFalse((self.home / "laeufe").exists())
        self.assertEqual(self._review(repo, "--anbieter", "deepseek", "--trotzdem").returncode, 0)

    def test_review_sperrt_env_datei(self):
        repo, git = self._repo()
        (repo / ".env").write_text("A=1\n")
        git("add", "-N", ".env")
        self.assertEqual(self._review(repo, "--anbieter", "deepseek").returncode, 2)

    def test_review_base_vergleicht_mit_branch(self):
        repo, git = self._repo()
        git("checkout", "-q", "-b", "feature")
        (repo / "m.py").write_text("a = 3\n")
        git("commit", "-qam", "aenderung")
        erg = self._review(repo, "--anbieter", "deepseek", "--base", "master") if self._hat_master(repo) else self._review(repo, "--anbieter", "deepseek", "--base", "main")
        self.assertEqual(erg.returncode, 0, erg.stderr)
        self.assertIn("+a = 3", (self.letzter_lauf() / "aenderungen.patch").read_text())

    def _hat_master(self, repo):
        return b"master" in subprocess.run(["git", "branch"], cwd=repo, capture_output=True).stdout

    def test_review_zu_grosser_diff(self):
        from omni_agent import review
        with self.assertRaises(KonfigFehler):
            review.pruefe({"diff": "+x\n" * (review.MAX_ZEICHEN // 2), "namen": "M\tm.py", "neu": [], "ziel": "t"}, False)

    def test_status_befehl(self):
        self.lauf("run", "--text", "x", "--anbieter", "deepseek")
        liste = self.lauf("status", "--json")
        daten = json.loads(liste.stdout)
        self.assertEqual(daten[0]["zustand"], "fertig")
        einzel = self.lauf("status", daten[0]["lauf"][:8], "--json")
        self.assertTrue(json.loads(einzel.stdout)["bericht"].endswith("bericht.md"))

    def test_setup_legt_schluesseldatei_mit_600_an(self):
        self.lauf("setup")
        datei = self.home / "env"
        self.assertTrue(datei.exists())
        self.assertEqual(stat.S_IMODE(datei.stat().st_mode), 0o600)
        self.assertEqual(stat.S_IMODE(self.home.stat().st_mode), 0o700)
        self.assertNotIn(FAKE_KEY, datei.read_text())

    def test_setup_ersetzt_veralteten_link_durch_weiterleiter_der_updates_ueberlebt(self):
        link_ordner = Path(self.tmp.name) / ".local" / "bin"
        link_ordner.mkdir(parents=True)
        (link_ordner / "omni-agent").symlink_to(Path(self.tmp.name) / "weg" / "omni-agent")  # zeigt ins Leere
        self.lauf("setup")
        link = link_ordner / "omni-agent"
        self.assertFalse(link.is_symlink())
        self.assertTrue(os.access(link, os.X_OK))
        self.assertIn("omni-agent-shim", link.read_text())
        # Plugin-Verzeichnis nachbauen: Weiterleiter folgt installed_plugins.json, nicht einem festen Pfad
        plugins = Path(self.tmp.name) / ".claude" / "plugins"
        plugins.mkdir(parents=True)
        (plugins / "installed_plugins.json").write_text(json.dumps(
            {"plugins": {"omni-agent@omni-agent": [{"installPath": str(WURZEL)}]}}))
        env = {"PATH": os.environ["PATH"], "HOME": self.tmp.name, "OMNI_AGENT_HOME": str(self.home)}
        erg = subprocess.run([str(link), "--version"], capture_output=True, text=True, env=env)
        self.assertEqual(erg.returncode, 0, erg.stderr)
        from omni_agent import VERSION
        self.assertIn(VERSION, erg.stdout)

    def test_setup_fasst_fremden_befehl_nicht_an(self):
        link_ordner = Path(self.tmp.name) / ".local" / "bin"
        link_ordner.mkdir(parents=True)
        fremd = link_ordner / "omni-agent"
        fremd.write_text("#!/bin/sh\necho fremd\n")
        os.chmod(fremd, 0o755)
        env = {"PATH": f"{link_ordner}:{os.environ['PATH']}", "HOME": self.tmp.name, "OMNI_AGENT_HOME": str(self.home)}
        subprocess.run([sys.executable, str(BIN), "setup"], capture_output=True, text=True, env=env)
        self.assertIn("fremd", fremd.read_text())

    def test_doctor_nennt_nie_den_schluessel(self):
        erg = self.lauf("doctor")
        self.assertNotIn(FAKE_KEY, erg.stdout + erg.stderr)
        self.assertIn("deepseek", erg.stdout)

    def test_arbeitsordner_muss_leer_sein(self):
        voll = Path(self.tmp.name) / "voll"
        voll.mkdir()
        (voll / "datei").write_text("x")
        erg = self.lauf("run", "--text", "x", "--anbieter", "deepseek", "--ordner", str(voll))
        self.assertEqual(erg.returncode, 2)


# ---------------------------------------------------------------------------
# Version 1.1: Subagent, Befehle, interne Skills, Hooks, losgelöste Läufe, Projektmodus, Review-Gate
# ---------------------------------------------------------------------------

def _frontmatter(pfad: Path) -> dict:
    text = pfad.read_text(encoding="utf-8")
    assert text.startswith("---\n"), pfad
    kopf = text.split("---\n", 2)[1]
    felder, schluessel = {}, None
    for zeile in kopf.splitlines():
        if zeile.startswith("  - ") and schluessel:
            felder.setdefault(schluessel, []).append(zeile[4:].strip())
        elif ":" in zeile and not zeile.startswith(" "):
            schluessel, _, wert = zeile.partition(":")
            felder[schluessel.strip()] = wert.strip() or []
    return felder


def _bash_zeilen(pfad: Path) -> list:
    """Befehlszeilen `omni-agent …` aus Code-Blöcken und !-Einschüben einer Plugin-Datei."""
    import re
    text = pfad.read_text(encoding="utf-8")
    zeilen = re.findall(r"^!`(.+)`$", text, flags=re.M)
    for block in re.findall(r"```(?:bash)?\n(.*?)```", text, flags=re.S):
        zeilen += [z for z in block.splitlines() if z.strip()]
    return [z.strip() for z in zeilen if "omni-agent" in z]


class PluginAufbau(unittest.TestCase):
    def test_agent_ist_duenner_weiterleiter(self):
        f = _frontmatter(WURZEL / "agents" / "lauf.md")
        self.assertEqual(f["name"], "lauf")
        self.assertEqual(f["tools"], "Bash")
        self.assertIn("Proaktiv", f["description"])
        for skill in f["skills"]:
            self.assertTrue((WURZEL / "skills" / skill / "SKILL.md").is_file(), skill)
        text = (WURZEL / "agents" / "lauf.md").read_text()
        self.assertIn("--warten 540", text)
        self.assertIn("timeout: 600000", text)

    def test_interne_skills_sind_nicht_aufrufbar(self):
        skills = sorted(p.parent.name for p in (WURZEL / "skills").glob("*/SKILL.md"))
        self.assertEqual(skills, ["omni-agent-auftrag", "omni-agent-ergebnis", "omni-agent-laufzeit"])
        for name in skills:
            self.assertEqual(_frontmatter(WURZEL / "skills" / name / "SKILL.md")["user-invocable"], "false", name)

    def test_befehle_vollstaendig_und_nur_setup_darf_das_modell_rufen(self):
        erwartet = {"run", "review", "adversarial-review", "status", "result", "cancel", "doctor", "konten", "setup"}
        vorhanden = {p.stem for p in (WURZEL / "commands").glob("*.md")}
        self.assertEqual(vorhanden, erwartet)
        for name in erwartet:
            f = _frontmatter(WURZEL / "commands" / f"{name}.md")
            self.assertTrue(f.get("description"), name)
            if name == "setup":
                self.assertNotIn("disable-model-invocation", f)
            else:
                self.assertEqual(f["disable-model-invocation"], "true", name)

    def test_run_befehl_ruft_agent_nicht_skill(self):
        text = (WURZEL / "commands" / "run.md").read_text()
        self.assertIn('subagent_type: "omni-agent:lauf"', text)
        self.assertIn("Agent", _frontmatter(WURZEL / "commands" / "run.md")["allowed-tools"])
        self.assertIn("AskUserQuestion", _frontmatter(WURZEL / "commands" / "run.md")["allowed-tools"])
        self.assertIn("omni-agent fortsetzbar", text)

    def test_adversarial_befehl_erzwingt_flag(self):
        self.assertIn("--adversarial", (WURZEL / "commands" / "adversarial-review.md").read_text())
        self.assertIn("omni-agent review --vorschau", (WURZEL / "commands" / "adversarial-review.md").read_text())

    def test_hooks_rufen_bekannte_hook_namen(self):
        daten = json.loads((WURZEL / "hooks" / "hooks.json").read_text())["hooks"]
        self.assertEqual(set(daten), {"SessionStart", "SessionEnd", "Stop"})
        befehle = {ereignis: daten[ereignis][0]["hooks"][0]["command"] for ereignis in daten}
        self.assertTrue(befehle["SessionStart"].endswith("hook start"))
        self.assertTrue(befehle["SessionEnd"].endswith("hook ende"))
        self.assertTrue(befehle["Stop"].endswith("hook stopp"))
        for b in befehle.values():
            self.assertIn('"${CLAUDE_PLUGIN_ROOT}/bin/omni-agent"', b)

    def test_dokumentierte_befehle_sind_echte_befehle(self):
        """Jede in Befehlen, Agent und Skills genannte Zeile `omni-agent …` muss der echte Parser annehmen (kein erfundenes Flag)."""
        import re
        import shlex
        from omni_agent.cli import baue_parser
        parser = baue_parser()
        dateien = list((WURZEL / "commands").glob("*.md")) + [WURZEL / "agents" / "lauf.md"] + list((WURZEL / "skills").glob("*/SKILL.md"))
        geprueft = 0
        for datei in dateien:
            for zeile in _bash_zeilen(datei):
                m = re.search(r"omni-agent ((?:run|review|status|result|cancel|warte|fortsetzbar|konto|doctor|setup|hook)\b[^\n|`]*)", zeile)
                if not m:
                    continue
                teile = shlex.split(m.group(1).replace("$ARGUMENTS", "").replace("…", "x").replace("[", "").replace("]", ""))
                teile = [t for t in teile if t not in ("|",) and not t.startswith("<")]
                # Platzhalter in Beispielen wie NAME, ID, LAUF, M sind gültige Werte
                try:
                    parser.parse_args(teile)
                except SystemExit:
                    self.fail(f"{datei.name}: Parser lehnt ab: omni-agent {m.group(1)}")
                geprueft += 1
        self.assertGreater(geprueft, 8)

    def test_skills_laufzeit_beispiele_parsen(self):
        from omni_agent.cli import baue_parser
        p = baue_parser()
        a = p.parse_args(["run", "--warten", "540", "--konto", "fbs", "--projekt", "--schreibend", "--fortsetzen", "--text", "x"])
        self.assertEqual((a.warten, a.konto, a.projekt, a.schreibend, a.fortsetzen), (540, "fbs", "", True, ""))
        w = p.parse_args(["warte", "20260101-000000", "--max", "540"])
        self.assertEqual((w.lauf, w.max), ("20260101-000000", 540))

    def test_keine_alten_skills_mehr(self):
        for alt in ("run", "review", "status", "doctor", "setup", "delegieren"):
            self.assertFalse((WURZEL / "skills" / alt).exists(), alt)


class LosgeloesteLaeufe(Farm):
    def test_hintergrund_meldet_sofort_und_lauf_geht_weiter(self):
        (self.bin / "modus").write_text("kurz")
        t0 = time.time()
        erg = subprocess.run([sys.executable, str(BIN), "run", "--hintergrund", "--text", "x", "--anbieter", "deepseek"],
                             env=dict(self.env), capture_output=True, text=True, timeout=30)
        self.assertEqual(erg.returncode, 0, erg.stderr)
        self.assertLess(time.time() - t0, 5)
        self.assertIn("Gestartet:", erg.stdout)
        ordner = self.letzter_lauf()
        self.assertEqual(json.loads((ordner / "status.json").read_text())["zustand"], "arbeitet")
        for _ in range(60):
            time.sleep(0.5)
            if json.loads((ordner / "status.json").read_text())["zustand"] != "arbeitet":
                break
        self.assertEqual(json.loads((ordner / "status.json").read_text())["zustand"], "fertig")
        self.assertTrue((ordner / "konsole.log").read_text().strip())  # Konsole des Laufs liegt im Ordner

    def test_warten_liefert_bericht_mit_marke_fertig(self):
        erg = self.lauf("run", "--warten", "30", "--text", "Sag hallo", "--anbieter", "deepseek")
        self.assertEqual(erg.returncode, 0, erg.stderr)
        zeilen = erg.stdout.splitlines()
        self.assertTrue(zeilen[0].startswith("Gestartet:"))
        self.assertTrue(any(z.startswith("[fertig]") for z in zeilen))
        self.assertIn("# Bericht", erg.stdout)
        self.assertIn("Nachfrage an denselben Agenten", erg.stdout)

    def test_warten_zu_kurz_meldet_laeuft_noch_und_warte_setzt_fort(self):
        (self.bin / "modus").write_text("kurz")
        erg = subprocess.run([sys.executable, str(BIN), "run", "--warten", "0", "--text", "x", "--anbieter", "deepseek"],
                             env=dict(self.env), capture_output=True, text=True, timeout=30)
        self.assertEqual(erg.returncode, 0, erg.stderr)
        self.assertIn("[läuft noch]", erg.stdout)
        self.assertIn("omni-agent warte", erg.stdout)
        zweite = subprocess.run([sys.executable, str(BIN), "warte", "--max", "30"], env=dict(self.env), capture_output=True, text=True, timeout=60)
        self.assertEqual(zweite.returncode, 0, zweite.stderr)
        self.assertIn("[fertig]", zweite.stdout)
        self.assertIn("Spaet fertig", zweite.stdout)

    def test_warten_meldet_fehler_mit_grund_und_exit_1(self):
        erg = self.lauf("run", "--warten", "30", "--text", "x", "--anbieter", "deepseek", modus="ohne")
        self.assertEqual(erg.returncode, 1)
        self.assertIn("[fehler]", erg.stdout)
        self.assertIn("Letzte Zeilen aus fehler.log", erg.stdout)
        self.assertNotIn(FAKE_KEY, erg.stdout)

    def test_frueher_fehler_wird_durchgereicht(self):
        erg = self.lauf("run", "--hintergrund", "--text", "x", "--anbieter", "gibtsnicht")
        self.assertEqual(erg.returncode, 2)
        self.assertIn("Unbekannter Anbieter", erg.stderr)

    def test_abbrechen_eines_losgeloesten_laufs(self):
        (self.bin / "modus").write_text("haengt")
        erg = subprocess.run([sys.executable, str(BIN), "run", "--hintergrund", "--text", "x", "--anbieter", "deepseek", "--zeit", "60"],
                             env=dict(self.env), capture_output=True, text=True, timeout=30)
        self.assertEqual(erg.returncode, 0, erg.stderr)
        abbruch = subprocess.run([sys.executable, str(BIN), "cancel"], env=dict(self.env), capture_output=True, text=True, timeout=60)
        self.assertIn("abgebrochen", abbruch.stdout)
        self.assertEqual(json.loads((self.letzter_lauf() / "status.json").read_text())["zustand"], "abgebrochen")

    def test_ohne_flags_bleibt_run_blockierend_ohne_gestartet_zeile(self):
        erg = self.lauf("run", "--text", "x", "--anbieter", "deepseek")
        self.assertNotIn("Gestartet:", erg.stdout)


class SitzungenUndHooks(Farm):
    def test_lauf_merkt_sich_claude_sitzung_und_status_filtert(self):
        self.env["OMNI_AGENT_SITZUNG"] = "sitzung-a"
        self.lauf("run", "--text", "erster", "--anbieter", "deepseek")
        self.env["OMNI_AGENT_SITZUNG"] = "sitzung-b"
        self.lauf("run", "--text", "zweiter", "--anbieter", "deepseek")
        status = json.loads(self.lauf("status", "--json").stdout)
        self.assertEqual(len(status), 1)
        self.assertEqual(status[0]["auftrag"], "zweiter")
        alle = json.loads(self.lauf("status", "--json", "--alle").stdout)
        self.assertEqual(len(alle), 2)

    def test_status_ohne_sitzung_zeigt_alles_und_markdown_tabelle(self):
        self.lauf("run", "--text", "Tabellenprobe", "--anbieter", "deepseek")
        md = self.lauf("status", "--md").stdout
        self.assertIn("| Lauf | Zustand |", md)
        self.assertIn("Tabellenprobe", md)

    def test_result_und_cancel_nehmen_standardmaessig_die_eigene_sitzung(self):
        self.env["OMNI_AGENT_SITZUNG"] = "a"
        self.lauf("run", "--text", "Auftrag A", "--anbieter", "deepseek")
        self.env["OMNI_AGENT_SITZUNG"] = "b"
        self.lauf("run", "--text", "Auftrag B", "--anbieter", "deepseek")
        self.env["OMNI_AGENT_SITZUNG"] = "a"
        self.assertIn("Auftrag A", self.lauf("result").stdout)  # neuester Lauf von a, nicht der neueste überhaupt
        self.env["OMNI_AGENT_SITZUNG"] = "ganz-neu"
        self.assertIn("Auftrag B", self.lauf("result").stdout)  # Sitzung ohne Läufe: Rückfall auf den neuesten

    def test_fortsetzbar(self):
        self.env["OMNI_AGENT_SITZUNG"] = "a"
        self.assertEqual(json.loads(self.lauf("fortsetzbar").stdout), {"available": False})
        self.lauf("run", "--text", "Erster", "--anbieter", "deepseek")
        erg = json.loads(self.lauf("fortsetzbar").stdout)
        self.assertTrue(erg["available"])
        self.assertEqual(erg["anbieter"], "deepseek")
        self.env["OMNI_AGENT_SITZUNG"] = "andere"
        self.assertEqual(json.loads(self.lauf("fortsetzbar").stdout), {"available": False})

    def _hook(self, name, eingabe, env_extra=None):
        env = dict(self.env, **(env_extra or {}))
        return subprocess.run([sys.executable, str(BIN), "hook", name], env=env, input=json.dumps(eingabe),
                              capture_output=True, text=True, timeout=60)

    def test_hook_start_schreibt_sitzung_in_env_datei(self):
        datei = Path(self.tmp.name) / "claude-env"
        erg = self._hook("start", {"session_id": "abc-123"}, {"CLAUDE_ENV_FILE": str(datei)})
        self.assertEqual(erg.returncode, 0, erg.stderr)
        self.assertEqual(datei.read_text(), "export OMNI_AGENT_SITZUNG='abc-123'\n")

    def test_hook_ohne_env_datei_oder_im_lauf_tut_nichts(self):
        self.assertEqual(self._hook("start", {"session_id": "x"}).returncode, 0)
        datei = Path(self.tmp.name) / "claude-env"
        erg = self._hook("start", {"session_id": "x"}, {"CLAUDE_ENV_FILE": str(datei), "OMNI_AGENT_LAUF": "1"})
        self.assertEqual(erg.returncode, 0)
        self.assertFalse(datei.exists())

    def test_hook_ende_beendet_nur_laufende_dieser_sitzung(self):
        (self.bin / "modus").write_text("haengt")
        env = dict(self.env, OMNI_AGENT_SITZUNG="s1")
        erg = subprocess.run([sys.executable, str(BIN), "run", "--hintergrund", "--text", "x", "--anbieter", "deepseek", "--zeit", "60"],
                             env=env, capture_output=True, text=True, timeout=30)
        self.assertEqual(erg.returncode, 0, erg.stderr)
        ordner = self.letzter_lauf()
        self._hook("ende", {"session_id": "fremde-sitzung"})
        self.assertEqual(json.loads((ordner / "status.json").read_text())["zustand"], "arbeitet")
        self._hook("ende", {"session_id": "s1", "reason": "clear"})
        self.assertEqual(json.loads((ordner / "status.json").read_text())["zustand"], "arbeitet")
        self._hook("ende", {"session_id": "s1", "reason": "other"})
        for _ in range(40):
            time.sleep(0.5)
            if json.loads((ordner / "status.json").read_text())["zustand"] != "arbeitet":
                break
        self.assertEqual(json.loads((ordner / "status.json").read_text())["zustand"], "abgebrochen")


class Projektmodus(Farm):
    def setUp(self):
        super().setUp()
        self.env["OMNI_AGENT_KONTO_TK"] = FAKE_KEY
        self.assertEqual(self.lauf("konto", "add", "tk", "--art", "api").returncode, 0)
        self.projekt = Path(self.tmp.name) / "projekt"
        self.projekt.mkdir()
        (self.projekt / "code.py").write_text("x = 1\n")

    def _lauf_in(self, cwd, *args, modus="antwort"):
        (self.bin / "modus").write_text(modus)
        return subprocess.run([sys.executable, str(BIN), *args], env=dict(self.env), cwd=cwd, capture_output=True, text=True, timeout=60)

    def test_agent_arbeitet_im_projekt_nur_lesend_und_bericht_kommt_aus_schlussantwort(self):
        erg = self._lauf_in(self.projekt, "run", "--konto", "tk", "--projekt", "--text", "Lies code.py")
        self.assertEqual(erg.returncode, 0, erg.stderr)
        self.assertEqual((self.bin / "cwd.log").read_text().strip(), str(self.projekt.resolve()))
        argv = json.loads((self.bin / "argv.log").read_text().splitlines()[-1])
        werkzeuge = argv[argv.index("--allowed-tools") + 1:]
        self.assertIn("Read", werkzeuge)
        self.assertNotIn("Write", werkzeuge)
        self.assertNotIn("Edit", werkzeuge)
        self.assertNotIn("Bash", werkzeuge)
        ordner = self.letzter_lauf()
        self.assertIn("Schlussantwort des Agenten", (ordner / "bericht.md").read_text())
        self.assertFalse((self.projekt / "bericht.md").exists())  # nichts im Projekt hinterlassen
        self.assertIn("nur lesen", erg.stdout)
        status = json.loads((ordner / "status.json").read_text())
        self.assertEqual((status["zustand"], status["projekt"], status["schreibend"]), ("fertig", str(self.projekt.resolve()), False))
        self.assertIn("Projektordner", (self.bin / "argv.log").read_text())  # Projekt-Rahmen im Prompt

    def test_schreibend_gibt_write_und_edit_frei(self):
        erg = self._lauf_in(self.projekt, "run", "--konto", "tk", "--projekt", "--schreibend", "--text", "Ändere code.py")
        self.assertEqual(erg.returncode, 0, erg.stderr)
        argv = json.loads((self.bin / "argv.log").read_text().splitlines()[-1])
        werkzeuge = argv[argv.index("--allowed-tools") + 1:]
        self.assertIn("Write", werkzeuge)
        self.assertIn("Edit", werkzeuge)
        self.assertNotIn("Bash", werkzeuge)

    def test_projekt_mit_fremdanbieter_wird_verweigert(self):
        erg = self._lauf_in(self.projekt, "run", "--anbieter", "deepseek", "--projekt", "--text", "x")
        self.assertEqual(erg.returncode, 2)
        self.assertIn("nur mit Claude-Konten und Codex", erg.stderr)
        self.assertFalse((self.home / "laeufe").exists())

    def test_schreibend_ohne_projekt_und_projekt_mit_material_scheitern(self):
        self.assertEqual(self._lauf_in(self.projekt, "run", "--konto", "tk", "--schreibend", "--text", "x").returncode, 2)
        material = Path(self.tmp.name) / "mat"
        material.mkdir()
        self.assertEqual(self._lauf_in(self.projekt, "run", "--konto", "tk", "--projekt", "--material", str(material), "--text", "x").returncode, 2)

    def test_explizit_verlangtes_schreiben_ohne_schreibend_scheitert(self):
        erg = self._lauf_in(self.projekt, "run", "--konto", "tk", "--projekt", "--werkzeuge", "lesen,schreiben", "--text", "x")
        self.assertEqual(erg.returncode, 2)
        self.assertIn("--schreibend", erg.stderr)

    def test_nachfrage_bleibt_im_projekt(self):
        self._lauf_in(self.projekt, "run", "--konto", "tk", "--projekt", "--text", "Erste Frage")
        erg = self._lauf_in(Path(self.tmp.name), "run", "--fortsetzen", "--text", "Zweite Frage")
        self.assertEqual(erg.returncode, 0, erg.stderr)
        cwds = (self.bin / "cwd.log").read_text().split()
        self.assertEqual(cwds[0], cwds[1])  # Nachfrage läuft im selben Projekt, nicht im aktuellen Verzeichnis

    def test_codex_sandbox_im_projekt_read_only(self):
        from omni_agent.runner.codex import CodexRunner
        from omni_agent.anbieter import hole_anbieter
        projekt, ordner = Path("/tmp/projekt"), Path("/tmp/lauf")
        ctx = LaufKontext(prompt="p", ordner=ordner, anbieter=hole_anbieter("codex"), modell="gpt-6.1-sol", base_url=None,
                          protokoll="openai-responses", schluessel={}, werkzeuge=("lesen",), max_runden=5, projekt=projekt)
        argv = CodexRunner().baue(ctx).argv
        self.assertEqual(argv[argv.index("--sandbox") + 1], "read-only")
        self.assertEqual(argv[argv.index("--cd") + 1], str(projekt))
        ctx.schreibend = True
        argv = CodexRunner().baue(ctx).argv
        self.assertEqual(argv[argv.index("--sandbox") + 1], "workspace-write")


class ReviewGate(Farm):
    def setUp(self):
        super().setUp()
        self.env["OMNI_AGENT_KONTO_TK"] = FAKE_KEY
        self.assertEqual(self.lauf("konto", "add", "tk", "--art", "api").returncode, 0)
        self.assertEqual(self.lauf("konto", "standard", "tk").returncode, 0)
        self.repo, self.git = self._repo()

    def _stopp(self, modus="allow", **eingabe):
        (self.bin / "modus").write_text(modus)
        daten = {"session_id": "s1", "cwd": str(self.repo), "last_assistant_message": "Habe m.py geändert", **eingabe}
        return subprocess.run([sys.executable, str(BIN), "hook", "stopp"], env=dict(self.env), input=json.dumps(daten),
                              capture_output=True, text=True, timeout=60)

    def _gate(self, an=True):
        self.assertEqual(self.lauf("setup", "--review-gate", "an" if an else "aus").returncode in (0, 2), True)

    def test_aus_ist_standard_und_laesst_still_durch(self):
        (self.repo / "m.py").write_text("a = 2\n")
        erg = self._stopp()
        self.assertEqual((erg.returncode, erg.stdout.strip()), (0, ""))
        self.assertFalse((self.home / "laeufe").exists())

    def test_an_ohne_aenderungen_ruft_kein_modell(self):
        self._gate()
        erg = self._stopp()
        self.assertEqual((erg.returncode, erg.stdout.strip()), (0, ""))
        self.assertFalse((self.home / "laeufe").exists())

    def test_block_dann_gleicher_stand_wird_nicht_erneut_blockiert(self):
        self._gate()
        (self.repo / "m.py").write_text("a = 2\n")
        erste = self._stopp("block")
        self.assertEqual(erste.returncode, 0, erste.stderr)
        entscheidung = json.loads(erste.stdout)
        self.assertEqual(entscheidung["decision"], "block")
        self.assertIn("Datei m.py Zeile 1 ist kaputt", entscheidung["reason"])
        zweite = self._stopp("block")  # gleicher Diff: kein zweites Mal blockieren, kein zweiter Lauf
        self.assertEqual(zweite.stdout.strip(), "")
        self.assertEqual(len(list((self.home / "laeufe").iterdir())), 1)
        (self.repo / "m.py").write_text("a = 3\n")  # geänderter Diff: wieder prüfen
        dritte = self._stopp("block")
        self.assertEqual(json.loads(dritte.stdout)["decision"], "block")

    def test_allow_laesst_durch_und_gibt_diff_und_antwort_als_material(self):
        self._gate()
        (self.repo / "m.py").write_text("a = 2\n")
        erg = self._stopp("allow")
        self.assertEqual((erg.returncode, erg.stdout.strip()), (0, ""))
        ordner = sorted((self.home / "laeufe").iterdir())[-1]
        self.assertTrue(ordner.name.endswith("-gate"))
        self.assertIn("+a = 2", (ordner / "aenderungen.patch").read_text())
        self.assertIn("Habe m.py geändert", (ordner / "letzte_antwort.md").read_text())
        self.assertEqual(json.loads((ordner / "status.json").read_text())["art"], "gate")

    def test_geheimnis_im_diff_ueberspringt_das_gate(self):
        self._gate()
        (self.repo / "k.py").write_text('API_KEY = "sk-ant-api03-abcdefghijklmnopqrstuvwxyz0123456789ABCDEFG"\n')
        self.git("add", "-N", "k.py")
        erg = self._stopp("block")
        self.assertEqual(erg.stdout.strip(), "")
        self.assertIn("übersprungen", erg.stderr)
        self.assertFalse((self.home / "laeufe").exists())

    def test_gate_im_lauf_tut_nichts(self):
        self._gate()
        (self.repo / "m.py").write_text("a = 2\n")
        self.env["OMNI_AGENT_LAUF"] = "1"
        self.assertEqual(self._stopp("block").stdout.strip(), "")

    def test_anschalten_braucht_standardkonto(self):
        self.assertEqual(self.lauf("konto", "standard", "--loeschen").returncode, 0)
        self.assertEqual(self.lauf("setup", "--review-gate", "an").returncode, 2)

    def test_stopp_weist_auf_laufende_laeufe_hin(self):
        (self.bin / "modus").write_text("haengt")
        env = dict(self.env, OMNI_AGENT_SITZUNG="s1")
        subprocess.run([sys.executable, str(BIN), "run", "--hintergrund", "--text", "x", "--konto", "tk", "--zeit", "60"],
                       env=env, capture_output=True, text=True, timeout=30)
        try:
            erg = self._stopp()
            self.assertIn("arbeiten noch", erg.stderr)
        finally:
            subprocess.run([sys.executable, str(BIN), "cancel"], env=env, capture_output=True, text=True, timeout=60)


class ReviewVertrag(Farm):
    def test_auftrag_hat_festes_berichtsgeruest(self):
        repo, _ = self._repo()
        (repo / "m.py").write_text("a = 2\n")
        self.assertEqual(self._review(repo, "--anbieter", "deepseek").returncode, 0)
        auftrag = (self.letzter_lauf() / "auftrag.md").read_text()
        for marke in ("## Urteil", "freigeben", "nacharbeiten", "## Befunde", "### [kritisch|hoch|mittel|niedrig]", "Sicherheit:", "## Nächste Schritte"):
            self.assertIn(marke, auftrag)
        self.assertNotIn("gegnerisch", auftrag.split("<befundlatte>")[0])  # ohne --adversarial keine Haltung

    def test_gegnerisch_ergaenzt_haltung_und_angriffsflaeche(self):
        repo, _ = self._repo()
        (repo / "m.py").write_text("a = 2\n")
        self._review(repo, "--anbieter", "deepseek", "--adversarial")
        auftrag = (self.letzter_lauf() / "auftrag.md").read_text()
        self.assertIn("<haltung>", auftrag)
        self.assertIn("<angriffsflaeche>", auftrag)

    def test_sauberer_baum_prueft_den_branch_gegen_den_hauptzweig(self):
        repo, git = self._repo()
        git("branch", "-M", "main")
        git("checkout", "-qb", "feature")
        (repo / "m.py").write_text("a = 99\n")
        git("commit", "-qam", "feature")
        erg = self._review(repo, "--anbieter", "deepseek")
        self.assertEqual(erg.returncode, 0, erg.stderr)
        self.assertIn("Branch gegen main", erg.stdout)
        self.assertIn("+a = 99", (self.letzter_lauf() / "aenderungen.patch").read_text())

    def test_review_hintergrund_vorschau_startet_nichts(self):
        repo, _ = self._repo()
        (repo / "m.py").write_text("a = 2\n")
        erg = self._review(repo, "--anbieter", "deepseek", "--hintergrund", "--vorschau")
        self.assertEqual(erg.returncode, 0, erg.stderr)
        self.assertIn("nichts gesendet", erg.stdout)
        self.assertFalse((self.home / "laeufe").exists())


if __name__ == "__main__":
    unittest.main()
