# 撤稿校准 / Retraction Calibration

目标是用已经撤稿的论文作为回顾性校准案例，让 `耿同学.skill` 的信号提取更接近专家复核结果。

The goal is to make `耿同学.skill` closer to expert review by using already retracted papers as retrospective calibration cases.

在对齐步骤之前，流程必须保持盲法：

The process must stay blind until the alignment step:

```text
1. Import the retracted paper DOI.
   导入已撤稿论文 DOI。
2. Discover available materials and read existing algorithmic signals.
   发现可用材料，并读取已有算法信号。
3. Do not register or read the official retraction reason during the blind pass.
   盲法阶段不登记、不读取官方撤稿原因。
4. Load the official retraction notice as the calibration label.
   盲法结束后，把官方撤稿通知作为校准标签。
5. Compare blind signal groups with official reason groups.
   将盲提取信号族与官方原因族对齐。
6. Classify every miss as a material gap, extraction gap, analyzer gap, or unsupported signal family.
   将每个未匹配项归类为材料缺口、抽取缺口、分析器缺口或暂不支持的信号族。
```

Run against the local API:

对本地 API 运行：

```bash
python3 scripts/run_retraction_calibration.py --base-url http://127.0.0.1:8010 --limit 5
```

Optionally inspect publisher/PMC landing pages:

可选：检查 publisher/PMC landing page：

```bash
python3 scripts/run_retraction_calibration.py \
  --base-url http://127.0.0.1:8010 \
  --limit 10 \
  --inspect-landing-pages
```

For image-heavy retractions, fetch linked PDFs, extract embedded images as `figure_image` artifacts and run image audits before alignment:

对图像问题较多的撤稿案例，在对齐前抓取关联 PDF、把嵌入图片抽取为 `figure_image` artifact，并运行图像审计：

```bash
python3 scripts/run_retraction_calibration.py \
  --base-url http://127.0.0.1:8010 \
  --limit 5 \
  --inspect-landing-pages \
  --fetch-pdfs \
  --fetch-images \
  --extract-pdf-images \
  --run-image-audits \
  --max-image-artifacts 12
```

By default, batch image audit uses faster hash/patch checks. Add `--deep-image-audits` only for smaller focused runs that need slower shift-correlation checks.

默认批量图像审计使用较快的 hash/patch 检查。只有在较小、聚焦的运行中需要更慢的 shift-correlation 检查时，才添加 `--deep-image-audits`。

If Crossref starts rate-limiting a large calibration batch, use OpenAlex-only metadata import and rely on the official notice fields in the seed file for labels:

如果 Crossref 对大批量校准限流，可以只用 OpenAlex 导入元数据，并依赖 seed 文件中的 official notice 字段作为标签：

```bash
python3 scripts/run_retraction_calibration.py \
  --base-url http://127.0.0.1:8010 \
  --limit 20 \
  --metadata-sources openalex \
  --inspect-landing-pages \
  --fetch-images \
  --run-image-audits
```

If a trusted local proxy or DNS layer maps public hosts such as `pmc.ncbi.nlm.nih.gov` to `198.18.x.x`, start the temporary calibration API with `ARTIFACT_FETCH_ALLOW_PRIVATE_NETWORKS=1`. Keep the default block enabled for normal deployments.

如果可信本地代理或 DNS 层把 `pmc.ncbi.nlm.nih.gov` 等公网 host 映射到 `198.18.x.x`，可以用 `ARTIFACT_FETCH_ALLOW_PRIVATE_NETWORKS=1` 启动临时校准 API。正常部署应保持默认阻断。

Only after blind alignment, record official notices into the local database:

只有完成盲法对齐之后，才把官方通知记录到本地数据库：

```bash
python3 scripts/run_retraction_calibration.py \
  --base-url http://127.0.0.1:8010 \
  --limit 20 \
  --record-official-events
```

## 案例数据 / Case Data

The seed cases live in:

Seed case 存放位置：

```text
data/seeds/retraction_calibration_cases.json
```

Each case stores:

- original article DOI / 原始论文 DOI；
- title hint / 标题提示；
- official notice URL and notice DOI / 官方通知 URL 和通知 DOI；
- optional public mirror URL for easier manual reading / 便于人工阅读的可选公开镜像 URL；
- short paraphrased official reason summary / 简短转述的官方原因摘要；
- structured reason categories / 结构化原因类别。

The first seed set contains at least 20 official retraction cases and intentionally emphasizes image/data-integrity retractions because those map most directly to the current numeric and image analyzers.

第一批 seed 至少包含 20 个官方撤稿案例，并有意强调图像和数据完整性撤稿，因为这些原因最能映射到当前 numeric 和 image analyzer。

