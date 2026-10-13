#!/usr/bin/env python3
"""Agent Skill Hub v0.4 — Fluent-inspired Windows desktop workspace (stdlib Tkinter).

UI and policy edits are separate from filesystem effects. No Skill is executed.
"""
from __future__ import annotations

import os
import subprocess
import sys
import uuid
from argparse import Namespace
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog, ttk

import skill_hub as hub
import share_engine as engine
import agent_registry as registry
import gui_logic as logic

BG = '#F5F7FB'
NAV = '#162131'
NAV_MUTED = '#9FAFC6'
TEXT = '#19263A'
MUTED = '#64748B'
ACCENT = '#386BEB'
ACCENT_DARK = '#2559D2'
BORDER = '#E2E8F0'
WHITE = '#FFFFFF'
GREEN = '#16835D'
AMBER = '#B77011'
RED = '#CA4F4F'
FONT = 'Microsoft YaHei UI' if sys.platform == 'win32' else 'DejaVu Sans'


def button(parent, label, callback, *, kind='secondary', padx=14, pady=9):
    palette = {
        'primary': (ACCENT, WHITE, ACCENT_DARK),
        'secondary': (WHITE, TEXT, '#EFF3F9'),
        'ghost': (BG, TEXT, '#E9EFFA'),
        'sidebar': (NAV, '#D5DEEC', '#273B54'),
        'danger': ('#FCEEEE', RED, '#F9DCDD'),
    }
    bg, fg, hover = palette[kind]
    b = tk.Button(parent, text=label, command=callback, bg=bg, fg=fg,
                  activebackground=hover, activeforeground=fg, bd=0,
                  padx=padx, pady=pady, relief='flat', cursor='hand2',
                  font=(FONT, 10, 'bold' if kind == 'primary' else 'normal'),
                  highlightthickness=1 if kind == 'secondary' else 0,
                  highlightbackground=BORDER, highlightcolor=ACCENT)
    b.bind('<Enter>', lambda _e: b.configure(bg=hover))
    b.bind('<Leave>', lambda _e: b.configure(bg=bg))
    return b


def text_label(parent, text, *, size=10, color=TEXT, bold=False, bg=WHITE, **kwargs):
    return tk.Label(parent, text=text, bg=bg, fg=color,
                    font=(FONT, size, 'bold' if bold else 'normal'), **kwargs)


