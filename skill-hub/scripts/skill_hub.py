#!/usr/bin/env python3
"""Skill Hub: safe local Agent Skills discovery, collection, and links.

Python >= 3.10, standard library only. No network, no skill execution.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import stat
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import agent_registry as registry

NAME_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
META_RE = re.compile(r"^([a-zA-Z][a-zA-Z0-9_-]*):\s*(.*)$")
DENY_FILES = {".env", ".env.local", ".env.production", ".npmrc", "id_rsa", "id_ed25519", "credentials.json", "secrets.json", "token.json"}
DENY_FOLDERS = {".git", "__pycache__", ".venv", "venv", "node_modules"}
MAX_BYTES = 50 * 1024 * 1024
MAX_FILES = 2000
MAX_DEPTH = 8

@dataclass
class Skill:
    name: str
    source: str
    folder: Path
    fingerprint: str
    files: int
    size: int

    def as_dict(self):
        return {"name": self.name, "source": self.source, "folder": str(self.folder),
                "sha256": self.fingerprint, "files": self.files, "bytes": self.size}


def canonical(path: Path) -> Path:
    return path.expanduser().resolve(strict=False)


def below(candidate: Path, parent: Path) -> bool:
    try:
        candidate.relative_to(parent)
        return True
    except ValueError:
        return False


def is_link(path: Path) -> bool:
    try:
        if path.is_symlink() or bool(getattr(path, "is_junction", lambda: False)()):
            return True
        if os.name == "nt" and path.exists():
            flags = getattr(path.lstat(), "st_file_attributes", 0)
            return bool(flags & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400))
        return False
    except OSError:
        return True


def default_output() -> Path:
    if os.name == "nt" and Path("D:/").exists():
        return Path("D:/AI-Skills/skills")
    return Path.home() / "AI-Skills" / "skills"


def known_roots(project: Path | None = None) -> list[tuple[str, Path]]:
    return registry.scan_roots(project)


def discover_roots(args) -> list[tuple[str, Path]]:
    items = known_roots(Path(args.project) if args.project else None)
    for i, value in enumerate(args.extra_root or []):
        items.append((f"custom-{i+1}", Path(value)))
    for id_, value in (getattr(args, "agent_paths", None) or {}).items():
        if id_ in registry.BY_ID and isinstance(value, str) and value.strip():
            items.append((f"configured::{id_}", Path(value)))
    output = canonical(Path(args.out))
    seen: set[str] = set()
    good = []
    for name, path in items:
        rp = canonical(path)
        k = os.path.normcase(str(rp))
        if k in seen or not path.is_dir() or is_link(path):
            continue
        if below(rp, output) or rp == output:
            continue
        seen.add(k)
        good.append((name, path))
    return good


def traverse(root: Path, output: Path, errors: list[dict]) -> Iterable[Path]:
    seen: set[str] = set()
    stack: list[tuple[Path, int]] = [(root, 0)]
    while stack:
        path, depth = stack.pop()
        if is_link(path):
            # Exclude previously linked skills: no recursive traversal or duplicate imports.
            continue
        real = canonical(path)
        if below(real, output):
            continue
        k = os.path.normcase(str(real))
        if k in seen:
            continue
        seen.add(k)
        if (path / "SKILL.md").is_file():
            yield path
            continue
        if depth >= MAX_DEPTH:
            continue
        try:
            subs = sorted((p for p in path.iterdir() if p.is_dir() and p.name not in DENY_FOLDERS), key=lambda p: p.name.lower())
        except (OSError, PermissionError) as exc:
            errors.append({"path": str(path), "reason": f"unreadable folder: {exc}"})
            continue
        stack.extend((p, depth + 1) for p in reversed(subs))


def skill_meta(file: Path) -> tuple[str | None, str | None]:
    try:
        with file.open("r", encoding="utf-8-sig") as f:
            head = f.read(256 * 1024)
    except (OSError, UnicodeError):
        return None, None
    lines = head.splitlines()
    if not lines or lines[0].strip() != "---":
        return None, None
    meta: dict[str, str] = {}
    for line in lines[1:]:
        if line.strip() == "---":
            return meta.get("name"), meta.get("description")
        match = META_RE.match(line)
        if match:
            v = match.group(2).strip().strip("\"'")
            meta[match.group(1)] = v
    return None, None


def inventory(folder: Path) -> tuple[str, int, int]:
    """Hash content relative paths; reject unsafe content rather than following links."""
    hash_ = hashlib.sha256()
    count = 0
    total = 0
    paths = [folder]
    files: list[Path] = []
    while paths:
        p = paths.pop()
        if is_link(p):
            raise ValueError(f"symbolic link / junction inside skill: {p}")
        if p.is_dir():
            with os.scandir(p) as it:
                entries = sorted(list(it), key=lambda x: x.name)
            for e in entries:
                child = Path(e.path)
                if e.name in DENY_FOLDERS:
                    continue
                if (e.name.lower() in DENY_FILES or e.name.lower().startswith(".env.")
                    or e.name.lower().endswith((".pem", ".pfx", ".p12"))):
                    raise ValueError(f"potential secret file in skill: {child}")
                paths.append(child)
        elif p.is_file():
            files.append(p)
            count += 1
            if count > MAX_FILES:
                raise ValueError("skill file count limit exceeded")
        else:
            raise ValueError(f"unsupported file type: {p}")
    for p in sorted(files, key=lambda x: x.relative_to(folder).as_posix()):
        rel = p.relative_to(folder).as_posix()
        hash_.update(rel.encode("utf-8"))
        hash_.update(b"\0")
        with p.open("rb") as f:
            while True:
                data = f.read(1024 * 1024)
                if not data:
                    break
                total += len(data)
                if total > MAX_BYTES:
                    raise ValueError("skill size limit exceeded (50 MiB)")
                hash_.update(data)
        hash_.update(b"\0")
    return hash_.hexdigest(), count, total


def scan(args) -> dict:
    out = canonical(Path(args.out))
    roots = discover_roots(args)
    found = []
    errors: list[dict] = []
    for source, root in roots:
        for directory in traverse(root, out, errors):
            name, desc = skill_meta(directory / "SKILL.md")
            if not name or not NAME_RE.fullmatch(name) or len(name) > 64:
                errors.append({"path": str(directory), "reason": "invalid or missing name in SKILL.md YAML header"})
                continue
            if directory.name != name:
                errors.append({"path": str(directory), "reason": f"directory name differs from skill name: {name}"})
                continue
            if not desc or desc in {"|", ">", "|-", ">-"} and not has_multiline_desc(directory / "SKILL.md"):
                errors.append({"path": str(directory), "reason": "missing description in SKILL.md"})
                continue
            try:
                fp, n, size = inventory(directory)
            except (OSError, ValueError) as exc:
                errors.append({"path": str(directory), "reason": str(exc)})
                continue
            found.append(Skill(name, source, directory, fp, n, size))
    found.sort(key=lambda s: (s.name, s.source, str(s.folder).lower()))
    groups: dict[str, list[Skill]] = {}
    for s in found:
        groups.setdefault(s.name, []).append(s)
    unique, duplicates, conflicts = [], [], []
    for name, group in sorted(groups.items()):
        versions = {s.fingerprint for s in group}
        if len(versions) > 1:
            conflicts.append({"name": name, "versions": [s.as_dict() for s in group]})
        else:
            unique.append(group[0])
            if len(group) > 1:
                duplicates.append({"name": name, "copies": [s.as_dict() for s in group]})
    return {"roots": [{"agent": n, "path": str(p)} for n,p in roots],
            "skills": [s.as_dict() for s in found],
            "unique": unique, "duplicates": duplicates,
            "conflicts": conflicts, "errors": errors}


def has_multiline_desc(file: Path) -> bool:
    try:
        t = file.read_text(encoding="utf-8-sig")[:256 * 1024]
    except (UnicodeError, OSError):
        return False
    m = re.search(r"(?m)^description:\s*[>|][-+]?\s*$\n((?:[ \t]+[^\n]*\n?)+)", t)
    return bool(m and m.group(1).strip())


def merge(plan: dict, out: Path, apply: bool) -> list[dict]:
    actions = []
    for skill in plan["unique"]:
        dst = out / skill.name
        if dst.exists() or is_link(dst):
            try:
                fp, _, _ = inventory(dst)
                status = "already-present" if fp == skill.fingerprint else "existing-destination-conflict"
            except (OSError, ValueError):
                status = "existing-destination-unreadable-or-unsafe"
            actions.append({"name": skill.name, "action": status, "destination": str(dst)})
            continue
        if apply:
            out.mkdir(parents=True, exist_ok=True)
            # Atomic publish into destination, never overwrite existing skill directories.
            tmp = Path(tempfile.mkdtemp(prefix=".skillhub-", dir=str(out)))
            try:
                shutil.copytree(skill.folder, tmp / skill.name, symlinks=True)
                copied_hash, _, _ = inventory(tmp / skill.name)
                if copied_hash != skill.fingerprint:
                    raise RuntimeError(f"source changed while copying: {skill.name}")
                if dst.exists() or is_link(dst):
                    raise RuntimeError(f"destination already appeared: {dst}")
                (tmp / skill.name).rename(dst)
                status = "copied"
            except Exception as e:
                status = f"failed: {e}"
            finally:
                shutil.rmtree(tmp, ignore_errors=True)
        else:
            status = "would-copy"
        actions.append({"name": skill.name, "action": status, "destination": str(dst), "source": str(skill.folder)})
    return actions


def link_target(target: Path, dest: Path) -> None:
    if os.name == "nt":
        cmd = ["cmd", "/c", "mklink", "/J", str(dest), str(target)]
        subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    else:
        dest.symlink_to(target, target_is_directory=True)


def link(out: Path, agents: list[str], apply: bool) -> list[dict]:
    homes = registry.targets()
    actions = []
    if not out.exists():
        return [{"action": "missing-shared-library", "destination": str(out)}]
    for agent in agents:
        dest_root = homes[agent]
        if canonical(dest_root) == out or below(out, canonical(dest_root)):
            actions.append({"agent": agent, "action": "unsafe-shared-library-nested-in-target", "destination": str(dest_root)})
            continue
        for skill in sorted(out.iterdir(), key=lambda p: p.name.lower()):
            if not skill.is_dir() or is_link(skill) or not (skill / "SKILL.md").is_file():
                continue
            dest = dest_root / skill.name
            if dest.exists() or is_link(dest):
                status = "already-linked" if is_link(dest) and canonical(dest) == canonical(skill) else "target-name-taken"
            elif apply:
                try:
                    dest_root.mkdir(parents=True, exist_ok=True)
                    link_target(skill, dest)
                    status = "linked"
                except (OSError, subprocess.CalledProcessError) as exc:
                    status = f"failed: {exc}"
            else:
                status = "would-link"
            actions.append({"agent": agent, "name": skill.name, "action": status,
                            "destination": str(dest), "target": str(skill)})
    return actions


def to_jsonable(plan: dict) -> dict:
    return {k: [s.as_dict() if isinstance(s, Skill) else s for s in v] for k,v in plan.items()}


def show(plan: dict, actions: list[dict] | None = None) -> None:
    print("\n=== Agent Skill Hub ===")
    print(f"Scanned roots: {len(plan['roots'])}; skills found: {len(plan['skills'])}; "
          f"unique: {len(plan['unique'])}; duplicates: {len(plan['duplicates'])}; "
          f"CONFLICTS: {len(plan['conflicts'])}; warnings: {len(plan['errors'])}")
    for r in plan["roots"]:
        print(f"  source  {r['agent']}: {r['path']}")
    for s in plan["unique"]:
        print(f"  skill   {s.name}  [{s.source}]")
    for conflict in plan["conflicts"]:
        print(f"  !!! CONFLICT: {conflict['name']}")
        for s in conflict["versions"]:
            print(f"      {s['source']}: {s['folder']} ({s['sha256'][:12]})")
    for e in plan["errors"]:
        print(f"  WARNING {e['path']}: {e['reason']}")
    if actions is not None:
        print("\n--- Proposed or applied actions ---")
        for a in actions:
            print(f"  {a.get('agent', 'hub')}/{a.get('name','-')}: {a['action']} => {a.get('destination')}")


def write_report(path: Path, result: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Report written to: {path}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Merge Windows Agent SKILL.md directories without modifying originals.")
    parser.add_argument("command", choices=["scan", "merge", "link", "sync"])
    parser.add_argument("--out", default=str(default_output()), help="Shared skills directory (default D:\\AI-Skills\\skills if D: exists)")
    parser.add_argument("--project", help="Optionally include these six project skill roots")
    parser.add_argument("--extra-root", action="append", default=[], help="Additional explicitly allowed skill root; repeat as needed")
    parser.add_argument("--agents", nargs="+", choices=sorted(registry.targets()), default=["codex", "claude"], help="Agents to link to, for link/sync")
    parser.add_argument("--apply", action="store_true", help="Actually copy and/or create links; default is a dry run")
    parser.add_argument("--report", help="Write JSON report to the path you provide")
    args = parser.parse_args(argv)
    out = canonical(Path(args.out))
    if args.command == "link":
        actions = link(out, args.agents, args.apply)
        print("=== Agent Skill Hub links ===")
        for a in actions:
            print(f"{a.get('agent', 'hub')}/{a.get('name', '-')}: {a['action']} => {a['destination']}")
        if args.report:
            write_report(Path(args.report), {"links": actions, "applied": args.apply})
        return 1 if any(a['action'].startswith("failed") for a in actions) else 0
    plan = scan(args)
    actions = []
    if args.command in {"merge", "sync"}:
        actions = merge(plan, out, args.apply)
    if args.command == "sync":
        # In preview, simulate the proposed library after the merge without touching disk.
        if args.apply:
            actions.extend(link(out, args.agents, True))
        else:
            actions.append({"name": "preview", "action": "link-preview-uses-current-library-only; run 'merge --apply' then 'link' for detailed link plan", "destination": str(out)})
    show(plan, actions if actions else None)
    if args.command != "scan" and not args.apply:
        print("\nPREVIEW ONLY: nothing was changed. Add --apply after reviewing the results.")
    if args.report:
        serial = to_jsonable(plan)
        serial["actions"] = actions
        serial["applied"] = args.apply
        write_report(Path(args.report), serial)
    return 2 if plan["conflicts"] or plan["errors"] or any("conflict" in a.get("action", "") or a.get("action", "").startswith("failed") for a in actions) else 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("Interrupted", file=sys.stderr)
        sys.exit(130)
