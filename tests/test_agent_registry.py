"""Real registry paths are populated only when we have documented SKILL.md roots."""
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from argparse import Namespace

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "skill-hub" / "scripts"))
import agent_registry as r
import skill_hub as hub
import share_engine as engine

class RegistryTests(unittest.TestCase):
    def test_all_entries_including_deepseek_harness(self):
        self.assertEqual(len(r.CATALOG), 34)
        self.assertEqual(len(r.BY_ID), len(r.CATALOG))
        self.assertIn("deepseek-harness", r.BY_ID)
        self.assertEqual(r.BY_ID["deepseek-harness"].target, ".dsh/skills")
        self.assertIsNone(r.BY_ID["grok-bot"].target)
        self.assertNotIn("grok-bot", engine.base_targets())

    def test_environment_home_respected(self):
        with patch.dict("os.environ", {"DSH_HOME": "/tmp/dsh-hub-test"}):
            self.assertEqual(r.expand_root(".dsh/skills", id="deepseek-harness"), Path("/tmp/dsh-hub-test/skills"))

    def test_configured_manual_root_detected_without_unsafe_default(self):
        with tempfile.TemporaryDirectory() as temp:
            t = Path(temp)
            home = t / "home"
            home.mkdir()
            source = t / "grok" / "skills"
            skill = source / "one"
            skill.mkdir(parents=True)
            (skill / "SKILL.md").write_text("---\nname: one\ndescription: sample\n---\n", encoding="utf-8")
            # Isolate HOME so real skills installed on the developer's machine
            # are never scanned by the test.
            with patch.object(r.Path, "home", return_value=home):
                plan = hub.scan(Namespace(out=str(t / "lib"), project=None, extra_root=[], agent_paths={"grok-bot": str(source)}))
                self.assertEqual(len(plan["skills"]), 1)
                self.assertEqual(engine.source_agent(plan["skills"][0]["source"], []), "grok-bot")
                self.assertEqual(engine.target_roots([], configured={"grok-bot": str(source)})["grok-bot"], source)
                self.assertNotIn("grok-bot", engine.target_roots([]))

if __name__ == "__main__":
    unittest.main()
