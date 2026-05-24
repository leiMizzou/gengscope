# 工作流一图看懂 / Workflow Overview

这张图说明 `耿同学.skill / GengScope` 的核心机制：agent 只是入口，真正的导入、材料发现、信号提取和报告生成由本地 GengScope engine 完成。

![GengScope workflow overview](assets/gengscope-workflow.svg)

## 中文说明

1. 使用入口：Codex 安装 `skills/gengscope`，Claude Code 使用 `.claude/skills/gengscope/SKILL.md`。
2. 本地引擎：两种入口都调用同一个 `gengscope` CLI 或 `http://127.0.0.1:8010/` API。
3. 导入与建库：从 DOI、作者、机构、实验室或本地名单开始。
4. 材料发现：寻找 PDF、PMC 页面、landing page、source data、figure image 等可审计材料。
5. 信号提取：运行 numeric、image、metadata analyzer，并记录公开事件和官方状态。
6. 复核与校准：把信号族、证据位置和官方状态分开呈现，撤稿校准只在 blind pass 后读取官方原因。
7. 输出：生成 risk card、agent summary、entity report、calibration notes、复核摘要和归档报告。

核心边界：GengScope 输出的是公开状态、材料覆盖率和算法审计信号，用于人工复核优先级排序；不能直接据此认定论文、作者或机构造假。

## English Summary

1. Entry: Codex installs `skills/gengscope`; Claude Code uses `.claude/skills/gengscope/SKILL.md`.
2. Engine: both entrypoints call the same `gengscope` CLI or `http://127.0.0.1:8010/` API.
3. Import and corpus build: start from a DOI, author, institution, lab or local entity list.
4. Material discovery: find PDFs, PMC pages, landing pages, source data and figure images.
5. Signal extraction: run numeric, image and metadata analyzers while recording public events and official statuses.
6. Review and calibration: keep signal families, evidence pointers and official statuses separate. Retraction calibration reads official reasons only after the blind pass.
7. Output: produce risk cards, agent summaries, entity reports, calibration notes, review notes and archived reports.

Boundary: GengScope outputs public statuses, material coverage and algorithmic review signals for human review priority. These records do not by themselves prove misconduct.
