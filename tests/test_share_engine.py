import tempfile
import unittest
from argparse import Namespace
from pathlib import Path
from unittest.mock import patch
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "skill-hub" / "scripts"))
import skill_hub as hub
import share_engine as engine


def make_skill(folder: Path, name: str, body: str = "hello") -> Path:
    dest = folder / name
    dest.mkdir(parents=True, exist_ok=True)
    (dest / "SKILL.md").write_text(
        f"---\nname: {name}\ndescription: reusable skill\n---\n# {body}\n", encoding="utf-8")
    return dest


class ShareEngineTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)
        self.codex = self.base / "codex-src"
        self.claude = self.base / "claude-src"
        self.library = self.base / "library" / "skills"
        self.claude_target = self.base / "claude-target"
        self.cursor_target = self.base / "cursor-target"
        self.codex.mkdir()
        self.claude.mkdir()
        self.paths = {"claude": self.claude_target, "cursor": self.cursor_target}
        self.cfg = {"policies": {}, "custom_agents": [], "managed_links": {},
                    "library": str(self.library), "project": ""}
        self.root_mock = patch.object(hub, "known_roots", return_value=[("Codex / shared", self.codex), ("Claude Code", self.claude)])
        self.root_mock.start()
        self.addCleanup(self.root_mock.stop)

    def scan(self):
        return hub.scan(Namespace(out=str(self.library), project=None, extra_root=[]))

    def select(self, scanned, agent_names):
        for x in scanned["skills"]:
            if x["name"] in agent_names:
                self.cfg["policies"][engine.key_for_skill(x)] = {"enabled": True, "targets": agent_names[x["name"]]}

    def test_selective_share_and_safe_revoke(self):
        original = make_skill(self.codex, "fpga-test")
        scanned = self.scan()
        self.select(scanned, {"fpga-test": ["claude"]})
        preview = engine.make_plan(scanned, self.cfg, self.paths)
        self.assertEqual([x["status"] for x in preview["operations"]], ["would-copy", "would-link"])
        result = engine.apply_plan(preview, self.cfg, scanned, self.paths)
        self.assertEqual([x["status"] for x in result], ["copied", "linked"])
        link = self.claude_target / "fpga-test"
        # Windows installs directory junctions (mklink /J), which is_symlink()
        # does not recognize; the engine's own is_link() covers both.
        self.assertTrue(hub.is_link(link))
        self.assertFalse((self.cursor_target / "fpga-test").exists())
        self.assertTrue((original / "SKILL.md").is_file())
        self.cfg["policies"][engine.key_for_skill(scanned["skills"][0])]["enabled"] = False
        updated = engine.make_plan(scanned, self.cfg, self.paths)
        self.assertEqual([x["status"] for x in updated["operations"]], ["would-unlink"])
        result = engine.apply_plan(updated, self.cfg, scanned, self.paths)
        self.assertEqual(result[0]["status"], "unlinked")
        self.assertFalse(link.exists())
        self.assertTrue((self.library / "fpga-test" / "SKILL.md").exists())
        self.assertTrue((original / "SKILL.md").exists())

    def test_conflicting_versions_block_all(self):
        make_skill(self.codex, "same", "one")
        make_skill(self.claude, "same", "different")
        scanned = self.scan()
        self.select(scanned, {"same": ["cursor"]})
        preview = engine.make_plan(scanned, self.cfg, self.paths)
        self.assertTrue(preview["conflicts"])
        with self.assertRaises(ValueError):
            engine.apply_plan(preview, self.cfg, scanned, self.paths)
        self.assertFalse(self.library.exists())

    def test_existing_target_preserved(self):
        make_skill(self.codex, "repeat", "source")
        make_skill(self.claude_target, "repeat", "target")
        scanned = self.scan()
        self.select(scanned, {"repeat": ["claude"]})
        preview = engine.make_plan(scanned, self.cfg, self.paths)
        self.assertEqual(preview["operations"][1]["status"], "target-name-taken")
        result = engine.apply_plan(preview, self.cfg, scanned, self.paths)
        self.assertEqual(result[1]["status"], "target-name-taken")
        self.assertIn("target", (self.claude_target / "repeat" / "SKILL.md").read_text())
        self.assertFalse(self.cfg["managed_links"])

    def test_same_versions_union_recipients(self):
        make_skill(self.codex, "shared")
        make_skill(self.claude, "shared")
        scanned = self.scan()
        self.cfg["policies"][engine.key_for_skill(scanned["skills"][0])] = {"enabled": True, "targets": ["claude"]}
        self.cfg["policies"][engine.key_for_skill(scanned["skills"][1])] = {"enabled": True, "targets": ["cursor"]}
        preview = engine.make_plan(scanned, self.cfg, self.paths)
        self.assertFalse(preview["conflicts"])
        self.assertEqual(len(preview["operations"]), 3)
        self.assertEqual({x["agent"] for x in preview["operations"] if x["kind"] == "link"}, {"claude", "cursor"})

    def test_existing_shared_library_conflict(self):
        make_skill(self.codex, "collision", "new")
        make_skill(self.library, "collision", "old")
        scanned = self.scan()
        self.select(scanned, {"collision": ["claude"]})
        preview = engine.make_plan(scanned, self.cfg, self.paths)
        self.assertTrue(preview["conflicts"])
        self.assertEqual(preview["operations"][0]["status"], "destination-conflict")

    def test_modified_link_never_unlinked(self):
        make_skill(self.codex, "safe")
        scanned = self.scan()
        self.select(scanned, {"safe": ["claude"]})
        p = engine.make_plan(scanned, self.cfg, self.paths)
        engine.apply_plan(p, self.cfg, scanned, self.paths)
        link = self.claude_target / "safe"
        link.unlink()
        real = make_skill(self.claude_target, "safe", "do not remove")
        self.cfg["policies"][engine.key_for_skill(scanned["skills"][0])]["enabled"] = False
        p = engine.make_plan(scanned, self.cfg, self.paths)
        self.assertEqual(p["operations"][0]["status"], "changed-or-already-removed")
        outcome = engine.apply_plan(p, self.cfg, scanned, self.paths)
        self.assertEqual(outcome[0]["status"], "skipped-changed-link")
        self.assertTrue(real.exists())


if __name__ == "__main__":
    unittest.main()
