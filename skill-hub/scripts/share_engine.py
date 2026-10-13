#!/usr/bin/env python3
"""Policy engine for Agent Skill Hub GUI (safe preview before changes)."""
from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

import skill_hub as hub
import agent_registry as registry

AGENT_NAMES = {entry.id: entry.name for entry in registry.CATALOG}


def base_targets(home: Path | None = None) -> dict[str, Path]:
    """Only documented installation roots. Manual-only Agents have no automatic target."""
    return registry.targets(home)


def settings_path() -> Path:
    home = Path(os.environ.get("LOCALAPPDATA") or (Path.home() / ".agent-skill-hub"))
    return home / "AgentSkillHub" / "settings.json" if os.environ.get("LOCALAPPDATA") else home / "settings.json"


def load_settings(path: Path | None = None) -> dict:
    path = path or settings_path()
    if not path.exists():
        return {"policies": {}, "custom_agents": [], "managed_links": {}, "library": str(hub.default_output()), "project": "", "agent_paths": {}}
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("Invalid JSON settings")
    for key, default in {"policies": {}, "custom_agents": [], "managed_links": {}, "library": str(hub.default_output()), "project": "", "agent_paths": {}}.items():
        data.setdefault(key, default)
    if not isinstance(data["policies"], dict) or not isinstance(data["managed_links"], dict) or not isinstance(data["agent_paths"], dict):
        raise ValueError("Invalid policy or ledger")
    return data


