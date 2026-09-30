# How the finished work should read and feel

Planning document, 29 September 2026. This is guidance for the eventual submission, not a README claiming that the project already exists.

The supplied assignment asks for a public repository, data, an explanation, and a short submission note. The user's current request is to research and plan before coding. Publication and sending a submission are later actions; nothing has been uploaded or sent.

## Make the result easy to inspect

The first screen of the repository should tell the reviewer what the project does, how many stores the completed run verified, when it ran, and where the data lives. Those numbers must come from the final run report.

Include one actual store example with links to its evidence. Show the country evidence and Shopify evidence separately. Follow it with one real rejected example and why it failed. This is a compact way to demonstrate judgment without asking the reader to trust an accuracy claim.

The result file must be useful on its own. The evidence file gives a curious reviewer more detail. A local report is worth adding only if the pipeline and audit are finished: searchable rows, category/state filters, visible missing fields, and an evidence panel for each store. Every displayed number comes from the same export snapshot. No decorative confidence percentages or made-up sample stores.

## A README that sounds like someone explaining their work

Use short sections in this order:

1. What the script does and the measured result.
2. Where the result files are and what their columns mean.
3. How to run a small example, with commands tested from a clean setup.
4. Where the candidate domains came from, including exact source links.
5. How Shopify and India were checked, with actual examples.
6. How contacts, socials, category, description, logo, and state were extracted.
7. What was missing, what went wrong, and how the sample audit was done.
8. What would need to change at 10× and 100× the size.
9. Actual working time, unattended runtime, and any costs.

Explain decisions in ordinary language. For example: “A rupee price was useful for finding candidates, but I did not use it to decide where the business was based.” That is a writing example, not a statement about an experiment already completed.

Use first person only for decisions and work the student can honestly explain. Do not invent personal effort, discoveries, manual checks, or elapsed time. If a tool or agent performed part of the work, describe the method accurately when relevant and follow any disclosure requirement from the evaluator. A natural writing style does not require pretending how the work happened.

Avoid words such as “revolutionary,” “seamless,” “enterprise-grade,” and “100% accurate.” Replace broad claims with a concrete observation. If the crawler missed phones in lazy-loaded footers, explain that and say what was changed. If the count stops below 1,000, state the number and the measured reason.

## Evidence to collect while building

| Record | Why it belongs in the final explanation |
| --- | --- |
| Source manifest and per-source yield | Shows where the domains came from and which sources actually helped |
| Before/after result for a corrected failure | Shows how a wrong extraction led to a specific improvement |
| Alias merge example | Demonstrates that duplicate domains did not inflate the count |
| One ambiguous address decision | Makes the definition of “based in India” concrete |
| Logo comparison from the audit | Shows that the extractor selected a brand mark rather than a favicon or product image |
| Field missingness with reasons | Makes the data's limits visible |
| Frozen sample and review notes | Supports the reported accuracy without changing the sample after seeing errors |
| Run timestamps and request totals | Supports the runtime and rate-limit explanation |

These are records of work to collect during implementation. Do not manufacture anecdotes to fill the list.

## A short demonstration

Open the final dataset and choose a row. Show its source pages and explain both verification decisions. Then show a domain alias that was merged and a candidate that was excluded. Finally, run a small saved-fixture example and show that it produces the expected output without needing to crawl hundreds of sites.

If the local report exists, use it for this walkthrough. Keep the CSV available so the work remains easy to use without the report. The explanation should take about three minutes and use real results from the submitted snapshot.

## Checks before calling it finished

All seven requested data groups are present. The accepted store count agrees across the dataset, report, and README. Every accepted row has source evidence. Audit results identify the reviewer and distinguish human inspection from agent inspection. Missing fields have measured counts. Setup commands work. Secrets and raw caches are excluded from Git. The public repository and data links are tested after publication.

The short submission note should state the actual method, accepted count, working time, unattended runtime, and where the files live. Write it when those facts exist.

## Reading the planning files

`PRODUCT_REQUIREMENTS.md` defines the result and the inclusion rules. `ENGINEERING_PLAN.md` explains the implementation sequence, evidence checks, experiments, and tests. This file describes how to present the completed work clearly. Together they replace the earlier draft; there is no separate implemented product or dataset yet.
