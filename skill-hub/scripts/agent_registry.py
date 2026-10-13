"""Documented user-level Skill roots, plus manual-only popular Agent surfaces.

A listing in the GUI does NOT mean the product supports filesystem Agent Skills.
Only verified entries have automatic scan/install paths. No program files scanned.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class AgentDefinition:
    id: str
    name: str
    user_roots: tuple[str, ...] = ()
    project_roots: tuple[str, ...] = ()
    docs: str = ""
    note: str = ""
    # An empty target means NEVER infer a writable root.
    target: str | None = None


def verified(id: str, name: str, roots: tuple[str, ...], docs: str, *,
             project: tuple[str, ...] = (), target: str | None = None, note: str = "") -> AgentDefinition:
    return AgentDefinition(id, name, roots, project, docs, note, target or roots[0])


def manual(id: str, name: str, note: str = "未核实官方本地 SKILL.md 目录；请手动指定路径并确认产品确实支持。") -> AgentDefinition:
    return AgentDefinition(id, name, note=note)


# Screenshot order, plus Codex and Gemini CLI from the existing supported set.
CATALOG: tuple[AgentDefinition, ...] = (
    manual("aider", "Aider"),
    verified("antigravity-cli", "Antigravity CLI", (".gemini/antigravity-cli/skills",),
             "https://www.antigravity.google/docs/skills?tab=ide", project=(".agents/skills",)),
    verified("claude", "Claude Code", (".claude/skills",),
             "https://code.claude.com/docs/en/skills", project=(".claude/skills",)),
    manual("claude-desktop", "Claude 桌面端", "与 Claude Code 是不同客户端；当前不自动假定共享本地技能目录。"),
    manual("claude-science", "Claude Science"),
    manual("cline-cli", "Cline CLI", "不同发行版本可能使用不同根目录；不自动等同于 Cline 桌面扩展。"),
    manual("grok-bot", "Grok Bot"),
    manual("grok-build", "Grok Build"),
    verified("kilo", "Kilo Code", (".kilo/skills",), "https://kilo.ai/docs/customize/skills", project=(".kilo/skills",)),
    verified("kimi-cli", "Kimi CLI", (".kimi/skills",),
             "https://github.com/MoonshotAI/kimi-cli/blob/main/docs/en/customization/skills.md", project=(".kimi/skills",)),
    manual("manus", "Manus"),
    manual("mimo-cli", "MiMo CLI"),
    manual("minimax-cli", "MiniMax CLI"),
    manual("oh-my-pi", "Oh My Pi", "已发现其 Skills 文档，但此版本未核实 Windows 用户级安装目录；请手动配置。"),
    verified("openclaw", "OpenClaw", (".openclaw/skills", ".openclaw/workspace/skills"),
             "https://docs.openclaw.ai/tools/skills", project=(".agents/skills",),
             note="默认扫描托管库和默认工作区；自定义多 Agent 工作区需手动添加。"),
    verified("opencode", "OpenCode", (".config/opencode/skills", ".opencode/skills"),
             "https://docs.opencode.ai/docs/skills/", project=(".opencode/skills",)),
    verified("qwen", "QwenCode", (".qwen/skills",),
             "https://qwenlm.github.io/qwen-code-docs/en/users/features/skills/", project=(".qwen/skills",)),
    manual("vibe-trading", "Vibe-Trading"),
    manual("gemini-desktop", "Gemini 桌面端", "不能将 Gemini CLI 技能目录直接视为桌面客户端的技能目录。"),
    manual("kimi-desktop", "Kimi 桌面端"),
    manual("openscience", "OpenScience"),
    verified("antigravity", "Antigravity", (".gemini/config/skills", ".gemini/antigravity/skills"),
             "https://www.antigravity.google/docs/skills?tab=ide", project=(".agents/skills",)),
    verified("cline", "Cline 桌面端", (".cline/skills",),
             "https://github.com/cline/cline/blob/main/docs/customization/skills.mdx", project=(".cline/skills", ".clinerules/skills")),
    verified("cursor", "Cursor", (".cursor/skills",),
             "https://cursor.com/docs/skills", project=(".cursor/skills",)),
    verified("deepseek-harness", "DeepSeek Harness", (".dsh/skills",),
             "https://github.com/deepseek-ai/deepseek-harness/blob/master/docs/subsystems/skills.md",
             project=(".dsh/skills",), note="也读取 .agents/skills；支持 DSH_HOME 和 customSkillDirs，扁平单文件技能需另行适配。"),
    manual("hermes-desktop", "Hermes 桌面端"),
    manual("mimo-desktop", "MiMo 桌面端"),
    manual("minimax-desktop", "MiniMax 桌面端"),
    manual("workbuddy", "WorkBuddy"),
    manual("workbuddy-ai", "WorkBuddy AI"),
    manual("zcode", "ZCode"),
    manual("coffee-cli", "Coffee CLI"),
    verified("codex", "Codex", (".agents/skills", ".codex/skills"),
             "https://developers.openai.com/codex/skills", project=(".agents/skills", ".codex/skills")),
    verified("gemini", "Gemini CLI", (".gemini/skills",),
             "https://github.com/google-gemini/gemini-cli/blob/main/docs/cli/using-agent-skills.md", project=(".gemini/skills",)),
)

BY_ID = {entry.id: entry for entry in CATALOG}


def expand_root(rel: str, home: Path | None = None, *, id: str = "") -> Path:
    home = home or Path.home()
    if id == "deepseek-harness" and rel == ".dsh/skills" and os.environ.get("DSH_HOME"):
        return Path(os.environ["DSH_HOME"]).expanduser() / "skills"
    return home / rel


def scan_roots(project: Path | None = None, home: Path | None = None) -> list[tuple[str, Path]]:
    paths: list[tuple[str, Path]] = []
    for a in CATALOG:
        for i, rel in enumerate(a.user_roots):
            paths.append((f"agent::{a.id}::{i}", expand_root(rel, home, id=a.id)))
    if project:
        project = Path(project).expanduser()
        for a in CATALOG:
            for i, rel in enumerate(a.project_roots):
                paths.append((f"project-agent::{a.id}::{i}", project / rel))
    return paths


def targets(home: Path | None = None) -> dict[str, Path]:
    return {a.id: expand_root(a.target, home, id=a.id) for a in CATALOG if a.target}

# These products are documented as reading the generic .agents/skills alias.
# This is display-only: it NEVER changes their native write targets.
SHARED_AGENTS_READERS = frozenset({
    "codex", "gemini", "opencode", "kilo", "kimi-cli", "openclaw",
    "antigravity", "antigravity-cli", "deepseek-harness",
})