def save_settings(data: dict, path: Path | None = None) -> None:
    path = path or settings_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmpname = tempfile.mkstemp(prefix="settings-", suffix=".tmp", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        os.replace(tmpname, path)
    finally:
        if os.path.exists(tmpname):
            os.unlink(tmpname)


def source_agent(source: str, custom_agents: list[dict]) -> str:
    if source.startswith("agent::") or source.startswith("project-agent::") or source.startswith("configured::"):
        return source.split("::")[1]
    # Legacy v0.2 naming preserved for older reports/tests.
    if source.startswith("Codex") or source in {"project / Codex", "project / shared"}:
        return "codex"
    if source.startswith("Claude") or source == "project / Claude":
        return "claude"
    if source.startswith("Cursor") or source == "project / Cursor":
        return "cursor"
    if source.startswith("Gemini") or source == "project / Gemini":
        return "gemini"
    if source.startswith("OpenCode") or source == "project / OpenCode":
        return "opencode"
    if source.startswith("custom-"):
        try:
            index = int(source.split("-")[1]) - 1
            return str(custom_agents[index]["id"])
        except (IndexError, KeyError, ValueError):
            return "unknown"
    return "unknown"


def target_roots(custom_agents: list[dict], home: Path | None = None,
                 configured: dict[str, str] | None = None) -> dict[str, Path]:
    roots = base_targets(home)
    for id_, value in (configured or {}).items():
        if id_ in registry.BY_ID and isinstance(value, str) and value.strip():
            roots[id_] = Path(value).expanduser()
    for entry in custom_agents:
        roots[str(entry["id"])] = Path(entry["path"]).expanduser()
    return roots


def key_for_skill(skill: dict) -> str:
    return os.path.normcase(str(hub.canonical(Path(skill["folder"]))))


def management_key(agent: str, name: str) -> str:
    return f"{agent}::{name}"


def _safe_link(root: Path, library: Path) -> bool:
    a, b = hub.canonical(root), hub.canonical(library)
    return a != b and not hub.below(a, b) and not hub.below(b, a)


def make_plan(scan_result: dict, settings: dict, target_paths: dict[str, Path]) -> dict:
    """Create immutable preview. A failed collision blocks only that skill."""
    library = hub.canonical(Path(settings["library"]))
    policies = settings.get("policies", {})
    managed = settings.get("managed_links", {})
    available = {key_for_skill(s) for s in scan_result["skills"]}
    selected: dict[str, list[dict]] = {}
    for skill in scan_result["skills"]:
        policy = policies.get(key_for_skill(skill), {})
        if policy.get("enabled"):
            selected.setdefault(skill["name"], []).append(skill)
    operations: list[dict] = []
    conflicts: list[str] = []
    desired_links: set[str] = set()
    desired_paths: set[str] = set()
    for name, copies in sorted(selected.items()):
        versions = {s["sha256"] for s in copies}
        if len(versions) > 1:
            conflicts.append(f"{name}: selected source Skills have different contents; choose only one version")
            continue
        s = copies[0]
        dst = library / name
        merge_status = "would-copy"
        if dst.exists() or hub.is_link(dst):
            try:
                current, _, _ = hub.inventory(dst)
                merge_status = "already-present" if current == s["sha256"] else "destination-conflict"
            except (OSError, ValueError):
                merge_status = "destination-unsafe"
        operations.append({"kind": "merge", "name": name, "source": s["folder"],
                           "source_sha": s["sha256"], "target": str(dst), "status": merge_status})
        blocked = merge_status in {"destination-conflict", "destination-unsafe"}
        if blocked:
            conflicts.append(f"{name}: existing shared-library version differs or is unsafe")
        recipients = set()
        for copy in copies:
            recipients.update(policies.get(key_for_skill(copy), {}).get("targets", []))
        for agent in sorted(recipients):
            if agent not in target_paths:
                conflicts.append(f"{name}: unknown target agent {agent}")
                continue
            root = Path(target_paths[agent])
            if not _safe_link(root, library):
                conflicts.append(f"{name}: sharing library overlaps {agent} target directory")
                continue
            key = management_key(agent, name)
            desired_links.add(key)
            dest = root / name
            desired_paths.add(os.path.normcase(str(hub.canonical(dest))))
            if blocked:
                status = "blocked-library-conflict"
            elif dest.exists() or hub.is_link(dest):
                status = "already-linked" if hub.is_link(dest) and hub.canonical(dest) == hub.canonical(dst) else "target-name-taken"
            else:
                status = "would-link"
            operations.append({"kind": "link", "name": name, "agent": agent, "source": s["folder"],
                               "target": str(dest), "library_skill": str(dst), "status": status})
    # Remove only links previously *created by this GUI*, and only after the
    # originating source was successfully rescanned. Never delete library copies.
    for key, record in sorted(managed.items()):
        if key in desired_links or record.get("source") not in available:
            continue
        path = Path(record["target"])
        # Other agent aliases can point to the same physical Skills root.
        # Never revoke a link that is still desired at that exact destination.
        if os.path.normcase(str(hub.canonical(path))) in desired_paths:
            continue
        linked_to = Path(record["library_skill"])
        status = "would-unlink" if hub.is_link(path) and hub.canonical(path) == hub.canonical(linked_to) else "changed-or-already-removed"
        operations.append({"kind": "unlink", "agent": record.get("agent"),
                           "name": record.get("name"), "target": str(path),
                           "library_skill": str(linked_to), "source": record.get("source"), "status": status,
                           "managed_key": key})
    return {"operations": operations, "conflicts": conflicts,
            "selected_skills": len(selected), "library": str(library)}


def apply_plan(preview: dict, settings: dict, rescan: dict, targets: dict[str, Path]) -> list[dict]:
    """Re-check file hashes and path collisions at apply time, then execute."""
    if preview["conflicts"]:
        raise ValueError("Resolve all conflicts before applying: " + "; ".join(preview["conflicts"]))
    fresh = make_plan(rescan, settings, targets)
    if fresh != preview:
        raise ValueError("The scan or sharing plan has changed; refresh the preview")
    available = {key_for_skill(s): s for s in rescan["skills"]}
    statuses: dict[str, str] = {}
    log: list[dict] = []
    library = Path(preview["library"])
    for item in preview["operations"]:
        if item["kind"] != "merge":
            continue
        original = available.get(key_for_skill({"folder": item["source"]}))
        if not original or original["sha256"] != item["source_sha"]:
            statuses[item["name"]] = "failed-source-changed"
            log.append({**item, "status": "failed-source-changed"})
            continue
        skill = hub.Skill(item["name"], original["source"], Path(original["folder"]), original["sha256"], original["files"], original["bytes"])
        result = hub.merge({"unique": [skill]}, library, True)[0]
        statuses[item["name"]] = result["action"]
        log.append({**item, "status": result["action"]})
    managed = settings.setdefault("managed_links", {})
    for item in preview["operations"]:
        if item["kind"] == "merge":
            continue
        dest = Path(item["target"])
        src = Path(item["library_skill"])
        if item["kind"] == "link":
            if statuses.get(item["name"]) not in {"already-present", "copied"}:
                status = "skipped-library-not-ready"
            elif dest.exists() or hub.is_link(dest):
                status = "already-linked" if hub.is_link(dest) and hub.canonical(dest) == hub.canonical(src) else "target-name-taken"
            elif not _safe_link(dest.parent, library):
                status = "unsafe-target"
            else:
                try:
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    hub.link_target(src, dest)
                    status = "linked"
                    managed[management_key(item["agent"], item["name"])] = {
                        "agent": item["agent"], "name": item["name"], "source": key_for_skill({"folder": item["source"]}),
                        "target": str(dest), "library_skill": str(src)
                    }
                except Exception as exc:
                    status = f"failed: {exc}"
            log.append({**item, "status": status})
        if item["kind"] == "unlink":
            if not hub.is_link(dest) or hub.canonical(dest) != hub.canonical(src):
                status = "skipped-changed-link"
            else:
                try:
                    # Junctions are directory entries on Windows; remove ONLY the
                    # junction itself, never the target contents.
                    if os.name == "nt" and not dest.is_symlink():
                        dest.rmdir()
                    else:
                        dest.unlink()
                    status = "unlinked"
                    managed.pop(item["managed_key"], None)
                except OSError as exc:
                    status = f"failed: {exc}"
            log.append({**item, "status": status})
    return log