The offline test suite guards seed quality: case IDs, original DOIs and notice DOIs must be unique, reason categories must map to a known calibration family, and every seeded DOI must keep a title hint containing expected DOI-specific title terms. This prevents calibration drift from accidental DOI/title mismatches.

离线测试会保护 seed 质量：case ID、原始 DOI 和通知 DOI 必须唯一，原因类别必须映射到已知校准族，每个 seed DOI 的 title hint 必须包含该 DOI 预期的标题关键词。这可以避免 DOI/title 错配导致校准漂移。

## 当前基线 / Current Baseline

The current 20-case calibration batch was rerun on 2026-05-24 against a clean temporary SQLite database with:

当前 20 篇案例校准批次于 2026-05-24 在干净的临时 SQLite 数据库上重新运行，命令如下：

```bash
python3 scripts/run_retraction_calibration.py \
  --base-url http://127.0.0.1:8012 \
  --limit 20 \
  --metadata-sources openalex \
  --inspect-landing-pages \
  --fetch-images \
  --run-image-audits \
  --max-image-artifacts 8 \
  --min-completed-cases 20 \
  --min-matched-cases 18 \
  --max-analyzer-gap 2
```

Observed result after adding PMC article-page prioritization, HTML image-source discovery, multi-scale same-figure internal patch similarity detection and running internal-only audits for the final image artifact in each case:

加入 PMC article-page 优先、HTML image-source 发现、多尺度同图内部 patch 相似性检测，并对每个 case 的最终 image artifact 运行 internal-only audit 后，观察结果如下：

- `20/20` cases completed / `20/20` 案例完成。
- Prefix checkpoints from the same ordered run: `5/5`, `9/10`, `18/20` cases matched at least one official reason family by blind algorithmic signal / 同一有序运行的 prefix checkpoint 为 `5/5`、`9/10`、`18/20`。
- `18/20` cases matched at least one official reason family by blind algorithmic signal / `18/20` 案例至少有一个盲提取算法信号族匹配官方原因族。
- Status counts / 状态计数：`matched_by_blind_signal=18`, `analyzer_gap=2`, `material_gap=6`, `covered_by_primary_signal=17`, `context_label_only=2`, `unsupported_signal_family=1`.
- The dominant remaining blockers are true data-material gaps for data-irregularity/raw-data/reproducibility labels, one table/primer consistency family without an analyzer, and two image analyzer misses where figure images were available but no signal fired / 主要剩余阻塞是 data-irregularity/raw-data/reproducibility 标签对应的真实材料缺口，一个 table/primer consistency 信号族尚无 analyzer，以及两个已有 figure image 但 analyzer 未触发的图像缺口。

Use the threshold flags above for a nightly or manual live regression gate. The script exits non-zero when the batch fails to complete, matched cases drop below the current baseline or analyzer gaps exceed the current baseline.

上述 threshold flag 可用于 nightly 或手动 live regression gate。当批次未完成、匹配案例低于当前基线，或 analyzer gap 超过当前基线时，脚本会以非零状态退出。

The live 20-case run performs DOI import, landing-page inspection, remote image fetches and image audits, so it can take minutes and depends on publisher/PMC/network behavior. Keep ordinary pull-request CI on offline tests and seed-quality checks; run the live calibration gate manually or on a scheduled job with a temporary local API and cached artifacts.

20 篇 live run 会执行 DOI 导入、landing-page 检查、远程图片抓取和图像审计，因此可能耗时数分钟，并依赖 publisher/PMC/network 行为。普通 PR CI 应保持为离线测试和 seed 质量检查；live calibration gate 适合手动运行，或用临时本地 API 与缓存 artifact 定时运行。

## 对齐状态 / Alignment Status

- `matched_by_blind_signal`: an existing analyzer produced a signal in the same family as the official reason.
- `material_gap`: the needed auditable material was not discovered.
- `extraction_gap`: PDF or landing material was found, but figure/table/source-data extraction is missing.
- `material ops`: runtime counts for successfully fetched PDFs, extracted PDF images, image-audit signals and operation errors during the blind pass.
- `analyzer_gap`: relevant auditable material was found, but no matching signal fired.
- `covered_by_primary_signal`: an official reliability conclusion such as `data_unreliable` is downstream of an image/data/table concern already matched by a blind signal.
- `context_label_only`: an official reliability conclusion is present, but no primary evidence signal fired; improve primary analyzers rather than counting this as missing source-data material.
- `unsupported_signal_family`: the reason category has no analyzer family yet, such as primer/table consistency.

## 边界 / Boundary

This calibration workflow evaluates recall against official retrospective labels. It must not be presented as an independent misconduct classifier.

这个校准流程是用官方回顾性标签评估召回率。它不能被表述为独立的 misconduct 分类器。
