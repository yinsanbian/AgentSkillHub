"""Pure selection/filter/policy operations used by v0.4 GUI; easy to test headlessly."""
from __future__ import annotations
from copy import deepcopy
from typing import Iterable
import share_engine as engine


def visible_rows(rows: list[dict], query: str = '', mode: str = 'all', conflicts: set[str] | None = None) -> list[dict]:
    q = query.strip().casefold()
    conflicts = conflicts or set()
    def keep(row):
        found = q in row.get('name', '').casefold() or q in row.get('source', '').casefold()
        if not found:
            return False
        if mode == 'shared':
            return bool(row.get('enabled'))
        if mode == 'private':
            return not bool(row.get('enabled')) and not bool(row.get('managed'))
        if mode == 'conflict':
            return row.get('name') in conflicts
        return True
    return [r for r in rows if keep(r)]


def change_policies(config: dict, skills: Iterable[dict], *, enabled: bool, targets: Iterable[str] | None = None) -> int:
    """Stage the same change to multiple skills without touching source files."""
    selected = [x for x in skills if not x.get('managed')]
    unique_targets = list(dict.fromkeys(targets or [])) if enabled else []
    count = 0
    for item in selected:
        key = engine.key_for_skill(item)
        previous = config.setdefault('policies', {}).get(key, {})
        new_targets = unique_targets if targets is not None else (previous.get('targets', []) if enabled else [])
        new = {'enabled': enabled, 'targets': list(new_targets)}
        if previous != new:
            config['policies'][key] = new
            count += 1
    return count


def describe_changes(preview: dict) -> dict:
    operations = preview.get('operations', [])
    return {
        'copy': sum(x['status'] == 'would-copy' for x in operations),
        'link': sum(x['status'] == 'would-link' for x in operations),
        'unlink': sum(x['status'] == 'would-unlink' for x in operations),
        'blocked': len(preview.get('conflicts', [])),
    }
