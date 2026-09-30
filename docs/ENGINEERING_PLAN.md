# How we will build it

Planning revision: 29 September 2026. Read this alongside `PRODUCT_REQUIREMENTS.md`. These are implementation decisions and experiments to run; no code or store collection has started.

## Start with the uncertain part

The hardest part is getting enough useful candidate domains. Extracting a footer from one site is straightforward compared with finding thousands of relevant sites without buying a list or overloading a service.

The first draft assumed that Common Crawl would provide enough candidates. That is still a hypothesis. Its URL Index tells us which URLs were crawled; it does not contain a ready-made list of verified Indian Shopify businesses. We need to measure its yield before choosing it as the main source.

Use a short source investigation, then build one complete path from candidate to evidence-backed output. Avoid building several discovery adapters before any of them have shown useful yield.

## Discovery sources and what is established

| Source | What it can provide | What remains to check |
| --- | --- | --- |
| [Common Crawl URL Index](https://commoncrawl.org/url-index) | Public URL records and crawl metadata in Parquet; documented fields allow host and path filtering. | Local scan size, time, candidate quality, and how many useful hosts are new after deduplication. |
| [Common Crawl CDX service](https://index.commoncrawl.org/) | Targeted URL lookups for a known domain or narrow prefix. | Service availability and an appropriately small query scope. The service explicitly directs bulk filtering toward the URL Index. |
| [Shopify's VAHDAM case study](https://www.shopify.com/in/case-studies/vahdam) and related first-party case studies | Named candidate brands and useful examples for initial investigation. | Current platform, current merchant location, correct regional storefront, and live domain. A historical case study is not current verification. |
| Manual search results | Leads on Indian brands using `.com` and on less common categories. | Reproducible query log and source URLs. Search snippets cannot become final evidence. |
| Other public brand directories or repositories | Potential additional candidate lists. | None has yet been selected or validated for this project. Record the exact source and reuse terms before relying on one. |

Free access is different from free computation. The URL Index can be processed locally, but a broad scan may still use substantial bandwidth, disk, and time. Athena is a paid alternative and is outside the default local plan. Publicly viewable directories are not automatically licensed for bulk redistribution.

For the first source experiment, select and record one recent available crawl from Common Crawl's published catalog. Read only the needed columns. Filter to successful HTML records with store-like paths under `.in`, group by host, then sample the resulting hosts. Paths such as `/products/` and `/collections/` are useful leads but occur on other platforms too. Run a separate, bounded experiment on `myshopify.com` hosts; a global sweep could have very poor India yield.

The selected partition, file list, query, sample seed, downloaded bytes, and elapsed time must be recorded. A `LIMIT` clause is not a guarantee that a Parquet query scans little data. Stop the first experiment at two hours or 5 GB transferred, whichever comes first, and examine the results before extending it. Those are proposed local experiment limits, not measured resource needs.

For search expansion, log queries that combine a category or city with commerce/Shopify clues. Include `.com` domains. Manual search or a permitted official API is acceptable; do not make automated search-page scraping an undeclared dependency.

## The pilot

First inspect about 30 candidates by hand to learn the page patterns. Include apparent positives, negatives, and awkward cases. Any labels created here belong to the development set and cannot double as the final accuracy sample.

Next run the first implementation on 300 unique candidates, ideally about 100 from each of three source routes when available. Keep each source's yield separate; hand-selected case studies will otherwise make the discovery method look better than it is.

For each source, count discovered hosts, new hosts after deduplication, reachable sites, Shopify passes, India passes, accepted stores, unresolved stores, and requests used. Report both accepted stores per candidate and accepted stores per 1,000 requests. A duplicate discovered through another source is not a new store.

| Overall acceptance yield | Unique candidates needed for 1,000 stores, before further losses |
| --- | --- |
| 20% | About 5,000 |
| 40% | About 2,500 |
| 60% | About 1,667 |

These are arithmetic scenarios, not predictions. The next batch can have a different yield. Use the actual pilot to choose the next source and estimate work. If new batches mostly repeat existing domains, measure the marginal yield and change source rather than repeatedly crawling duplicates.

## Keep the local design small

Use Python, one SQLite database, and files for the cache and exports. Proposed libraries are `httpx` for requests, one HTML parser, `phonenumbers` for phone normalization, `tldextract` for host handling, a tested robots parser, and `pytest` for important rules. Pick and lock compatible versions during setup. A distributed queue and a cloud database would add work without helping the first thousand records.

Keep the code in a few modules with clear jobs: source import, URL handling, polite fetching, page selection, extraction, verification, storage, and export. Verification functions should consume saved observations rather than perform hidden network calls. That lets us change a rule and re-evaluate existing evidence without fetching every site again.

The future CLI needs operations for importing sources, running a bounded batch, resuming a run, reviewing unresolved records, and exporting a snapshot. The exact commands belong in the README only after they exist and have been tried from a clean environment.

## Request order

1. Import and normalize a candidate while retaining the original URL and discovery source.
2. Resolve public DNS, fetch robots rules, and request the allowed homepage. Check each redirect destination before following it.
3. Collect preliminary platform clues. Reject clear non-store pages; keep uncertain cases available for limited inspection.
4. Select useful links from the homepage and fetch permitted contact, about, legal, and returns pages. India verification often needs these pages, so it cannot run before them.
5. Extract fields and platform/location evidence from the same observations.
6. Decide Shopify status and India status separately, resolve aliases, and put conflicts into review.
7. Export accepted records, missingness counts, and audit material from one saved run snapshot.

Record reachability, platform, location, and review state in separate fields. A timeout should not become a negative platform label. Failed new fetches should not silently overwrite older observations; keep the history and apply the freshness rule at export.

## Fetching rules

Use a named crawler user agent. Configure a real operator contact URL when implementation begins. Apply the same policy to HTML, sitemaps, logo checks, and any optional API requests.

| Setting | Initial value or behavior |
| --- | --- |
| Per-host concurrency | 1 request |
| Minimum gap | 2 seconds between request starts, increased by applicable crawl delay or backoff |
| Global concurrency | 8 hosts; reduce when failures or throttling rise |
| Initial page budget | Homepage plus 6 useful pages; one documented enrichment pass may add 4 |
| Response budget | 2 MiB decompressed per HTML page; stop and label truncation |
| Request timeout | 20 seconds overall, with shorter connection timeout |
| Transient retry | At most 2 retries with jitter; honor `Retry-After` and defer long waits |
| Redirect budget | 5 hops, with destination checks |
| Browser fallback | Only a small unresolved queue; all subrequests must obey the fetch policy |

Treat robots handling as a tested part of the fetcher. Parse matching user-agent rules correctly, including wildcard and end anchors. Follow applicable rules for each origin. A robots 404 can permit crawling; network errors and 5xx should defer it. Treat 401/403 conservatively as blocked, and 429 as a reason to back off. Cache robots for no more than 24 hours in normal operation. This policy follows the standard where applicable and makes a few deliberately stricter choices. [RFC 9309](https://www.rfc-editor.org/rfc/rfc9309.html)

Check URLs and resolved addresses to prevent requests to loopback/private networks, including after redirects and during browser fallback. Verify TLS normally. Cap sitemap decompression and ignore external-entity expansion. Do not submit forms, create carts, log in, or work around access challenges. Browsers should not be a way around a denied HTTP request.

## What counts as Shopify evidence

Use named evidence families rather than a magic numeric score. Ten images from one Shopify CDN still represent one family of evidence. A rule score is not a measured probability.

| Family | Example | Treatment |
| --- | --- | --- |
| Store identity | A valid `Shopify.shop` assignment naming a shop, in the storefront's own runtime markup | Strong when tied to the active storefront, rather than quoted in an article or example |
| Platform delivery | Shopify-specific runtime asset references or a DNS chain ending at `shops.myshopify.com` | Corroborates identity; proxies can hide the DNS relationship |
| Public commerce response | A permitted Shopify response tied to the same shop, where HTML leaves uncertainty | Optional corroboration; not required for every store |
| Presentation clues | Shopify attribution, familiar routes, CDN images | Supporting hints only; copying a footer or an image is easy |

The normal automatic route requires a store identity signal plus a different corroborating family on a live commerce page. Sites without the normal theme markup, including headless stores, go through a separate review path. A current Shopify backend relationship must be tied to that specific storefront. A Buy Button alone does not establish that Shopify runs the whole storefront.

This rule is provisional until tested against labeled pages. It will miss some real stores; measure that limitation rather than weakening the rule until the count looks good. Conflicting platform or identity evidence requires review.

Shopify's current documentation supports tokenless access for some Storefront API operations, including product and collection queries. The earlier blanket claim that product queries always require a token was incorrect. HTML remains the default for simplicity; a permitted public read query is an optional diagnostic, with no token collection or mutation. [Storefront API access](https://shopify.dev/docs/storefronts/headless/building-with-the-storefront-api)

The documented Shopify runtime object, DNS conventions, and asset conventions inform these rules, but Shopify does not guarantee a universal external detector. [Runtime object](https://shopify.dev/docs/storefronts/themes/best-practices/performance/load-critical-resources-before-content-for-header), [DNS and proxy behavior](https://shopify.dev/docs/storefronts/themes/best-practices/performance/avoid-request-proxies), [CDN assets](https://shopify.dev/docs/storefronts/themes/best-practices/performance/use-shopify-cdn)

## What counts as Indian business evidence

Look for the operator of the store, not every address mentioned on the page. Contact and legal pages may contain customer examples, overseas distributors, factories, or fulfillment providers.

A labeled merchant address in India is the main automatic path. A clear statement that the business is based in India can be reviewed and accepted even without a state. Keep the exact relevant passage and the page URL. A country selector, rupee symbol, Indian phone number, or delivery promise cannot substitute for this.

For state extraction, use a versioned reference list of states and union territories, with documented aliases such as Bangalore/Bengaluru and Gurgaon/Gurugram handled in location parsing. A city must appear in an address context and map unambiguously before it can support a state. Do not guess a state from a six-digit number or a city name in a shipping list. If a PIN-code dataset is later used, record its source and date and treat it as corroboration.

Registered/principal office has priority over business contact address. Returns addresses require an explicit relationship to the merchant. Keep conflicting locations visible. Structured organization markup helps locate evidence but must agree with the visible business content. Schema.org distinguishes an organization's address from its area served; the latter describes service coverage and is not location proof. [Organization schema](https://schema.org/Organization) WHOIS/RDAP is optional corroboration when public organizational data is available; it is not essential to this pipeline.

## Field extraction decisions

Collect HTML links, visible text, and relevant JSON-LD. Parse structured data without executing scripts. Keep a value's raw form, normalized form, source URL, observation time, and extractor rule.

For emails, decode `mailto:` values and visible obfuscation only when the result is unambiguous. For phones, preserve extensions and country context. Do not automatically turn every ten-digit sequence into an Indian number. Public WhatsApp links can supply a business phone when clearly associated with the store. Keep all supported contacts, including international support numbers, even for an Indian business. Record them as published contacts; syntax checks do not prove deliverability or ownership.

For socials, recognize profile URLs and remove tracking parameters carefully. Exclude share and intent endpoints. Do not crawl the social network to collect extra contacts in the first version.

For categories, start with a small documented taxonomy and specific subcategories where supported. Inspect navigation and at most a few representative product/collection pages within the page budget. Product-level categories must not automatically describe the entire catalog. Keep an `unknown`/missing state for insufficient evidence. Any later model-assisted classification needs its input evidence and version recorded.

For descriptions, prefer a useful homepage meta description, then About or hero copy. Preserve original wording and Unicode. Do not silently summarize it. Mark truncation if the selected passage exceeds the export limit.

For logos, consider the header image, organization logo data, lazy-load attributes, `srcset`, and inline SVG. Verify the chosen asset with a bounded allowed fetch. A filename containing `logo` is a clue, not enough by itself. Keep the original image URL including version parameters; removing parameters can break an asset. Select safely saved inline SVG only if it is actually the header brand mark, with scripts and external references removed. Do not render text into an invented logo.

When a field is missing, use its reason to decide whether the extra four-page enrichment pass is useful. Stop at the published budget and record pages checked. This gives a measurable definition of “all discoverable contacts” within this run.

## Storage, identity, and export

SQLite stores candidates, observations, evidence, fields, aliases, run configuration, and review decisions. Keep raw and normalized values. Each evidence item needs a source URL, fetched-at time, fetch outcome, short excerpt or selector, content hash, and rule version. A hash helps identify a snapshot; it does not replace inspectable evidence.

Persist completed work and retry eligibility after each page. Replaying a run must not duplicate observations or accepted rows. A manual correction is a separate recorded decision with a reason and reviewer type; it should not erase the machine result. Agent inspection must be described as agent inspection, not passed off as an independent human audit.

Merge aliases only with positive identity evidence. Shared images, contact details, company ownership, or similar brand names are review clues, not sufficient merge keys. Keep case-sensitive paths when normalizing URLs. Use the final primary hostname for display and a stable internal identifier for record history.

Exports must come from one named snapshot and sort predictably. Define schema and rule versions. JSON preserves exact string values. In CSV, protect cells that spreadsheet software might interpret as formulas and document the escaping rule. Run a round-trip import check so JSON-encoded contacts and socials survive export.

## Tests that are worth writing

Test the decisions most likely to create bad data: false Shopify clues, copied footers, India shipping without Indian location, multi-address businesses, state/city confusion, alias collisions, logos versus favicons, social share links, malformed phone numbers, and CSV escaping.

Use saved fixtures for these cases so a change can be tested offline. Add fetcher tests for robots matching, redirects to another origin, timeout/retry behavior, 429 handling, decompression limits, and interrupted-run recovery. Include a test that different `*.myshopify.com` stores do not merge.

A small live smoke run checks that the whole pipeline still works. It does not replace offline regression tests, and routine tests should not repeatedly hit merchant sites.

## Quality measurement without inflated claims

After development, freeze the rules and export a dataset snapshot. Draw a reproducible simple random sample of 150 accepted records, or all records if fewer exist. Keep a separate diagnostic sample of unusual cases and rare sources. Do not combine those oversampled cases into an unweighted headline accuracy figure.

Check the joint claim “Shopify and India-based,” canonical URL, logo, state, category, description fidelity, and contact attribution. Report numerator and denominator for each metric. Contact precision counts supported extracted contacts; contact completeness is estimated by inspecting the same allowed pages and checking for missed contacts. It cannot measure undiscovered contacts elsewhere on the web.

Report the observed acceptance accuracy and a binomial confidence interval, making clear that a small perfect sample does not prove 100% accuracy. The target is at least 98% observed correctness for the joint claim. Any material systematic error still blocks release even if the percentage passes. Correct the rule, re-evaluate the affected dataset, and draw a fresh audit sample for the new snapshot.

Inspect a separate sample of rejected and unresolved candidates to find preventable misses. That estimates errors within the candidate pool; it cannot measure recall across all Indian Shopify stores because the full population is unknown.

Record who performed the review and when. Reserve a short independent human spot-check for the user or reviewer if available. Never call the audit independent if the same extractor simply validates its own output.

## Build order and completion checks

| Step | Deliverable | What must be true before moving on |
| --- | --- | --- |
| 1. Source investigation | Named source manifest and initial candidate sample | At least one source is accessible and its actual resource use is understood |
| 2. Small complete run | About 20 candidates through fetch, evidence, decisions, and export | A selected output row can be traced back to its sources; interruption/resume works |
| 3. Pilot | 300 unique candidates where available | Source yield and common failure cases are measured; verification rules revised from examples |
| 4. Field quality | Extractors and meaningful regression fixtures | Missingness and wrong-field cases have been inspected, especially logos and addresses |
| 5. Larger batches | Increasing accepted dataset | Each batch has useful marginal yield; retries and request budgets stay bounded |
| 6. Audit and freshness | Frozen snapshot, sample audit, final checks | Evidence is current, errors are corrected, and remaining limits are disclosed |
| 7. Submission | Dataset, code, tested instructions, short README, optional report | Clean local reproduction works and all published numbers match the run artifacts |

Estimate four to six focused working days, with collection time depending on yield. Log actual sessions and unattended runtime. The page budget and fetch rate allow a request-volume estimate, but blocked sites and retries make a promised full-run duration premature. Calculate it after the pilot.

For final freshness, recheck qualifying evidence older than seven days. If new evidence fails or contradicts the stored decision, move the record out of the current accepted export. Keep historical observations separate.

## What changes at a larger scale

At 10,000 stores, discovery coverage, duplicate work, and refresh scheduling become more expensive. Keep the same schema, reuse stored evidence, and schedule incremental checks by age and failure history. Add workers only when measurements show that one local runner is the bottleneck.

At 100,000 stores, a shared host-level scheduler and a database designed for concurrent workers become reasonable. Object storage can hold compressed snapshots with retention limits. Discovery would need broader licensed/open sources and explicit source-quality monitoring. Neither scale removes the need for sampled review, conservative location decisions, or per-host politeness.

The current unknowns are candidate yield, the best `.com` discovery source, how much browser rendering is needed, and the time required for address/logo review. The pilot is designed to answer those questions. The user has asked to finish planning before coding, so implementation and store collection remain pending.
