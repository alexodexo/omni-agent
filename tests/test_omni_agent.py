"""Tests für den Omni-Agent-Kern. Nur Standardbibliothek: python3 -m unittest discover -s tests -v

Kein Test spricht mit einem echten Anbieter. Der Ende-zu-Ende-Test nutzt ein vorgetäuschtes `claude`.
"""
import json
import os
import stat
import subprocess
import sys
import tempfile
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

    def test_codex_verlangt_shell_ausdruecklich(self):
        with self.assertRaises(KonfigFehler) as ctx:
            loese_werkzeuge(None, RUNNER["codex"])
        self.assertIn("+shell", str(ctx.exception))
        w = loese_werkzeuge("+shell", RUNNER["codex"])
        self.assertIn("shell", w)
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
        for flag in ("--strict-mcp-config", "--no-session-persistence", "--allowed-tools"):
            self.assertIn(flag, argv)
        self.assertEqual(argv[argv.index("--setting-sources") + 1], "project")
        self.assertEqual(argv[argv.index("--permission-mode") + 1], "dontAsk")
        self.assertNotIn("Bash", argv)

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


class Plugin(unittest.TestCase):
    def test_version_in_plugin_json_gleich_kern(self):
        from omni_agent import VERSION
        manifest = json.loads((WURZEL / ".claude-plugin" / "plugin.json").read_text())
        self.assertEqual(manifest["version"], VERSION)

    def test_skills_haben_beschreibung(self):
        for ordner in sorted((WURZEL / "skills").iterdir()):
            kopf = (ordner / "SKILL.md").read_text().split("---")[1]
            self.assertIn("description:", kopf, ordner.name)

    def test_run_skill_ist_fuer_claude_aufrufbar_aber_nur_auf_ausdruecklichen_wunsch(self):
        # Sonst scheitert /goal: ein gesperrter Skill kann von Claude nicht selbst gerufen werden.
        kopf = (WURZEL / "skills" / "run" / "SKILL.md").read_text().split("---")[1]
        self.assertNotIn("disable-model-invocation", kopf)
        self.assertIn("ausdrücklich", kopf)


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
    print(json.dumps({"type": "system", "subtype": "init", "model": os.environ.get("ANTHROPIC_MODEL")}), flush=True)
    print(json.dumps({"type": "assistant", "message": {"content": [{"type": "tool_use", "name": "WebSearch", "input": {"query": "test"}}]}}), flush=True)
    print("Zeile mit Geheimnis: " + os.environ.get("ANTHROPIC_AUTH_TOKEN", ""), flush=True)
    sys.stderr.write("stderr mit Geheimnis: " + os.environ.get("ANTHROPIC_AUTH_TOKEN", "") + "\\n")
    if modus == "haengt":
        time.sleep(60)
    if modus == "ok":
        open("bericht.md", "w").write("# Bericht\\nFertig\\n")
    print(json.dumps({"type": "result", "subtype": "success", "num_turns": 1, "duration_ms": 10, "total_cost_usd": 0, "result": "ok"}), flush=True)
""")


class EndeZuEnde(MitHome):
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


if __name__ == "__main__":
    unittest.main()
