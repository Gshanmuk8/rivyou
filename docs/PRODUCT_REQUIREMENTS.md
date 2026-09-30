# What we are building

Planning revision: 29 September 2026. Based on the supplied `README_SDE_Intern_Rivyou.md`.

Rivyou wants a list of Indian Shopify stores that someone can actually use. The target is 1,000 stores, but every row has to stand up to a spot-check. A long spreadsheet with guessed addresses or unrelated contact details would miss the point of the assignment.

The project will run locally. It will discover candidate websites, check their platform and business location, collect the requested information, and save the results with the evidence behind them. The current work covers research and planning only. Implementation starts after this phase.

## What should make this submission strong

A reviewer should be able to pick any row and answer three questions quickly: Why is this Shopify? Why is the business based in India? Where did each field come from?

That is the main design choice. Each accepted store gets an evidence record with source links, short relevant extracts, observation dates, and the rules used to accept it. The final report also shows rejected and unresolved cases, so the reader can see the decisions behind the count.

Once the data is sound, a small local report can make it easier to inspect. It should show the store, its actual logo, the seven requested fields, and links to the evidence. This is an extra presentation feature. The CSV and pipeline must be complete before spending time on it.

## What the assignment asks for

| Requirement | Planned delivery |
| --- | --- |
| Aim for 1,000+ verified Indian Shopify stores | Accepted dataset, with the actual count and clear inclusion rules |
| Primary domain | Current customer-facing URL; aliases retained separately |
| All discoverable business emails and phones | Deduplicated lists with the page where each was found |
| Social profiles linked from the site | Named network and profile URL; sharing buttons excluded |
| What the store sells | Useful category and, where supported, a more specific subcategory |
| Its own description or tagline | Merchant wording and the source page |
| Actual brand logo | Image URL, or an extracted image file where a URL is unavailable |
| Indian state | Normalized state or union territory, with location evidence |
| Explain missing fields | Counts, percentages, and observed reasons |
| Explain and reproduce the method | Code, setup instructions, source manifest, configuration, and actual run measurements |
| Public GitHub submission | Repository, result file location, and a short method/time note after local completion |

Evidence records, resumable runs, quality checks, and the optional report are our proposed additions. The assignment does not require a dashboard, a particular framework, or cloud deployment.

## Which businesses belong in the dataset

A store qualifies when there is current evidence that Shopify runs its commerce storefront and that the merchant business is based in India. These are separate checks. Passing one does not imply the other.

For India, the strongest ordinary evidence is a merchant's own contact or legal page identifying its Indian business entity and address. An explicit statement that the business is based in India can also qualify after review, even if it does not name a state. A returns warehouse by itself is insufficient: it may belong to a logistics company.

A `.com` domain is fine. A `.in` domain is just a lead. Currency, shipping destinations, an Indian phone number, and server location cannot settle the country question. Indian founders alone do not prove that a company now operates from India. If the merchant is an Indian subsidiary of a foreign brand, it can qualify when that Indian entity is clearly the operator of the storefront; record that basis.

Wholesale stores qualify under the same rules. The assignment does not limit the dataset to consumer brands. A Shopify-powered marketplace is also not automatically excluded; the row describes the marketplace operator, not each seller inside it.

A site that is blocked, password protected, parked, or too broken to verify goes into an unresolved or excluded file with a reason. It is not silently counted as a non-Shopify store.

## What one row means

Use one row for a distinct storefront, with one primary URL. A custom domain and its redirecting Shopify address are the same storefront. HTTP/HTTPS and `www` aliases are merged only when redirects or other direct evidence support the relationship.

Do not collapse every subdomain to its parent: `shop.example.com` may be the actual store. Do not collapse all `myshopify.com` stores into one registered domain. Separate brands can share an owner, address, or phone number and still deserve separate rows. Separate regional URLs with the same Shopify shop identity should normally be grouped; uncertain cases need a recorded decision.

Prefer a working HTTPS primary URL. A functioning HTTP-only site is an exception to review, rather than an invented HTTPS URL. Canonical tags are hints and must be checked against the live site.

## How the fields should behave

| Field | Rule |
| --- | --- |
| Contacts | Collect every distinct public business email and phone found within the documented crawl scope. Keep raw and normalized values. Do not claim that bounded crawling finds every contact on the entire internet. |
| Socials | Include profiles linked by the merchant. Exclude sharing URLs, the theme developer's profiles, and generic network homepages. A linked profile is not a guarantee that the account remains active. |
| Category | Base it on products and navigation. Keep mixed catalogs as mixed when the evidence does not support a narrower label. |
| Description | Preserve the merchant's words. Record which passage was used and whether it was shortened. Do not generate a replacement tagline. |
| Logo | Use the visible brand identity in the header or reliable organization markup. A favicon, product photo, payment icon, or homepage banner does not qualify. Inline SVG logos may be saved safely; text-only branding remains missing. |
| State | Prefer principal/registered office, then an explicit business contact address. Keep all candidate addresses and their roles. If the country is established but the state is unclear, leave the state missing. |

The data must distinguish an absent value from a failed attempt to collect it. For example, `not_found_in_allowed_pages` is more honest than `not_published` when only a few pages were inspected. Other reasons include `robots_blocked`, `fetch_failed`, `ambiguous`, `budget_exhausted`, and `text_only_logo`.

## Output contract

The final dataset will be available as CSV and JSON. Both carry the same records. CSV has eight main columns because the assignment's contacts field is split into emails and phones:

`domain_url`, `emails`, `phones`, `socials`, `category`, `description`, `logo_url`, `state`.

JSON uses arrays for contacts, a network-to-URLs object for socials, and `null` for missing scalar values. CSV stores arrays and objects as JSON strings and leaves missing scalar cells empty. A small data dictionary explains this convention. Evidence records are joined by a stable `store_id`, also included as an extra dataset column. A saved inline logo uses an additional `logo_path` pointing to a bundled file; its `logo_url` stays missing rather than containing a fake URL.

The supporting files are a source manifest, evidence JSONL, review decisions, a run report, and an audit report. Raw page caches stay local and outside Git. Publish selected minimal evidence and source links, not copies of entire websites.

## How we will judge the result

The non-negotiable rule is that every exported row has a supported Shopify decision and a supported India decision. Unresolved contradictions stay out of the accepted dataset.

The working target is at least 98% correctness on a separate random sample of accepted records. That number is a target, not a claim about results we have not collected. The audit must report its sample size, errors, and uncertainty. Contacts, logos, and state get their own checks; country accuracy alone does not establish field accuracy.

Missing values are allowed. Made-up values are not. We will report the share missing each field and inspect whether it reflects the sites or a weak extractor. We will also show source coverage so that a dataset concentrated on large English-language brands is not presented as a representative sample of Indian commerce.

## Scope and effort

Plan for about four to six focused working days, subject to the discovery pilot. Record actual working sessions separately from unattended crawl time. If the evidence supports fewer than 1,000 stores, explain the measured bottleneck and submit the clean result.

The first milestone is a small, fully traceable run. The last milestone is a reproducible submission with real measurements and a short, clear README. No store dataset, implementation, or public repository has been produced in this planning phase.
