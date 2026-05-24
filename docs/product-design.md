# Product Design

## 1. Product Name

GengScope

中文可称为：耿同学科研索引 / 耿同学论文索引。

GengScope 保留“耿同学”的记忆点，同时用 Scope 表达观察、审视和证据范围。产品定位是索引、证据定位和状态追踪，不是舆论审判。

对外发布时应注明：GengScope 是独立项目，名字灵感来自公开科研完整性讨论，不代表任何个人或第三方官方授权。

## 2. Target Users

### Primary Users

- 科研诚信研究者：需要追踪撤稿、更正、关注表达和机构调查。
- 期刊编辑和审稿人：需要快速查看作者、机构、论文是否有公开风险信号。
- 高校和科研机构管理部门：需要监控本机构论文的公开事件和更正状态。
- 科研媒体和调查记者：需要可引用、可溯源的事实索引。
- AI agent 用户：希望让 Codex / Claude Code 查询 DOI、作者、机构并生成审计报告。

### Secondary Users

- 普通读者：查看某篇论文的官方状态。
- 研究生和合作作者：在投稿、合作、引用前做基础风险排查。

## 3. Product Boundaries

平台做：

- 收集公开论文元数据。
- 统一作者、机构、期刊、DOI、年份、领域。
- 聚合公开事件：撤稿、更正、关注表达、机构通报、媒体报道、PubPeer 讨论。
- 保存算法发现的异常信号，并明确标注为 algorithmic_signal。
- 定位证据：图号、表号、source data 文件、supplementary 文件、数据列、图片 panel。
- 以作者、机构、实验室或本地名单为入口构建论文全库，并展示可审计覆盖率。
- 提供机构、作者、论文、事件检索。
- 提供本地 HTTP agent 查询 API。

平台不做：

- 不直接判定“造假”。
- 不把未经官方确认的疑点写成事实结论。
- 不做简单粗暴的高校黑榜。
- 不复制受版权或平台条款限制的大段评论、论文正文或图片。
- 不公开个人隐私信息，不做超出论文署名和机构公开信息之外的人肉化聚合。

## 4. Core Objects

### Paper

论文是平台核心对象。每篇论文以 DOI 为主键，OpenAlex ID、PMID、PMCID、arXiv ID 作为辅助标识。

### Author

作者需要保留原始署名和规范化作者实体。第一版不要追求完美消歧，先做到同一 DOI 内署名准确、跨论文弱关联可人工修正。

### Institution

机构使用 ROR 和 OpenAlex institution ID 做规范化。中文机构需要保留原始 affiliation 文本。

### Integrity Event

完整性事件包括官方撤稿、更正、关注表达、机构调查、机构结论、PubPeer 讨论、媒体报道、人工录入线索。

### Evidence Pointer

证据定位对象。用于指向具体图、表、文件、列、图片区域、URL 和截图哈希。

### Algorithmic Signal

算法信号是机器初筛结果。必须和官方事件分开，不参与事实定性。

## 5. Main Pages

### 5.1 Search

支持输入：

- DOI
- 论文标题
- 作者名
- 机构名
- 期刊名
- 年份范围
- 事件类型
- 官方状态
- 领域

搜索结果展示：

- 标题、期刊、年份、DOI
- 中国机构参与情况
- 通讯作者和第一作者
- 风险状态徽标
- 最近事件
- 是否有 source data / supplementary

### 5.2 Paper Detail

论文详情页是平台最重要页面。

模块：

- 基础信息：标题、期刊、年份、DOI、链接、摘要、主题。
- 作者与机构：作者顺序、通讯作者、原始 affiliation、规范化机构。
- 公开状态：撤稿、更正、关注表达、机构调查、媒体报道、PubPeer 讨论。
- 事件时间线：按日期展示事件来源和状态变化。
- 证据定位：图号、表号、source data 文件、列名、图片 panel、截图。
- 算法信号：数值异常、图片重复、元数据异常。
- 结论边界：明确区分官方结论、公开质疑、算法初筛。

### 5.3 Institution Detail

机构页展示：

- 机构基础信息：名称、别名、ROR、OpenAlex ID、国家、城市。
- 总论文数。
- 涉及中国机构论文数。
- 官方更正/撤稿/关注表达数量。
- 公开讨论信号数量。
- 算法初筛数量。
- 按年份、期刊、学科、事件类型拆分。
- 代表性事件时间线。

机构页禁止默认按绝对事件数量做“排名”。如果需要比较，必须提供归一化口径：

- 每千篇论文官方事件数。
- 按学科和年份归一化后的事件比例。
- 只比较同一学科、同一时间窗口内机构。

### 5.4 Author Detail

作者页展示：

- 署名变体。
- 关联机构。
- 论文列表。
- 通讯作者/第一作者论文。
- 公开事件。
- 共同作者网络。

第一版作者消歧要保守。跨机构、同名作者默认不合并，除非有 ORCID、OpenAlex author ID 或人工确认。

### 5.5 Review Workbench

给人工审查员使用。

功能：

- 认领待复核算法信号。
- 查看 source data 表格。
- 查看图片 panel 对比。
- 标注是否为误报、待确认、应生成事件草稿。
- 为每个判断添加证据链接。

### 5.6 Agent API Console

给 Codex / Claude Code / 脚本 / CI 使用。

功能：

- 输入 DOI，返回 paper risk card。
- 输入机构，返回机构概览。
- 输入作者，返回候选作者列表。
- 输入作者或机构，构建本地论文库。
- 返回可审计覆盖率、审计队列和实体风险画像。
- 输入论文列表，批量生成风险摘要。
- 输出 JSON，方便 agent 进一步生成报告。

## 6. Event Status Design

事件的事实层级从高到低：

```text
official_retraction
official_correction
official_expression_of_concern
institution_conclusion
institution_investigation
publisher_notice
public_discussion
media_report
algorithmic_signal
manual_review_needed
```

每个事件必须有：

- source_url
- source_type
- captured_at
- event_date
- claim_summary
- status_level
- verification_status

`claim_summary` 只能总结来源说了什么，不能扩大解释。

## 7. Risk Card

每篇论文生成一个 risk card：

```json
{
  "doi": "10.xxxx/yyyy",
  "title": "...",
  "official_status": "none | corrected | retracted | expression_of_concern",
  "institution_status": "none | investigation | conclusion",
  "public_discussion_count": 0,
  "algorithmic_signal_count": 0,
  "highest_signal_level": "none | low | medium | high | official",
  "summary": "存在公开讨论，但无官方结论。",
  "evidence": []
}
```

风险卡片默认语气：

- “存在公开质疑”
- “存在算法异常信号”
- “期刊已发布更正”
- “机构已启动调查”
- “尚未发现官方结论”

禁止语气：

- “这篇论文造假”
- “该作者造假”
- “该机构造假严重”
- “实锤”

## 8. MVP Product

第一版优先做 entity-driven local API：

1. 作者/机构搜索。
2. 基于作者/机构构建本地论文库。
3. 标记每篇论文的材料状态：metadata only、landing page、PDF、source data、fully auditable。
4. 生成实体画像：论文数、可审计数、已审计数、异常信号数、官方事件数。
5. 为可审计论文创建 review queue。
6. 保留 DOI 检索、论文详情、事件录入和 risk card。
7. 提供本地 HTTP API 和简洁 workbench，不把 MCP 作为核心服务。

不在 MVP 做：

- 全自动图片审计。
- 大规模 PDF 抓取。
- 高校排名。
- 用户评论区。
- 复杂作者消歧。
