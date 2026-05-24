# Retraction Calibration Social Drafts

Use these drafts after the updated code and docs are public. Replace the repository URL with the final release or demo URL if needed.

## 小红书

标题备选：

- 我们用 20 篇已撤稿论文反向校准了耿同学.skill
- 让科研完整性审计更接近专家判断：20 篇撤稿论文校准

正文：

这次把 GengScope / 耿同学.skill 的撤稿校准流程跑通并开放了。

方法是先不看撤稿原因，只导入已撤稿论文，发现公开 PDF、PMC 页面、figure image、source data 等材料，然后让系统做盲信号提取。等 blind pass 完成后，再回看官方撤稿通知，把系统信号族和官方原因做对齐。

这轮 20 篇案例的结果：

- 20/20 完成
- 18/20 至少有一个盲信号族对齐官方撤稿原因
- 5/10/20 checkpoint 分别是 5/5、9/10、18/20
- 剩余主要缺口是 source data/raw data 材料发现、表格/primer 一致性检查，以及少数图像 analyzer gap

这个结果不是“自动判定造假”。它的意义是：用已经有官方结论的历史案例，反过来校准系统的审计信号，让工具更像专家那样帮助排序、定位和复核。

代码、数据种子、校准脚本和文档已经同步到 GitHub：
https://github.com/leiMizzou/gengscope

关键词：
#科研诚信 #论文审计 #撤稿 #开源工具 #AI科研工具 #GengScope #耿同学skill

## Twitter / X

Short version:

GengScope / 耿同学.skill now has a 20-case retraction calibration workflow.

Blind pass first: import papers, discover materials, run signal extraction.
Only then align with official retraction reasons.

Latest gate: 20/20 completed, 18/20 matched by blind signal family.

https://github.com/leiMizzou/gengscope

Thread version:

1/ We added a retrospective retraction calibration workflow to GengScope / 耿同学.skill.

The goal is not to label misconduct. The goal is to make review signals closer to expert triage by learning from already retracted papers.

2/ The workflow stays blind first:

- import the retracted article
- discover PDFs, PMC pages, figures and source materials
- run numeric/image/metadata signal extraction
- do not read the official retraction reason yet

3/ After the blind pass, the script loads the official retraction notice and aligns reason families with signal families.

Current 20-case gate:

- 20/20 completed
- 18/20 matched at least one official reason family
- checkpoints: 5/5, 9/10, 18/20

4/ Remaining gaps are useful engineering targets:

- source/raw data discovery
- table and primer consistency checks
- a small number of image analyzer misses

Code and docs:
https://github.com/leiMizzou/gengscope

## 微信公众号

标题备选：

- 用 20 篇已撤稿论文校准科研完整性审计信号
- 耿同学.skill 更新：撤稿论文盲检校准流程开放

正文：

这次更新的核心，是给 GengScope / 耿同学.skill 加入了一套“撤稿校准”流程。

我们选择一批已经被期刊正式撤稿的论文，但在第一步不读取撤稿原因。系统先导入 DOI，发现公开材料，例如出版社页面、PMC 页面、PDF、figure image、source data 或 supplementary 文件，然后运行现有的信号提取器，包括图像相似、局部 patch 复用、数值异常和元数据聚类等。

只有在这个 blind pass 完成之后，流程才读取官方撤稿通知，并把官方原因归入结构化原因族，例如 image duplication、image overlap、raw data unavailable、data unreliable、table inconsistency 等。最后，系统比较盲检信号族和官方原因族是否对齐。

最新一轮 20 篇案例的结果如下：

- 20/20 案例完成；
- 18/20 案例至少有一个盲检信号族对齐官方撤稿原因；
- 5/10/20 前缀 checkpoint 分别为 5/5、9/10、18/20；
- 剩余缺口主要来自 source data/raw data 材料发现、表格/primer 一致性检查，以及少数图像 analyzer gap。

这套流程的目的不是自动判定论文造假。它的作用是用已经有官方结论的历史案例校准工具，让系统更好地服务于人工复核：先定位材料，提取可解释信号，再把信号和官方原因做回顾性对齐。

这也给下一步开发提供了清晰方向：补充 source data 和 raw data 的发现能力，增加表格/primer 一致性检查，继续调优图像类 analyzer。相比单纯堆更多模型判断，这种方式更容易形成可追溯、可回归测试、可解释的审计流程。

代码、校准案例、脚本和文档已开放：

https://github.com/leiMizzou/gengscope

结论边界：

GengScope 输出的是公开状态、材料覆盖和算法审计信号，用于人工复核优先级排序。除非期刊、机构、监管部门或作者公开确认，否则这些信号不能被当作论文、作者或机构存在学术不端的结论。
