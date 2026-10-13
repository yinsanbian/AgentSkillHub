"""Headless UI model tests — no display or filesystem writes required."""
import sys
import tempfile
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'skill-hub' / 'scripts'))
import gui_logic as logic
import share_engine as engine


class InterfaceLogicTests(unittest.TestCase):
    def test_search_status_and_conflict_filter(self):
        rows = [
            {'name': 'fpga-verification', 'source': 'Codex', 'enabled': True},
            {'name': 'rk3568-deploy', 'source': 'Claude', 'enabled': False},
            {'name': 'link-only', 'source': 'installed', 'managed': True, 'enabled': False},
        ]
        self.assertEqual([x['name'] for x in logic.visible_rows(rows, 'fpga')], ['fpga-verification'])
        self.assertEqual([x['name'] for x in logic.visible_rows(rows, mode='shared')], ['fpga-verification'])
        self.assertEqual([x['name'] for x in logic.visible_rows(rows, mode='private')], ['rk3568-deploy'])
        self.assertEqual([x['name'] for x in logic.visible_rows(rows, mode='conflict', conflicts={'rk3568-deploy'})], ['rk3568-deploy'])

    def test_bulk_policy_is_draft_and_ignores_managed_links(self):
        with tempfile.TemporaryDirectory() as t:
            root = Path(t)
            items = [{'name': 'one', 'folder': str(root/'one')},
                     {'name': 'two', 'folder': str(root/'two')},
                     {'name': 'linked', 'folder': str(root/'linked'), 'managed': True}]
            cfg = {'policies': {}}
            n = logic.change_policies(cfg, items, enabled=True, targets=['claude', 'cursor', 'claude'])
            self.assertEqual(n, 2)
            self.assertEqual(len(cfg['policies']), 2)
            self.assertEqual(cfg['policies'][engine.key_for_skill(items[0])]['targets'], ['claude', 'cursor'])
            n = logic.change_policies(cfg, items[:1], enabled=False)
            self.assertEqual(n, 1)
            self.assertEqual(cfg['policies'][engine.key_for_skill(items[0])], {'enabled': False, 'targets': []})

    def test_preview_counts(self):
        x = {'operations': [{'status': 'would-copy'}, {'status': 'would-link'},
                            {'status': 'would-link'}, {'status': 'would-unlink'}, {'status': 'already-present'}],
             'conflicts': ['test']}
        self.assertEqual(logic.describe_changes(x), {'copy': 1, 'link': 2, 'unlink': 1, 'blocked': 1})


if __name__ == '__main__':
    unittest.main()
