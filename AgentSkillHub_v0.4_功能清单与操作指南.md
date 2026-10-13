# Agent Skill Hub v0.4 — 功能清单、UI 改版说明与 Windows 操作指南

> 适用环境：Windows 10 / 11；Python 3.10+（带 Tkinter）；标准库运行，无需联网。
>
> 版本定位：**Fluent 2 风格的技能共享管理器**；延续 v0.3 的 34 个 Agent 条目和安全共享引擎，重新设计桌面 GUI。

## 1. 设计依据与改版方向

目前不存在一种对所有产品、所有人都“公认第一”的 UI 样式。考虑到这是 **Windows 上需要频繁检索、批量选择和预览文件改动的生产力工具**，本版采用：

- **视觉：** Microsoft Fluent 2 启发的布局与间距、低干扰卡片、克制的蓝色主操作按钮、深色导航栏。
- **导航：** 类似常见 IDE 文件管理器的左侧 Agent 导航；中央技能清单；右侧随选择变化的详情面板。
- **交互：** “先选择，再编辑；先暂存，再预览；确认后才执行”。
- **反馈：** 清晰显示当前 Agent、技能数量、共享状态、未保存变更和预览操作总数。

参考资料（设计原则，不表示官方对本产品的认可或排名）：

1. [Microsoft Fluent 2 — Layout](https://fluent2.microsoft.design/layout)：使用间距和接近性建立视觉层级。
2. [Microsoft — Navigation design basics](https://learn.microsoft.com/en-us/windows/apps/design/basics/navigation-basics)：导航应一致、简洁、清楚，避免复杂层级。
3. [Microsoft Fluent 2 — Navigation](https://fluent2.microsoft.design/components/web/react/core/nav/usage/)：高层导航保持易扫读、目标明确。
4. [Nielsen Norman Group — Ten Usability Heuristics](https://www.nngroup.com/articles/ten-usability-heuristics/)：系统状态可见、可撤销、预防错误、识别而非记忆。
5. [Nielsen Norman Group — Complex Applications](https://www.nngroup.com/articles/usability-heuristics-complex-applications/)：复杂应用尤其需要预览、及时反馈和明确后果。

## 2. 完整功能清单

以下区分 **已实现** 与 **尚未实现**，避免将规划功能误认为已支持。

| 模块 | 已实现的功能 | 使用位置 / 说明 |
|---|---|---|
| Agent 导航 | 34 个内置 Agent 条目 + 自定义 Agent | 左侧导航 |
| Agent 搜索 | 按名称或内部 ID 过滤 | 左侧搜索框 |
| Agent 状态 | 显示该 Agent 当前可见的 Skill 数量和有无发现技能 | 左侧名称及数字；有技能≠软件已安装 |
| 全部技能 | 汇总所有扫描到的技能 | 点击左侧 **全部技能** |
| 目录检测 | 13 个已有文档路径的客户端自动扫描；21 个只提供手动配置入口 | 根目录存在才扫描 |
| DeepSeek Harness | 支持 `.dsh/skills` 和 `DSH_HOME` | 自动扫描 / 分享目标 |
| 自定义 Agent | 手动登记名称与目录，并允许其作为共享接收方 | 左下角 **添加 Agent** |
| 移除自定义 | 仅移除目录记录，不删除技能文件 | 左下角 **移除自定义** |
| 修改目录 | 为内置 Agent 指定真实的本地 Skill 根目录 | 左下角 **配置目录** |
| 项目级 Skill | 可额外扫描选定工程中的 Agent Skill 目录 | **设置与路径** |
| 统一共享库 | 自定义共享库路径，例如 `D:\AI-Skills\skills` | **设置与路径** |
| Skill 列表 | 按名称、来源、共享状态显示 | 中央表格 |
| Skill 搜索 | 按技能名/来源过滤，不影响已保存策略 | 中央搜索框；`Ctrl+F` |
| 状态筛选 | 全部、已共享、未共享、有冲突 | 中央筛选按钮 |
| 单项详情 | 描述、文件目录与 Skill 来源 | 选中技能后在右侧显示 |
| 打开源目录 | 打开本地文件夹 | 右侧 **打开技能目录** |
| 定向共享 | 每个 Skill 单独开启/关闭共享、选择接收的 Agent | 右侧 **加入共享库** + 勾选接收方 |
| 接收范围快捷操作 | 全选、清空当前 Skill 的接收方 | 右侧接收方列表顶部 |
| 多选技能 | `Ctrl` / `Shift` 多选 | 中央表格 |
| 批量共享 | 把相同接收范围赋给多项 Skill | 中央底部 **批量设置共享** |
| 批量取消共享 | 对所选技能暂存取消共享策略 | 中央底部 **取消共享** |
| 自动去重 | 对同名同内容 Skill 去重 | 扫描 / 共享引擎 |
| 冲突检测 | 同名异版本、共享库版本冲突、目标目录同名占用 | 表格筛选、预览弹窗 |
| 暂存式编辑 | 勾选后先存入当前 UI 内存，不立即复制或建立链接 | 底部黄色未保存状态 |
| 保存配置 | 保存共享策略与目录记录，不执行文件写入共享操作 | 底部 **保存设置**；`Ctrl+S` |
| 变更预览 | 列出将复制、建立链接、撤销链接的全部操作 | 底部 **预览并执行** |
| 操作统计 | 分别显示新增副本、新增链接、撤销链接、冲突数量 | 预览弹窗上方 |
| 最终确认 | 实际文件改动之前再次确认；有冲突时禁用执行 | 预览弹窗 |
| 安全复制 | 只将缺失的 Skill 复制到共享库，校验文件内容 | 共享引擎 |
| 定向安装 | Windows Junction 连接共享副本与选定 Agent 的 Skill 目录 | 共享引擎 |
| 安全撤销 | 只撤销工具记录且仍指向原位置的链接 | 共享引擎 |
| 原始文件保护 | 不覆盖/删除原始 Skill，不执行 Skill 附带的脚本 | 整体策略 |
| 执行日志 | 查看本次运行期间最近一次执行结果 | 顶部 **查看日志** |
| 命令行兼容 | 保留 `scan` / `merge` / `link` / `sync` | `skill_hub.py` |
| 旧配置兼容 | 继续读取旧版 `settings.json` 的策略和链接管理记录 | 程序启动时 |

### 尚未实现 / 不能保证的能力

- **没有内置 Notion API 自动同步**。Notion 仍需额外集成。
- **不是实时双向同步服务**。修改原始 Skill 后，需要再次处理版本变更；已有共用库文件不会自动覆盖。
- **不是严格的访问权限控制系统**。某些 Agent 会主动读取通用 `.agents/skills`，因此仅选择一个接收方不代表其他 Agent 无法看见它。
- **不会自动探测任意程序安装情况**；左侧“有技能”表示发现可读的 Skill，不是安装检测。
- **未覆盖全部 34 个 Agent 的官方写入路径**。其中 21 个需要手动提供并确认目录，部分产品可能根本不支持本地 `SKILL.md`。
- **没有自动发布为 `.exe`**。使用 Python + Tkinter 和 `.bat` 启动；不需要第三方 pip 包。
- **执行日志只记录本次运行的最近结果**，不是持久化审计历史。

## 3. 新版界面的使用顺序

```text
左侧选择 Agent
   ↓
中间搜索/筛选技能（可 Ctrl / Shift 多选）
   ↓
右侧设置该 Skill 的共享状态和接收 Agent
   ↓
底部保存配置（仅保存策略）
   ↓
预览操作：复制 / 建立链接 / 撤销链接 / 冲突
   ↓
最终确认执行（真正修改文件系统）
```

注意：进入“预览并执行”也会先保存当前策略，以免计划与已保存策略不一致；**仅保存配置不会创建或删除 Skill 文件/链接**。

### 示例：将 Codex Skill 共享给 Claude Code 与 DeepSeek Harness

1. 左侧选择 **Codex**，中央选择 `fpga-verification`。
2. 右侧勾选 **加入共享库**。
3. 接收方只勾选 **Claude Code** 与 **DeepSeek Harness**。
4. 底部会提示存在未保存设置。点击 **预览并执行**。
5. 在弹窗中核对共用库路径、目标 Agent 和计划操作；无冲突时再点击 **确认执行**。
6. 根据需要重启相关 Agent，让其重新发现新增的 Skill。

### 示例：批量共享多项技能

1. 左侧进入 Agent 的技能列表。
2. 按 `Ctrl` 或 `Shift` 多选（Windows 表格标准交互）。
3. 点击中央底部 **批量设置共享**，在弹窗中勾选统一的接收范围。
4. 点击 **确认暂存**；再点击 **预览并执行** 查看每项改动。

### 示例：撤销共享

1. 选择 Skill，取消右侧 **加入共享库**（也可批量取消）。
2. 预览中应出现 **撤销链接**，核对目标后确认。
3. 只撤销仍符合原始管理记录的 Junction/符号链接，不删除共用库副本和原始 Skill。

## 4. 安装与启动（Windows）

1. 将 `AgentSkillHub-Windows-v0.4-Fluent.zip` 解压到例如 `D:\AgentSkillHub`。
2. 安装 Python 3.10 或更高版本，安装时保留 **Tcl/Tk and IDLE** 选项。
3. 双击 `启动图形界面.bat`；或在 PowerShell 中运行：

   ```powershell
   cd D:\AgentSkillHub
   py -3 .\skill-hub\scripts\gui.py
   ```

4. 左下角 **设置与路径** 可修改共享库（推荐 `D:\AI-Skills\skills`）和扫描项目目录。
5. 尽量先选择一个没有敏感信息的普通 Skill，预览后再共享到一个 Agent 测试。

**快捷键：** `Ctrl+F` 搜索 Skill；`Ctrl+S` 保存共享策略；`Ctrl+R` 重新扫描；列表用 `Ctrl/Shift` 多选。

### 安装为 Codex / Claude Code Skill（可选）

这一步不是启动 GUI 的必要条件，只是让 Agent 在自己的 Skill 列表中发现管理器指令。

```powershell
cd D:\AgentSkillHub
.\install.ps1 -Agents codex,claude
.\install.ps1 -Apply -Agents codex,claude
```

PowerShell 脚本默认预览，只有加 `-Apply` 才建立链接。

## 5. 安全边界与升级注意事项

- v0.4 使用与 v0.3 兼容的 `%LOCALAPPDATA%\AgentSkillHub\settings.json`（无 LOCALAPPDATA 时使用用户主目录下的设置文件）。升级前建议备份它及共享库。
- 已有同名文件夹不会被自动覆盖；冲突需由使用者先行处理。
- 扫描时拒绝内部符号链接/目录联接、疑似密钥文件（例如 `.env`、私钥、Token 文件）、超过大小/数量上限的 Skill。
- 更改共用库目录时，如仍有本工具管理的共享链接，界面将要求先撤销链接，避免产生失效引用。
- 即使某 Skill 内容符合安全规则，也应在分享给其他 Agent 之前审查它的指令、依赖、脚本和授权范围。
- 本工具不会执行 Skill 内的脚本，不上传扫描内容，不发送网络请求。

## 6. 测试范围和验收标准

当前执行：

```powershell
cd D:\AgentSkillHub
py -3 -m unittest discover -s tests -v
```

- **18 项单元测试通过**（原有 15 项 + 新增筛选、批量策略和预览统计 3 项）。
- 使用 Linux 虚拟显示环境进行了 GUI 启动、Agent 导航、Skill 选择、共享勾选及截图检查。
- **尚未在你的 Windows 真机、全部 34 个 Agent 客户端及所有实际 Junction 环境中验收。**

建议你完成的真实验收：

1. 左侧能显示 34 个内置条目并能搜索；你原来创建的自定义 Agent 仍在。
2. 点击 Codex、Claude Code、DeepSeek Harness 可以看到预期 Skill（以实际目录为准）。
3. 右侧勾选共享后，底部出现未保存状态；仅“保存设置”时未创建 Junction。
4. 预览列表准确区分复制、链接、撤销，并在冲突发生时禁用执行。
5. 选择 2 个 Skill 批量共享给指定 Agent，然后取消其中 1 个共享，确认原目录未被删除。
6. 重启程序后设置仍可读，已管理链接不会被误删除。
