# Implementation status

30 September 2026. This is the status against the original planning documents. Those documents are preserved as planning history; their statements about implementation not having started are no longer current.

## Implemented

- Local Python CLI, FastAPI workbench and SQLite storage.
- Attributed discovery from Shopify editorials, a pinned public domain list and a public India directory. Bounded Common Crawl CDX and saved-record adapters are available but were not sources for this result.
- Live Shopify and Indian business-address checks, field extraction, evidence snapshots, strict robots handling and host rate limits.
- One bounded enrichment pass, compressed content-addressed cache, durable pause/resume and offline replay.
- Identity deduplication, evidence-bound review notes, freshness checks, matching CSV/JSON exports, source attribution and snapshot checksums.
- Responsive Rivyou-themed UI: store explorer, search/filters, evidence, fetch history, sources, completeness, import, collection controls and downloads.
- Repeatable batch driver and a separate submission-file validator.
- Unit/integration tests and repeated isolated browser workflow checks. See UI_QA.md.

## Data delivery

The submitted snapshot has **1,033 accepted stores from 2,339 candidates**, snapshot `96232f7c659ca586`. The result files are `outputs/stores.csv` and `outputs/stores.json`. The README contains final missingness and timing tables. A 30-store agent review and 27 targeted address reviews are documented in `docs/DATA_REVIEW.md`. No candidate remains queued and no collection is active.

The broader pilot is complete: 288 new candidates, 124 initial automated accepts before deduplication/enrichment, in 519.5 seconds. Saved reports in `data/discovery/` document the measured source and pilot decisions. The expanded batches used these findings; their actual run history is included in the final report.

## Changes from the plan

- A large Common Crawl Parquet scan was replaced by a measurable public-list source. The broad Parquet scanner was not built, and no Common Crawl contribution is claimed.
- The UI was built alongside the first complete pipeline path because the user explicitly requested it.
- The original 2 MiB page cap excluded genuine storefronts. Expanded runs use 8 MiB and record the actual limit in run history.
- A follow-up for every review was wasteful: none of 50 unconfirmed/conflicting Shopify reviews became accepted in the measured pass. Subsequent enrichment targets confirmed Shopify sites missing India proof and unreachable homepages.
- Offline replay applies the final extraction rules to saved evidence without renewing observation dates.

## Remaining boundaries

- The public GitHub repo and read-only snapshot viewer are published. The crawler and review workbench still run locally; `render.yaml` and `vercel.json` prepare the viewer for those static hosts.
- The automated result and any agent spot-check are not an independent human accuracy audit. The audit sample remains available for one.
- No WHOIS/RDAP, OCR, browser-rendered merchant crawl, government address lookup or AI classifier is used. No Supabase or AI key is required.
- The app is local, single-user and unauthenticated. Its server binds to loopback.
- Seven-day freshness is fixed in the result projection. The user agent has a descriptive name but no invented operator contact.
- Third-party pages can change, block requests or omit fields. Those cases remain visible rather than becoming invented values.
