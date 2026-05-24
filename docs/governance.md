# Governance

## 1. Legal and Ethical Position

This platform is an index and evidence-location tool. It is not an adjudication body.

Core language:

- “公开质疑”
- “公开讨论”
- “机构调查”
- “期刊更正”
- “撤稿”
- “算法异常信号”
- “需要人工复核”

Avoid:

- “造假”
- “实锤”
- “黑榜”
- “骗子”
- “劣迹机构”

Use “造假” only when quoting an official source that explicitly uses equivalent language, and still attribute it to the source.

## 2. Source Hierarchy

Highest confidence:

- Publisher retraction notice.
- Publisher correction.
- Expression of concern.
- Institution official conclusion.
- Court/regulatory document.

Medium confidence:

- Institution investigation notice.
- Publisher editor note.
- Author correction statement.

Lower confidence:

- PubPeer discussion.
- Media reporting.
- Social media posts.
- Algorithmic detection.

## 3. Correction and Dispute Process

Every public event page should support:

- Report incorrect metadata.
- Submit missing official source.
- Request correction of summary.
- Mark event as disputed.

Admin decisions:

- Must be logged.
- Must preserve previous value in audit history.
- Must mark superseded events instead of deleting when possible.

## 4. Ranking Policy

Do not build a simple “institution fraud ranking”.

Allowed metrics:

- Total papers.
- Official event count.
- Public discussion count.
- Algorithmic signal count.
- Per-1000-paper official event rate.
- Field-normalized event rate.
- Year-normalized event rate.

Metrics must show denominator and methodology.

## 5. Privacy Policy

The platform may store:

- Public author names from papers.
- Public affiliations.
- ORCID/OpenAlex author IDs.
- Public official notices.

The platform should not store:

- Personal phone numbers.
- Private emails not part of publication metadata.
- Home addresses.
- Social media personal profiles unless directly relevant and public official source.

## 6. Copyright Policy

Default:

- Store metadata and links.
- Store checksums and derived analysis.
- Store small evidence snippets only when legally permitted.

Avoid:

- Bulk storing publisher PDFs without permission.
- Replicating full articles.
- Copying large PubPeer comment bodies.
- Reposting copyrighted figures publicly.

## 7. Review Levels

```text
level_0_unreviewed
level_1_source_link_verified
level_2_metadata_verified
level_3_evidence_pointer_verified
level_4_official_status_verified
```

Public pages should display review level.

## 8. Audit Logs

Log:

- Who created an event.
- Who edited a summary.
- Source URL changes.
- Status changes.
- Review decisions.
- Corpus builds, artifact uploads/discovery, audit runs and report exports.
- Deletions or hidden records.

Do not silently change event meaning.

The local API supports optional API key protection through `GENGSCOPE_API_KEY` or `GENGSCOPE_API_KEYS`. When enabled, clients must send `X-API-Key`, `X-GengScope-API-Key` or a bearer token for `/api/*` calls. API keys protect local access only; they are not a substitute for network isolation, TLS and role-based controls in a shared deployment.
