# Deckestra

Deckestra 是一个独立开发和维护的 PowerPoint Skill，技术 Skill 名固定为
`build-editable-decks`。仓库包含从文本、PDF、Word、论文、表格、已有 PPT 或主题
创建和编辑 PowerPoint 所需的工作流与脚本。

源码包含材料溯源、内容规划、确定性与模板化排版、DrawingML 原生对象导出、渲染
检查、有限修复和发布证据。

## 已包含的工作流

- 从材料或主题新建整套 PPT。
- 在明确要求时保持原文、页数和顺序不变，只重做视觉设计。
- 填充已有原生 PPTX，并尽量保留对象可编辑性。
- 创建可复用的 Brand、Style、Layout 和 Deck 工作区。
- 导出可编辑文本、普通形状、表格、受支持图表、备注和页面转场。
- 用来源 ID、哈希和验证报告绑定最终交付文件。

面向文字型报告和技术简报，主路径采用类型化页面 IR，不让模型逐项手写绝对坐标。
当前覆盖 12 类可编辑页面，最多自动适配 2 次，仍有溢出就整套失败，绝不截断正文；
运行轨迹只保留哈希和几何统计。复杂图片构图、严格模板复刻和原生 PPTX 填充走各自
独立的受控路径。

## v0.1.0 已验证范围

v0.1.0 是首次公开源码版本。自动发布门包含 46 项单元与集成测试。已验证范围包括
12 类确定性布局、这些布局的 SVG 质量零告警检查、重复运行输出一致性、有限溢出
处理、原生表格与图表导出冒烟测试、运行时隐私控制、全部可达 Git 历史扫描、固定
第三方数据检查和全文件来源锁。

本版本不是质量通过率认证。99% 整套完成率仍是未来目标。正式声明必须通过
`zh-cn-tech-brief-15-v1` 冻结评测，包括 1000 套盲测、至少 997 套整份通过、每套
15 页，并由两名独立评审者逐页完整检查。详见
[`certification/`](certification/)。

可选文档转换器、远程图片服务、旁白后端和编辑器集成已包含在源码中，但不属于
v0.1.0 的自动验证结论。

对象级动画创作不包含在 v0.1.0 中：此前所需的 PowerPoint 行为树捕获数据缺少充分
的可再分发来源证明，因此已从公开源码删除。页面切换、确定性 Morph 配对，以及对
已有 PPTX timing XML 的结构保留检查仍然可用。

## 作为本地 Skill 安装

