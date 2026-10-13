import tempfile
import unittest
from argparse import Namespace
from pathlib import Path
from unittest.mock import patch
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "skill-hub" / "scripts"))
import skill_hub as hub


def create_skill(base, name, body="hello", extra=None):
    path = base / name
    path.mkdir(parents=True, exist_ok=True)
    (path / "SKILL.md").write_text(f"---\nname: {name}\ndescription: does something useful\n---\n# {body}\n", encoding="utf-8")
    if extra:
        (path / "scripts").mkdir()
        (path / "scripts" / "run.py").write_text(extra, encoding="utf-8")
    return path


class HubTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.base = Path(self.tmp.name)
        self.codex = self.base / "codex"
        self.claude = self.base / "claude"
        self.codex.mkdir()
        self.claude.mkdir()
        self.out = self.base / "shared" / "skills"
        self.roots = [("codex", self.codex), ("claude", self.claude)]
        self.patch = patch.object(hub, "known_roots", return_value=self.roots)
        self.patch.start()

    def tearDown(self):
        self.patch.stop()
        self.tmp.cleanup()

    def args(self):
        return Namespace(out=str(self.out), project=None, extra_root=[])

    def test_scan_deduplicate_and_copy(self):
        create_skill(self.codex, "hello", "same")
        create_skill(self.claude, "hello", "same")
        create_skill(self.claude, "other", "another")
        report = hub.scan(self.args())
        self.assertEqual(len(report["unique"]), 2)
        self.assertEqual(len(report["duplicates"]), 1)
        self.assertEqual(len(report["conflicts"]), 0)
        preview = hub.merge(report, self.out, False)
        self.assertTrue(all(a["action"] == "would-copy" for a in preview))
        self.assertFalse(self.out.exists())
        applied = hub.merge(report, self.out, True)
        self.assertTrue(all(a["action"] == "copied" for a in applied))
        self.assertTrue((self.out / "hello" / "SKILL.md").exists())
        self.assertTrue(all(a["action"] == "already-present" for a in hub.merge(report, self.out, True)))

    def test_conflicts_do_not_copy(self):
        create_skill(self.codex, "hello", "one")
        create_skill(self.claude, "hello", "two")
        report = hub.scan(self.args())
        self.assertEqual(len(report["conflicts"]), 1)
        self.assertEqual(hub.merge(report, self.out, True), [])
        self.assertFalse(self.out.exists())

    def test_never_overwrite(self):
        create_skill(self.codex, "hello", "one")
        create_skill(self.out, "hello", "different")
        report = hub.scan(self.args())
        actions = hub.merge(report, self.out, True)
        self.assertEqual(actions[0]["action"], "existing-destination-conflict")
        self.assertIn("different", (self.out / "hello" / "SKILL.md").read_text(encoding="utf-8"))

    def test_secret_and_link_rejection(self):
        a = create_skill(self.codex, "secret-skill")
        (a / ".env").write_text("TOKEN=x")
        report = hub.scan(self.args())
        self.assertFalse(report["unique"])
        self.assertTrue(any("secret" in e["reason"] for e in report["errors"]))

    def test_missing_header_skipped(self):
        p = self.codex / "bad-skill"
        p.mkdir()
        (p / "SKILL.md").write_text("# no header")
        self.assertEqual(len(hub.scan(self.args())["errors"]), 1)

    def test_link_dry_run_and_preserve_original(self):
        create_skill(self.out, "hello")
        create_skill(self.claude, "hello", "customized")
        with patch.object(hub.Path, "home", return_value=self.base):
            actions = hub.link(self.out, ["claude"], False)
            self.assertEqual(actions[0]["action"], "would-link")
            self.assertFalse((self.base / ".claude/skills/hello").exists())
            actions = hub.link(self.out, ["claude"], True)
            self.assertEqual(actions[0]["action"], "linked")
            # Windows creates directory junctions; hub.is_link() covers both
            # junctions and POSIX symlinks.
            self.assertTrue(hub.is_link(self.base / ".claude/skills/hello"))
            self.assertIn("customized", (self.claude / "hello/SKILL.md").read_text())


if __name__ == "__main__":
    unittest.main()