class SkillHubGUI:
    def __init__(self, root: tk.Tk):
        self.root = root
        root.title('Agent Skill Hub · Skills 工作台')
        root.geometry('1480x870')
        root.minsize(1090, 690)
        root.configure(bg=BG)
        self.config = engine.load_settings()
        self.current_agent = 'codex'
        self.plan: dict = {'skills': [], 'roots': [], 'conflicts': [], 'errors': [], 'duplicates': []}
        self.rows: dict[str, dict] = {}
        self.filtered_rows: list[dict] = []
        self.selected_skill: dict | None = None
        self.dest_vars: dict[str, tk.BooleanVar] = {}
        self.dirty = False
        self.last_log = '尚无执行记录。'
        self.agent_query = tk.StringVar()
        self.skill_query = tk.StringVar()
        self.filter_mode = 'all'
        self.status_text = tk.StringVar(value='默认安全模式 · 操作前会先预览')
        self.library_text = tk.StringVar(value=self.config['library'])
        self.project_text = tk.StringVar(value=self.config.get('project', ''))
        self.share_var = tk.BooleanVar()
        self._init_style()
        self._build()
        self.agent_query.trace_add('write', lambda *_: self.render_agent_list())
        self.skill_query.trace_add('write', lambda *_: self.render_skills())
        self.root.bind('<Control-f>', lambda _e: self.focus_search())
        self.root.bind('<Control-s>', lambda _e: self.save_settings())
        self.root.bind('<Control-r>', lambda _e: self.rescan())
        self.root.protocol('WM_DELETE_WINDOW', self.close)
        self._build_target_options()
        self.rescan()

    def _init_style(self):
        style = ttk.Style(self.root)
        if 'clam' in style.theme_names():
            style.theme_use('clam')
        style.configure('Hub.Treeview', font=(FONT, 10), background=WHITE,
                        fieldbackground=WHITE, foreground=TEXT, rowheight=43,
                        borderwidth=0, relief='flat')
        style.configure('Hub.Treeview.Heading', font=(FONT, 10, 'bold'),
                        background='#F0F4FA', foreground=MUTED, relief='flat',
                        borderwidth=0, padding=(10, 12))
        style.map('Hub.Treeview', background=[('selected', '#E2EBFF')],
                  foreground=[('selected', TEXT)])
        style.map('Hub.Treeview.Heading', background=[('active', '#E7EDF6')])
        style.configure('Hub.Vertical.TScrollbar', background='#DAE2EF', troughcolor=WHITE,
                        relief='flat', borderwidth=0)

    def _build(self):
        self.sidebar = tk.Frame(self.root, bg=NAV, width=272)
        self.sidebar.pack(side='left', fill='y')
        self.sidebar.pack_propagate(False)
        self._build_sidebar()
        area = tk.Frame(self.root, bg=BG)
        area.pack(side='left', fill='both', expand=True)
        self._build_top(area)
        self._build_footer(area)
        main = tk.PanedWindow(area, orient='horizontal', bg=BG,
                              sashwidth=8, bd=0, relief='flat', opaqueresize=True)
        main.pack(fill='both', expand=True, padx=20, pady=(3, 10))
        left = tk.Frame(main, bg=WHITE, highlightthickness=1, highlightbackground=BORDER)
        right = tk.Frame(main, bg=WHITE, width=355, highlightthickness=1, highlightbackground=BORDER)
        main.add(left, minsize=410, stretch='always')
        main.add(right, minsize=305, stretch='never')
        self._build_skills(left)
        self._build_details(right)

    def _build_sidebar(self):
        brand = tk.Frame(self.sidebar, bg=NAV)
        brand.pack(fill='x', padx=22, pady=(24, 19))
        logo = tk.Label(brand, text='  S  ', bg=ACCENT, fg=WHITE, font=(FONT, 16, 'bold'), pady=7)
        logo.pack(side='left')
        title_box = tk.Frame(brand, bg=NAV)
        title_box.pack(side='left', padx=(10, 0))
        text_label(title_box, 'Agent Skill Hub', size=13, bold=True, bg=NAV, color=WHITE).pack(anchor='w')
        text_label(title_box, '共享技能管理器  /  v0.4', size=8, color=NAV_MUTED, bg=NAV).pack(anchor='w', pady=(4, 0))
        text_label(self.sidebar, 'AGENTS  ·  代理列表', size=9, color=NAV_MUTED, bold=True, bg=NAV).pack(anchor='w', padx=22, pady=(3, 9))
        search_bg = tk.Frame(self.sidebar, bg='#27364C')
        search_bg.pack(fill='x', padx=17, pady=(0, 12))
        text_label(search_bg, '⌕', size=16, bg='#27364C', color='#BBC9DB').pack(side='left', padx=(10, 3))
        search = tk.Entry(search_bg, textvariable=self.agent_query, bd=0, bg='#27364C',
                          fg=WHITE, insertbackground=WHITE, font=(FONT, 10), highlightthickness=0)
        search.pack(side='left', fill='x', expand=True, padx=(0, 8), pady=11)
        self.agent_canvas = tk.Canvas(self.sidebar, bg=NAV, bd=0, highlightthickness=0)
        self.agent_canvas.pack(side='top', fill='both', expand=True, padx=(7, 2))
        scrollbar = ttk.Scrollbar(self.sidebar, orient='vertical', command=self.agent_canvas.yview)
        scrollbar.place(relx=0.984, rely=0.212, relheight=0.67, anchor='ne')
        self.agent_canvas.configure(yscrollcommand=scrollbar.set)
        self.agent_list = tk.Frame(self.agent_canvas, bg=NAV)
        self.agent_window = self.agent_canvas.create_window((0, 0), window=self.agent_list, anchor='nw')
        self.agent_list.bind('<Configure>', lambda _e: self.agent_canvas.configure(scrollregion=self.agent_canvas.bbox('all')))
        self.agent_canvas.bind('<Configure>', lambda e: self.agent_canvas.itemconfigure(self.agent_window, width=e.width))
        self.agent_canvas.bind('<MouseWheel>', lambda e: self.agent_canvas.yview_scroll(int(-e.delta/120), 'units'))
        self.agent_list.bind('<MouseWheel>', lambda e: self.agent_canvas.yview_scroll(int(-e.delta/120), 'units'))
        foot = tk.Frame(self.sidebar, bg=NAV)
        foot.pack(fill='x', pady=(11, 18), padx=16)
        button(foot, '＋ 添加 Agent', self.add_agent, kind='sidebar').pack(fill='x')
        button(foot, '配置目录', self.configure_agent, kind='sidebar').pack(fill='x', pady=(2, 0))
        button(foot, '移除自定义', self.remove_agent, kind='sidebar').pack(fill='x', pady=(2, 0))
        button(foot, '设置与路径', self.open_settings, kind='sidebar').pack(fill='x', pady=(2, 0))

    def _build_top(self, area):
        frame = tk.Frame(area, bg=BG)
        frame.pack(fill='x', padx=24, pady=(21, 16))
        heading = tk.Frame(frame, bg=BG)
        heading.pack(side='left', fill='x', expand=True)
        text_label(heading, 'WORKSPACE  /  SKILLS', size=9, bg=BG, color=MUTED).pack(anchor='w')
        self.head_title = text_label(heading, '技能工作台', size=21, bold=True, bg=BG)
        self.head_title.pack(anchor='w', pady=(4, 2))
        self.head_caption = text_label(heading, '按 Agent 查看技能，然后选择共享范围', size=10, bg=BG, color=MUTED)
        self.head_caption.pack(anchor='w')
        buttons = tk.Frame(frame, bg=BG)
        buttons.pack(side='right', anchor='n', pady=(8, 0))
        button(buttons, '查看日志', self.view_log).pack(side='right', padx=(8, 0))
        button(buttons, '⟳  重新扫描', self.rescan).pack(side='right')

    def _build_skills(self, frame):
        top = tk.Frame(frame, bg=WHITE)
        top.pack(fill='x', padx=21, pady=(19, 15))
        text_label(top, '技能列表', size=15, bold=True).pack(side='left')
        self.count_label = text_label(top, '0 项', size=10, color=MUTED)
        self.count_label.pack(side='left', padx=10, pady=4)
        tk.Frame(frame, bg=BORDER, height=1).pack(fill='x')
        toolbar = tk.Frame(frame, bg=WHITE)
        toolbar.pack(fill='x', padx=20, pady=(16, 11))
        entry_wrap = tk.Frame(toolbar, bg='#F0F4F9')
        entry_wrap.pack(fill='x')
        text_label(entry_wrap, '⌕', size=15, bg='#F0F4F9', color=MUTED).pack(side='left', padx=(13, 5))
        self.search_entry = tk.Entry(entry_wrap, textvariable=self.skill_query, bd=0, highlightthickness=0,
                                     font=(FONT, 10), bg='#F0F4F9', fg=TEXT, insertbackground=TEXT)
        self.search_entry.pack(side='left', fill='x', expand=True, pady=12, padx=(0, 12))
        tabs = tk.Frame(frame, bg=WHITE)
        tabs.pack(fill='x', padx=20, pady=(0, 12))
        self.tab_buttons = {}
        for value, label in [('all', '全部'), ('shared', '已共享'), ('private', '未共享'), ('conflict', '有冲突')]:
            b = tk.Button(tabs, text=label, command=lambda v=value: self.set_filter(v),
                          bg=WHITE, fg=MUTED, bd=0, activeforeground=ACCENT, activebackground='#F2F6FF',
                          font=(FONT, 10), padx=11, pady=8, cursor='hand2')
            b.pack(side='left', padx=(0, 3))
            self.tab_buttons[value] = b
        self._paint_tabs()
        table_box = tk.Frame(frame, bg=WHITE)
        table_box.pack(fill='both', expand=True, padx=15)
        self.skills = ttk.Treeview(table_box, style='Hub.Treeview', show='headings', selectmode='extended',
                                    columns=('state', 'name', 'origin'), height=12)
        self.skills.heading('state', text='共享状态')
        self.skills.heading('name', text='SKILL NAME')
        self.skills.heading('origin', text='来源')
        self.skills.column('state', width=86, minwidth=82, stretch=False)
        self.skills.column('name', width=235, minwidth=150, stretch=True)
        self.skills.column('origin', width=145, minwidth=90, stretch=True)
        self.skills.pack(side='left', fill='both', expand=True)
        bar = ttk.Scrollbar(table_box, orient='vertical', command=self.skills.yview)
        bar.pack(side='right', fill='y')
        self.skills.configure(yscrollcommand=bar.set)
        self.skills.bind('<<TreeviewSelect>>', self.on_skill_select)
        self.skills.bind('<Double-1>', lambda _e: self.toggle_selected())
        self.empty = text_label(frame, '', size=10, color=MUTED, anchor='w')
        self.empty.pack(fill='x', padx=22, pady=(2, 4))
        bulk = tk.Frame(frame, bg='#F9FAFD', height=64)
        bulk.pack(fill='x', side='bottom')
        tk.Frame(bulk, bg=BORDER, height=1).pack(fill='x')
        actions = tk.Frame(bulk, bg='#F9FAFD')
        actions.pack(fill='x', padx=15, pady=12)
        self.selection_count = text_label(actions, '未选择技能', bg='#F9FAFD', size=9, color=MUTED)
        self.selection_count.pack(side='left', padx=(0, 8))
        button(actions, '批量设置共享', self.bulk_share, kind='ghost', padx=11, pady=7).pack(side='right')
        button(actions, '取消共享', self.bulk_disable, kind='ghost', padx=11, pady=7).pack(side='right', padx=(0, 5))

    def _build_details(self, frame):
        top = tk.Frame(frame, bg=WHITE)
        top.pack(fill='x', padx=20, pady=(19, 15))
        text_label(top, '技能详情', size=15, bold=True).pack(side='left')
        tk.Frame(frame, bg=BORDER, height=1).pack(fill='x')
        details = tk.Frame(frame, bg=WHITE)
        details.pack(fill='x', padx=20, pady=(18, 10))
        self.detail_name = text_label(details, '请选择一个 Skill', size=13, bold=True, anchor='w', justify='left', wraplength=300)
        self.detail_name.pack(fill='x', anchor='w')
        self.detail_hint = text_label(details, '点击中间的技能，查看说明与共享对象。', size=9,
                                       color=MUTED, wraplength=310, anchor='w', justify='left')
        self.detail_hint.pack(fill='x', pady=(7, 0))
        self.detail_path = text_label(details, '', size=9, color=MUTED, wraplength=310, justify='left', anchor='w')
        self.detail_path.pack(fill='x', pady=(10, 0))
        self.open_folder_btn = button(details, '打开技能目录  ↗', self.open_selected_folder, kind='ghost', padx=10, pady=7)
        self.open_folder_btn.pack(anchor='w', pady=(9, 0))
        tk.Frame(frame, bg=BORDER, height=1).pack(fill='x', pady=(2, 0))
        controls = tk.Frame(frame, bg=WHITE)
        controls.pack(fill='x', padx=20, pady=(15, 4))
        text_label(controls, '共享设置', size=11, bold=True).pack(anchor='w')
        self.share_check = tk.Checkbutton(controls, text='加入共享库', variable=self.share_var,
                                          command=self.change_single_policy, bg=WHITE, fg=TEXT,
                                          activebackground=WHITE, font=(FONT, 10), selectcolor=WHITE)
        self.share_check.pack(anchor='w', pady=(9, 7))
        top_targets = tk.Frame(frame, bg=WHITE)
        top_targets.pack(fill='x', padx=20, pady=(12, 4))
        text_label(top_targets, '共享到以下 Agent', size=10, bold=True).pack(side='left')
        self.clear_targets_btn = button(top_targets, '清空', lambda: self.set_targets(False), kind='ghost', padx=8, pady=5)
        self.clear_targets_btn.pack(side='right')
        self.all_targets_btn = button(top_targets, '全选', lambda: self.set_targets(True), kind='ghost', padx=8, pady=5)
        self.all_targets_btn.pack(side='right', padx=(0, 5))
        target_box = tk.Frame(frame, bg=WHITE)
        target_box.pack(fill='both', expand=True, padx=(20, 6), pady=(2, 7))
        self.targets_canvas = tk.Canvas(target_box, bg=WHITE, bd=0, highlightthickness=0)
        self.targets_canvas.pack(side='left', fill='both', expand=True)
        scroll = ttk.Scrollbar(target_box, orient='vertical', command=self.targets_canvas.yview)
        scroll.pack(side='right', fill='y')
        self.targets_canvas.configure(yscrollcommand=scroll.set)
        self.targets_frame = tk.Frame(self.targets_canvas, bg=WHITE)
        self.targets_canvas_window = self.targets_canvas.create_window((0, 0), window=self.targets_frame, anchor='nw')
        self.targets_frame.bind('<Configure>', lambda _e: self.targets_canvas.configure(scrollregion=self.targets_canvas.bbox('all')))
        self.targets_canvas.bind('<Configure>', lambda e: self.targets_canvas.itemconfigure(self.targets_canvas_window, width=e.width))
        self.targets_canvas.bind('<MouseWheel>', lambda e: self.targets_canvas.yview_scroll(int(-e.delta/120), 'units'))
        note = tk.Frame(frame, bg='#F0F4FA')
        note.pack(fill='x', side='bottom', padx=13, pady=(0, 13))
        text_label(note, '提示：共享控制链接安装位置，不保证阻止其他 Agent\n通过兼容目录读取技能。原始技能始终保留。',
                   color=MUTED, size=9, bg='#F0F4FA', wraplength=320, justify='left').pack(padx=11, pady=11, anchor='w')

    def _build_footer(self, area):
        footer = tk.Frame(area, bg=WHITE, height=77, highlightthickness=1, highlightbackground=BORDER)
        footer.pack(fill='x', side='bottom')
        left = tk.Frame(footer, bg=WHITE)
        left.pack(side='left', fill='y', padx=23, pady=15)
        self.dirty_badge = text_label(left, '●  所有设置已保存', size=10, bg=WHITE, color=GREEN, bold=True)
        self.dirty_badge.pack(anchor='w')
        self.footer_note = text_label(left, '更改会先暂存，不会立即复制或删除文件', size=9, bg=WHITE, color=MUTED)
        self.footer_note.pack(anchor='w', pady=(3, 0))
        actions = tk.Frame(footer, bg=WHITE)
        actions.pack(side='right', padx=19, pady=14)
        button(actions, '预览并执行  →', self.preview, kind='primary', padx=18).pack(side='right')
        button(actions, '保存设置', self.save_settings).pack(side='right', padx=(0, 9))
        text_label(area, ' ', bg=BG).pack_forget()

    def _paint_tabs(self):
        for name, b in self.tab_buttons.items():
            b.configure(bg='#E7EFFF' if self.filter_mode == name else WHITE,
                        fg=ACCENT if self.filter_mode == name else MUTED)

    def set_filter(self, mode):
        self.filter_mode = mode
        self._paint_tabs()
        self.render_skills()

    def focus_search(self):
        self.search_entry.focus_set()
        self.search_entry.select_range(0, 'end')

    def _mark_dirty(self):
        self.dirty = True
        self.dirty_badge.configure(text='●  存在未保存的共享设置', fg=AMBER)

    def _clean(self):
        self.dirty = False
        self.dirty_badge.configure(text='●  所有设置已保存', fg=GREEN)

    def _sync_paths(self):
        path = self.config['library']
        if not path.strip():
            raise ValueError('共享库路径不能为空')
        self.config['library'] = str(hub.canonical(Path(path)))
        project = self.config.get('project', '')
        if project and not Path(project).is_dir():
            raise ValueError('工程目录不存在')

    def rescan(self):
        try:
            self._sync_paths()
            args = Namespace(out=self.config['library'], project=self.config.get('project') or None,
                             extra_root=[a['path'] for a in self.config['custom_agents']],
                             agent_paths=self.config.get('agent_paths', {}))
            self.plan = hub.scan(args)
            self.render_agent_list()
            self.render_skills()
            self.status_text.set(f"已发现 {len(self.plan['skills'])} 个 Skills，{len(self.plan['conflicts'])} 个冲突")
            self.footer_note.configure(text=self.status_text.get())
            return True
        except Exception as exc:
            messagebox.showerror('无法扫描', str(exc), parent=self.root)
            return False

    def name_of_agent(self, agent):
        return engine.AGENT_NAMES.get(agent, next((x['name'] for x in self.config['custom_agents'] if x['id'] == agent), agent))

    def skills_for_agent(self, agent_id):
        if agent_id == 'all':
            return list(self.plan['skills'])
        if agent_id.startswith('custom_'):
            roots = [Path(a['path']) for a in self.config['custom_agents'] if a['id'] == agent_id]
        else:
            roots = []
            info = registry.BY_ID.get(agent_id)
            if info:
                roots.extend(registry.expand_root(rel, id=agent_id) for rel in info.user_roots)
                project = self.config.get('project')
                if project:
                    roots.extend(Path(project) / rel for rel in info.project_roots)
                custom_root = self.config.get('agent_paths', {}).get(agent_id)
                if custom_root:
                    roots.append(Path(custom_root))
                if agent_id in registry.SHARED_AGENTS_READERS:
                    roots.append(Path.home() / '.agents' / 'skills')
        canon = [hub.canonical(r) for r in roots if r.is_dir()]
        found = []
        for item in self.plan['skills']:
            if engine.source_agent(item['source'], self.config['custom_agents']) == agent_id or any(
                hub.below(hub.canonical(Path(item['folder'])), p) for p in canon):
                found.append(item)
        return found

    def render_agent_list(self):
        if not hasattr(self, 'agent_list'):
            return
        for child in self.agent_list.winfo_children():
            child.destroy()
        query = self.agent_query.get().strip().casefold()
        names = [('all', '全部技能')] + list(engine.AGENT_NAMES.items()) + [(a['id'], a['name']) for a in self.config['custom_agents']]
        visible = []
        for aid, name in names:
            if query and query not in name.casefold() and query not in aid.casefold():
                continue
            visible.append(aid)
            count = len(self.skills_for_agent(aid))
            selected = aid == self.current_agent
            active = '#304B71' if selected else NAV
            row = tk.Frame(self.agent_list, bg=active, cursor='hand2')
            row.pack(fill='x', padx=9, pady=2)
            marker = tk.Frame(row, width=3, bg='#8BB3FF' if selected else active)
            marker.pack(side='left', fill='y')
            dot = tk.Label(row, text='●' if count else '○', fg='#6ED9AD' if count else '#76869B',
                           bg=active, font=(FONT, 9))
            dot.pack(side='left', padx=(9, 8))
            lab = text_label(row, name, size=10, bg=active, color=WHITE if selected else '#C6D2E3',
                             bold=selected, anchor='w')
            lab.pack(side='left', fill='x', expand=True, pady=11)
            badge = text_label(row, str(count), size=9, bg=active, color='#B8C8DD')
            badge.pack(side='right', padx=11)
            for widget in (row, marker, dot, lab, badge):
                widget.bind('<Button-1>', lambda _e, a=aid: self.select_agent(a))
                widget.bind('<MouseWheel>', lambda e: self.agent_canvas.yview_scroll(int(-e.delta/120), 'units'))
        if self.current_agent not in visible and visible:
            self.current_agent = visible[0]

    def select_agent(self, aid):
        if aid == self.current_agent:
            return
        self.current_agent = aid
        self.skill_query.set('')
        self.filter_mode = 'all'
        self._paint_tabs()
        self.render_agent_list()
        self.render_skills()

    def _collect_rows(self):
        raw = self.skills_for_agent(self.current_agent)
        rows = []
        for item in raw:
            policy = self.config.get('policies', {}).get(engine.key_for_skill(item), {})
            rows.append({**item, 'enabled': bool(policy.get('enabled'))})
        if self.current_agent != 'all':
            candidates = []
            targets = engine.target_roots(self.config['custom_agents'], configured=self.config.get('agent_paths', {}))
            if self.current_agent in targets:
                candidates.append(targets[self.current_agent])
            if self.current_agent == 'codex':
                candidates.append(Path.home() / '.codex' / 'skills')
            seen = set()
            for root in candidates:
                try:
                    children = list(root.iterdir()) if root.is_dir() else []
                except OSError:
                    continue
                for child in children:
                    if str(child) in seen or not hub.is_link(child):
                        continue
                    seen.add(str(child))
                    name, _ = hub.skill_meta(child / 'SKILL.md')
                    if name:
                        rows.append({'name': name, 'folder': str(child), 'source': '已安装的技能链接',
                                     'enabled': False, 'managed': True})
        rows.sort(key=lambda x: (x.get('name', '').casefold(), bool(x.get('managed'))))
        return rows

    def render_skills(self):
        if not hasattr(self, 'skills'):
            return
        old_selected = [self.rows[i].get('folder') for i in self.skills.selection() if i in self.rows]
        self.skills.delete(*self.skills.get_children())
        self.rows = {}
        all_rows = self._collect_rows()
        conflicts = {x['name'] for x in self.plan.get('conflicts', [])}
        visible = logic.visible_rows(all_rows, self.skill_query.get(), self.filter_mode, conflicts)
        for idx, item in enumerate(visible):
            iid = f'skill-{idx}'
            self.rows[iid] = item
            status = '冲突' if item['name'] in conflicts else ('已链接' if item.get('managed') else '共享中' if item['enabled'] else '未共享')
            agent = self.name_of_agent(engine.source_agent(item['source'], self.config['custom_agents']))
            if item.get('managed'):
                agent = '链接'
            self.skills.insert('', 'end', iid=iid, values=(status, item['name'], agent))
            if item.get('folder') in old_selected:
                self.skills.selection_add(iid)
        title = '全部技能' if self.current_agent == 'all' else self.name_of_agent(self.current_agent)
        self.head_title.configure(text=title)
        self.head_caption.configure(text=f"检测到 {len(all_rows)} 项 · 已共享 {sum(bool(x.get('enabled')) for x in all_rows)} 项 · 冲突 {sum(x['name'] in conflicts for x in all_rows)} 项")
        self.count_label.configure(text=f'{len(visible)} / {len(all_rows)} 项')
        self.empty.configure(text='未找到匹配的技能。可调整搜索或筛选条件。' if not visible else '')
        self.on_skill_select()

    def on_skill_select(self, _event=None):
        ids = self.skills.selection()
        selected = [self.rows[x] for x in ids if x in self.rows]
        self.selection_count.configure(text=f'已选择 {len(selected)} 项' if selected else '未选择技能')
        if len(selected) != 1:
            self.selected_skill = None
            self.detail_name.configure(text=f'已选择 {len(selected)} 项技能' if selected else '请选择一个 Skill')
            self.detail_hint.configure(text='使用下方“批量设置共享”调整共同接收方。' if selected else '点击中间的技能，查看说明与共享对象。')
            self.detail_path.configure(text='')
            self.share_var.set(False)
            self._enable_details(False)
            return
        skill = selected[0]
        self.selected_skill = skill
        self.detail_name.configure(text=skill['name'])
        if skill.get('managed'):
            self.detail_hint.configure(text='这是已安装目录链接。请通过来源 Agent 调整共享设置。')
            self.share_var.set(False)
        else:
            _name, desc = hub.skill_meta(Path(skill['folder']) / 'SKILL.md')
            self.detail_hint.configure(text=(desc or '无描述')[:250])
            policy = self.config.get('policies', {}).get(engine.key_for_skill(skill), {})
            self.share_var.set(bool(policy.get('enabled')))
            for aid, var in self.dest_vars.items():
                var.set(aid in policy.get('targets', []))
        self.detail_path.configure(text=f"来源路径\n{skill['folder']}")
        self._enable_details(not bool(skill.get('managed')))

    def _enable_details(self, enable):
        self.share_check.configure(state='normal' if enable else 'disabled')
        for b in (self.clear_targets_btn, self.all_targets_btn):
            b.configure(state='normal' if enable and self.share_var.get() else 'disabled')
        self.open_folder_btn.configure(state='normal' if self.selected_skill else 'disabled')
        for w in self.targets_frame.winfo_children():
            if isinstance(w, tk.Checkbutton):
                w.configure(state='normal' if enable and self.share_var.get() else 'disabled')

    def _build_target_options(self):
        for child in self.targets_frame.winfo_children():
            child.destroy()
        self.dest_vars = {}
        target_roots = engine.target_roots(self.config['custom_agents'], configured=self.config.get('agent_paths', {}))
        for aid in sorted(target_roots, key=lambda k: self.name_of_agent(k).casefold()):
            if aid in registry.BY_ID and not registry.BY_ID[aid].target and aid not in self.config.get('agent_paths', {}):
                continue
            v = tk.BooleanVar(value=False)
            self.dest_vars[aid] = v
            line = tk.Checkbutton(self.targets_frame, text=self.name_of_agent(aid), variable=v,
                                  command=self.change_single_policy, bg=WHITE, fg=TEXT,
                                  activebackground=WHITE, font=(FONT, 10), selectcolor=WHITE,
                                  anchor='w', pady=7, padx=5)
            line.pack(fill='x')
            line.bind('<MouseWheel>', lambda e: self.targets_canvas.yview_scroll(int(-e.delta/120), 'units'))
        self._enable_details(False)

    def set_targets(self, value):
        if not self.selected_skill or self.selected_skill.get('managed'):
            return
        for v in self.dest_vars.values():
            v.set(value)
        self.change_single_policy()

    def change_single_policy(self):
        if not self.selected_skill or self.selected_skill.get('managed'):
            return
        new_targets = [aid for aid, v in self.dest_vars.items() if v.get()]
        change = logic.change_policies(self.config, [self.selected_skill], enabled=self.share_var.get(), targets=new_targets)
        if change:
            self._mark_dirty()
            self.render_skills()

    def toggle_selected(self):
        if len(self.skills.selection()) != 1 or not self.selected_skill or self.selected_skill.get('managed'):
            return
        self.share_var.set(not self.share_var.get())
        self.change_single_policy()

    def bulk_disable(self):
        selection = [self.rows[i] for i in self.skills.selection() if i in self.rows and not self.rows[i].get('managed')]
        if not selection:
            return
        count = logic.change_policies(self.config, selection, enabled=False)
        if count:
            self._mark_dirty()
        self.render_skills()
        self.footer_note.configure(text=f'暂存：{count} 个 Skill 将停止共享；预览后才会撤销链接')

    def bulk_share(self):
        selection = [self.rows[i] for i in self.skills.selection() if i in self.rows and not self.rows[i].get('managed')]
        if not selection:
            messagebox.showinfo('批量设置', '请按 Ctrl 或 Shift 在技能列表中多选。', parent=self.root)
            return
        dlg = tk.Toplevel(self.root)
        dlg.title('批量设置共享')
        dlg.configure(bg=BG)
        dlg.transient(self.root)
        dlg.grab_set()
        dlg.geometry('445x565')
        dlg.minsize(380, 400)
        text_label(dlg, f'为 {len(selection)} 个 Skill 设置接收范围', bg=BG, size=14, bold=True).pack(anchor='w', padx=22, pady=(24, 6))
        text_label(dlg, '将统一启用共享，并用本次选择替换这些技能的接收方。', bg=BG, color=MUTED,
                   wraplength=400, justify='left').pack(anchor='w', padx=22, pady=(0, 12))
        frame = tk.Frame(dlg, bg=WHITE, highlightthickness=1, highlightbackground=BORDER)
        frame.pack(fill='both', expand=True, padx=22)
        can = tk.Canvas(frame, bg=WHITE, bd=0, highlightthickness=0)
        can.pack(side='left', fill='both', expand=True)
        box = tk.Frame(can, bg=WHITE)
        cid = can.create_window((0, 0), window=box, anchor='nw')
        can.bind('<Configure>', lambda e: can.itemconfigure(cid, width=e.width))
        box.bind('<Configure>', lambda _e: can.configure(scrollregion=can.bbox('all')))
        scroll = ttk.Scrollbar(frame, orient='vertical', command=can.yview)
        scroll.pack(side='right', fill='y')
        can.configure(yscrollcommand=scroll.set)
        opts = {}
        for aid in self.dest_vars:
            v = tk.BooleanVar()
            opts[aid] = v
            tk.Checkbutton(box, text=self.name_of_agent(aid), variable=v, font=(FONT, 10),
                           bg=WHITE, activebackground=WHITE, anchor='w', pady=6).pack(fill='x', padx=12)
        def accept():
            targets = [aid for aid, v in opts.items() if v.get()]
            if not targets:
                messagebox.showwarning('选择接收方', '请至少选择一个接收 Agent。', parent=dlg)
                return
            n = logic.change_policies(self.config, selection, enabled=True, targets=targets)
            if n:
                self._mark_dirty()
            dlg.destroy()
            self.render_skills()
            self.footer_note.configure(text=f'批量设置已暂存：{n} 项技能，{len(targets)} 个接收 Agent')
        foot = tk.Frame(dlg, bg=BG)
        foot.pack(fill='x', padx=22, pady=18)
        button(foot, '确认暂存', accept, kind='primary').pack(side='right')
        button(foot, '取消', dlg.destroy).pack(side='right', padx=7)
        dlg.bind('<Escape>', lambda _e: dlg.destroy())
        self.root.wait_window(dlg)

    def save_settings(self):
        try:
            self._sync_paths()
            engine.save_settings(self.config)
            self._clean()
            self.footer_note.configure(text='共享设置已保存；尚未对技能文件执行变更')
            return True
        except Exception as exc:
            messagebox.showerror('无法保存设置', str(exc), parent=self.root)
            return False

    def _preview_data(self):
        roots = engine.target_roots(self.config['custom_agents'], configured=self.config.get('agent_paths', {}))
        return engine.make_plan(self.plan, self.config, roots), roots

    def preview(self):
        if not self.rescan():
            return
        if not self.save_settings():
            return
        try:
            preview, roots = self._preview_data()
        except Exception as exc:
            messagebox.showerror('预览失败', str(exc), parent=self.root)
            return
        stats = logic.describe_changes(preview)
        dlg = tk.Toplevel(self.root)
        dlg.title('变更预览 · Agent Skill Hub')
        dlg.geometry('790x590')
        dlg.minsize(600, 460)
        dlg.transient(self.root)
        dlg.configure(bg=BG)
        dlg.grab_set()
        text_label(dlg, '变更预览', size=18, bold=True, bg=BG).pack(anchor='w', padx=24, pady=(22, 4))
        text_label(dlg, '确认以下操作后才会修改共用库与 Agent 链接；不会覆盖来源 Skill。',
                   color=MUTED, bg=BG).pack(anchor='w', padx=24)
        stat = tk.Frame(dlg, bg=BG)
        stat.pack(fill='x', padx=24, pady=17)
        for label, value, c in [('新增副本', stats['copy'], ACCENT), ('新建链接', stats['link'], GREEN),
                                ('撤销链接', stats['unlink'], AMBER), ('冲突', stats['blocked'], RED)]:
            item = tk.Frame(stat, bg=WHITE, highlightthickness=1, highlightbackground=BORDER)
            item.pack(side='left', expand=True, fill='x', padx=(0, 8))
            text_label(item, str(value), size=17, bold=True, color=c).pack(pady=(10, 1))
            text_label(item, label, size=9, color=MUTED).pack(pady=(0, 10))
        tabs = ttk.Notebook(dlg)
        tabs.pack(fill='both', expand=True, padx=24)
        operations = tk.Text(tabs, wrap='none', bg=WHITE, fg=TEXT, font=(FONT, 10), bd=0, padx=14, pady=12)
        conflicts_box = tk.Text(tabs, wrap='word', bg=WHITE, fg=RED, font=(FONT, 10), bd=0, padx=14, pady=12)
        tabs.add(operations, text=f"操作计划 ({len(preview['operations'])})")
        tabs.add(conflicts_box, text=f"冲突 ({len(preview['conflicts'])})")
        map_status = {'would-copy': '复制', 'would-link': '创建链接', 'would-unlink': '撤销链接',
                      'already-present': '无变化', 'already-linked': '已存在',
                      'target-name-taken': '目标同名', 'destination-conflict': '版本冲突'}
        for op in preview['operations']:
            label = map_status.get(op['status'], op['status'])
            operations.insert('end', f"[{label}]  {op.get('name','')}  {self.name_of_agent(op['agent']) if op.get('agent') else '共用库'}\n    {op.get('target','')}\n\n")
        conflicts_box.insert('end', '\n'.join('• ' + x for x in preview['conflicts']) if preview['conflicts'] else '未发现阻止执行的冲突。')
        operations.configure(state='disabled')
        conflicts_box.configure(state='disabled')
        foot = tk.Frame(dlg, bg=BG)
        foot.pack(fill='x', padx=24, pady=17)
        def do_apply():
            if not messagebox.askyesno('确认执行', f"将新增 {stats['copy']} 份技能、创建 {stats['link']} 个链接，\n撤销 {stats['unlink']} 个本工具管理的链接。\n\n继续？", parent=dlg):
                return
            try:
                # The engine rechecks the immutable preview and refuses unsafe changes.
                changes = engine.apply_plan(preview, self.config, self.plan, roots)
                engine.save_settings(self.config)
                self.last_log = '\n'.join(f"{x['kind']} / {x.get('name', '')} / {x.get('agent', '共用库')} → {x['status']}" for x in changes)
                dlg.destroy()
                self.rescan()
                bad = [x for x in changes if x['status'].startswith(('failed', 'skipped', 'unsafe', 'target-name-taken'))]
                if bad:
                    messagebox.showwarning('部分操作未完成', f'已处理 {len(changes)} 项，其中 {len(bad)} 项需要检查。\n请查看执行日志。', parent=self.root)
                else:
                    messagebox.showinfo('完成', f'操作结束，共处理 {len(changes)} 项。\n如有必要，请重启接收 Skill 的 Agent。', parent=self.root)
            except Exception as exc:
                messagebox.showerror('执行失败', str(exc), parent=dlg)
        actions = [x for x in preview['operations'] if x['status'] in ('would-copy', 'would-link', 'would-unlink')]
        if actions and not preview['conflicts']:
            button(foot, '确认执行', do_apply, kind='primary').pack(side='right')
        button(foot, '关闭', dlg.destroy).pack(side='right', padx=(0, 10))
        dlg.bind('<Escape>', lambda _e: dlg.destroy())
        self.root.wait_window(dlg)

    def view_log(self):
        dlg = tk.Toplevel(self.root)
        dlg.title('执行记录')
        dlg.geometry('720x450')
        dlg.configure(bg=BG)
        text_label(dlg, '最近一次执行记录', size=15, bold=True, bg=BG).pack(anchor='w', padx=19, pady=16)
        box = tk.Text(dlg, bg=WHITE, fg=TEXT, wrap='word', font=(FONT, 10), padx=14, pady=13, bd=0)
        box.pack(fill='both', expand=True, padx=19, pady=(0, 19))
        box.insert('1.0', self.last_log)
        box.configure(state='disabled')

    def open_selected_folder(self):
        if not self.selected_skill:
            return
        p = Path(self.selected_skill['folder'])
        if not p.exists():
            messagebox.showwarning('目录不存在', str(p), parent=self.root)
            return
        if sys.platform == 'win32':
            os.startfile(str(p))  # noqa: S606 — explicit user-triggered local folder navigation
        elif sys.platform == 'darwin':
            subprocess.Popen(['open', str(p)])
        else:
            subprocess.Popen(['xdg-open', str(p)])

    def open_settings(self):
        dlg = tk.Toplevel(self.root)
        dlg.title('项目设置')
        dlg.geometry('670x355')
        dlg.configure(bg=BG)
        dlg.transient(self.root)
        dlg.grab_set()
        text_label(dlg, '项目设置', size=16, bold=True, bg=BG).pack(anchor='w', padx=22, pady=(22, 7))
        text_label(dlg, '仅保存路径配置，不会自动移动或覆盖已有技能文件。', bg=BG, color=MUTED).pack(anchor='w', padx=22)
        body = tk.Frame(dlg, bg=BG)
        body.pack(fill='x', padx=22, pady=20)
        def field(title, var, caption):
            text_label(body, title, size=10, bold=True, bg=BG).pack(anchor='w', pady=(9, 5))
            row = tk.Frame(body, bg=BG)
            row.pack(fill='x')
            ent = tk.Entry(row, textvariable=var, bg=WHITE, fg=TEXT, font=(FONT, 10), relief='solid', bd=1)
            ent.pack(side='left', fill='x', expand=True, ipady=7)
            button(row, '浏览…', lambda: var.set(filedialog.askdirectory(parent=dlg) or var.get()), padx=12, pady=6).pack(side='left', padx=(8, 0))
            text_label(body, caption, size=9, color=MUTED, bg=BG).pack(anchor='w', pady=(4, 2))
        field('共用库路径', self.library_text, '推荐使用空文件夹；不要把来源目录直接设为共用库。')
        field('项目根目录（可选）', self.project_text, '可额外发现项目级 Skills；留空只扫描用户级目录。')
        def apply_settings():
            library = self.library_text.get().strip()
            project = self.project_text.get().strip()
            if not library:
                messagebox.showwarning('路径为空', '必须填写共用库路径', parent=dlg)
                return
            if project and not Path(project).is_dir():
                messagebox.showwarning('路径无效', '工程目录必须存在', parent=dlg)
                return
            if (hub.canonical(Path(library)) != hub.canonical(Path(self.config['library']))
                    and self.config.get('managed_links')):
                messagebox.showwarning('需要先撤销链接',
                    '目前仍有本工具管理的共享链接。请先取消这些共享并执行撤销，再更改共用库路径。', parent=dlg)
                return
            self.config['library'] = library
            self.config['project'] = project
            if not self.save_settings():
                return
            dlg.destroy()
            self.rescan()
        bar = tk.Frame(dlg, bg=BG)
        bar.pack(fill='x', padx=22)
        button(bar, '保存并重新扫描', apply_settings, kind='primary').pack(side='right')
        button(bar, '取消', dlg.destroy).pack(side='right', padx=8)
        dlg.bind('<Escape>', lambda _e: dlg.destroy())
        self.root.wait_window(dlg)

    def add_agent(self):
        name = simpledialog.askstring('添加自定义 Agent', '请输入 Agent 名称：', parent=self.root)
        if not name or not name.strip():
            return
        path = filedialog.askdirectory(title=f'选择 {name} 的 Skills 根目录', parent=self.root)
        if not path:
            return
        if any(hub.canonical(Path(a['path'])) == hub.canonical(Path(path)) for a in self.config['custom_agents']):
            messagebox.showwarning('重复路径', '此路径已作为自定义 Agent 添加', parent=self.root)
            return
        self.config['custom_agents'].append({'id': 'custom_' + uuid.uuid4().hex[:10], 'name': name.strip(), 'path': path})
        self.save_settings()
        self._build_target_options()
        self.rescan()

    def configure_agent(self):
        aid = self.current_agent
        if aid == 'all':
            messagebox.showinfo('先选择 Agent', '请先在左侧选择一个 Agent。', parent=self.root)
            return
        if aid.startswith('custom_'):
            messagebox.showinfo('自定义 Agent', '如需更换目录，请先撤销其共享链接，再重新添加该 Agent。', parent=self.root)
            return
        info = registry.BY_ID.get(aid)
        if info is None:
            return
        if any(x.get('agent') == aid for x in self.config.get('managed_links', {}).values()):
            messagebox.showwarning('存在共享链接', '请先撤销此 Agent 的共享，再修改其目录。', parent=self.root)
            return
        path = filedialog.askdirectory(title=f'配置 {info.name} 的实际 Skills 根目录', parent=self.root)
        if not path:
            return
        if not messagebox.askyesno('核对 Skills 目录', f'将 {path}\n用作 {info.name} 的读取和接收共享路径。\n\n请确认该客户端确实使用此目录。继续吗？', parent=self.root):
            return
        self.config.setdefault('agent_paths', {})[aid] = path
        self.save_settings()
        self._build_target_options()
        self.rescan()

    def remove_agent(self):
        aid = self.current_agent
        if not aid.startswith('custom_'):
            messagebox.showinfo('移除自定义 Agent', '请先选择一个自定义 Agent；内置 Agent 不可移除。', parent=self.root)
            return
        if any(x.get('agent') == aid for x in self.config.get('managed_links', {}).values()):
            messagebox.showwarning('存在已管理链接', '请先撤销该 Agent 的共享链接，再移除目录记录。', parent=self.root)
            return
        if not messagebox.askyesno('移除目录记录', '只移除管理器中的自定义 Agent 配置，不删除原文件。继续？', parent=self.root):
            return
        self.config['custom_agents'] = [x for x in self.config['custom_agents'] if x['id'] != aid]
        self.current_agent = 'all'
        self.save_settings()
        self._build_target_options()
        self.rescan()

    def close(self):
        if self.dirty:
            response = messagebox.askyesnocancel('未保存设置', '有尚未保存的共享配置。\n要保存后退出吗？\n（保存不会执行复制或建立链接）', parent=self.root)
            if response is None:
                return
            if response and not self.save_settings():
                return
        self.root.destroy()


def main():
    root = tk.Tk()
    SkillHubGUI(root)
    root.mainloop()


if __name__ == '__main__':
    main()