OpenAI 的[官方 Skill 文档](https://learn.chatgpt.com/docs/build-skills)把 Skill
定义为包含 `SKILL.md`，并可附带脚本、参考资料、资源和 `agents/openai.yaml` 的
目录。Python 3.12 是当前已验证的发布环境。

在全新虚拟环境中克隆并验证公开源码：

```bash
git clone https://github.com/sunweitaosnape-lgtm/deckestra.git
python3.12 -m venv deckestra-venv
source deckestra-venv/bin/activate
python -m pip install -r deckestra/skills/build-editable-decks/requirements-maintainer.txt
python deckestra/tools/release_gate.py deckestra --history --require-provenance
cd deckestra
```

虚拟环境特意建在仓库外，因为隐私门禁会拒绝源码树内的运行环境。Windows 请运行
`deckestra-venv\\Scripts\\Activate.ps1` 激活环境；若无法激活，则每条 Python 命令
都使用 `deckestra-venv\\Scripts\\python.exe`。如果只安装已验证核心、不安装维护审计
依赖，请改用 `requirements-core.txt`。

把 `skills/build-editable-decks` 复制到以下任一位置：

| 作用范围 | 目标目录 |
|---|---|
| 当前仓库 | `.agents/skills/build-editable-decks` |
| 当前用户 | `$HOME/.agents/skills/build-editable-decks` |

macOS 或 Linux 的用户级安装命令：

```bash
mkdir -p "$HOME/.agents/skills"
cp -R skills/build-editable-decks "$HOME/.agents/skills/build-editable-decks"
python "$HOME/.agents/skills/build-editable-decks/scripts/attribution_guard.py"
```

Windows 请把同一文件夹复制到
`$HOME\\.agents\\skills\\build-editable-decks`，然后运行
`python $HOME\\.agents\\skills\\build-editable-decks\\scripts\\attribution_guard.py`。

安装确定性排版、验证和原生 PPTX 导出所需的固定核心依赖：

```bash
python -m pip install -r skills/build-editable-decks/requirements-core.txt
```

启动或重启 Codex 时请保持该环境处于激活状态，确保 Skill 脚本使用同一个已验证
解释器；也可以把核心依赖安装到 Codex 实际配置的 Python 解释器中。

只有需要可选的文档转换、图片服务、旁白或编辑器集成时，才安装
`skills/build-editable-decks/requirements.txt`。该清单不属于 v0.1.0 已验证环境，
并包含采用 AGPL/LGPL 许可的软件包。安装前请先阅读
[`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md)。Codex 通常会自动识别 Skill
变化；若未出现，重启 Codex。

GitHub 仓库是可审计的源码发行方式。OpenAI 官方建议在面向更广泛用户分发、或需要
捆绑连接器时再封装为 plugin；这属于后续分发形式，不是当前源码版的隐藏依赖。

## 使用

在 Codex 中用 `$build-editable-decks` 显式调用；在支持独立 Skills 的 ChatGPT
界面中也可以用 `@` 选择。示例：

```text
$build-editable-decks 把这些材料整理成 15 页中文技术简报，保留数据来源，表格和图表必须可编辑。

$build-editable-decks 把这篇论文改写成面向管理层的 12 页技术汇报。

$build-editable-decks 美化这个 PPTX，但不要修改原文、页数和顺序。
```

Skill 会明确选择四条路径之一：新建 PPT、创建可复用模板、填充原生 PPTX、增强原生
PPTX。所有运行项目都必须创建在已安装 Skill 目录之外。

## 隐私边界

公开源码不得包含用户文档、上传图片、真实业务 PPT、渲染图、音频、运行日志或私有
评测案例。测试只使用合成文本和程序生成的结构化测试数据。

发布门会检查文件名、文件魔数、嵌入位图、凭证、私有链接、本机路径、来源登记和
全部可达 Git 历史。盲测题目、逐页渲染、评审和证据始终留在仓库外。运行时默认本地
处理；只有用户明确要求依赖外部服务的功能时才调用外部提供方。远程参考图编辑还必
须额外提供 `--allow-remote-reference-upload`；远端提供方回执只记录哈希和计数，不
打印提示词正文、参考输入路径、签名 URL 或响应正文。普通本地 CLI 可以显示写入用户
项目内的目标文件路径。

详见 [`PRIVACY.md`](PRIVACY.md) 和 [`SECURITY.md`](SECURITY.md)。

## 开发与发布门

安装固定版本的维护依赖，并通过唯一的只读入口执行完整检查：

```bash
python -m pip install -r skills/build-editable-decks/requirements-maintainer.txt
python tools/release_gate.py . --history --require-provenance
```

上述完整门禁是首次公开源码版本的发布门。GitHub Actions 会在每次 push 和 pull
request 时运行同一命令。私有 1000 例盲测不阻塞 v0.1.0，也不会因此跳过或降低隐私、
来源、许可证、身份、语法、测试及提示词审计。

未来冻结盲测通过后，可以在仓库之外生成单独的认证源码包：

```bash
python tools/build_release.py . \
  --output /tmp/deckestra-source.zip \
  --certification-evidence /absolute/external/certification-runs/evidence.json
```

构建器会拒绝仓库内路径、已有目标文件、缺失来源锁、被禁止的可达历史证据或未完成
的盲测认证。它生成字节可复现的 ZIP，解包到临时目录，再对该副本重跑完整发布门和
认证门。

参与开发前请阅读 [`CONTRIBUTING.md`](CONTRIBUTING.md)。真实案例、截图、上传媒体
和私有测试数据永远不能作为贡献内容。

## 许可与来源

Deckestra 源码使用 MIT License。部分转换和工作流组件包含或改编自 MIT 许可的
`hugohe3/ppt-master`，完整许可文本保存在
`third_party/ppt-master/MIT.txt`。固定版本的 Apache POI 与 Open XML SDK 数据保留
各自许可和来源说明。单独安装的 Python 依赖继续适用各自许可证，其中包含
[`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md)列明的 copyleft 条款。
Deckestra 与上游项目不存在官方或背书关系。
