# Data review

The final snapshot is `96232f7c659ca586`: **1,033 stores** from 2,339 candidates. Every exported record passes both required automated checks and has field-level evidence. All accepted records use rule `2026-09-30.8`.

## What was checked

A deterministic sample of 30 stores was drawn from sorted store IDs with seed `20260930`. I read its Shopify signal families, merchant business-address excerpts, category/description and contact/profile values, verified the referenced cache hashes, and visually inspected the brand images. The record-level notes are in [agent-spot-check.json](../data/audit/agent-spot-check.json).

All 30 had supporting Shopify and Indian-business evidence under the documented rules. After correction, 29 had visually matching brand images and one deliberately has no logo. Seven sampled categories and one state remain empty. These are observations about this sample, not a population accuracy percentage.

This was an **agent review**, and the sample was used to improve the parser. It is not an independent human audit or a held-out evaluation. The separate 150-record [audit sample](../outputs/audit-sample.json) remains blank for an independent reviewer. Email delivery, phone routing, social-account ownership and the truth of merchant business claims were not independently checked.

## Corrections from the sample

- Dressfolk's visible support email disagreed with a copied mailto target for another brand. The displayed address now takes precedence.
- Voganow had a concatenated email ending in `.com.the`; Rico published a template `yourcompany.com` address. Both are filtered.
- Dermatouch had a concatenated YouTube link. Lavie linked third-party social posts and a provider unsubscribe address. Those are excluded from merchant profiles/contacts.
- Known YouTube channel tabs and LinkedIn company tabs normalize to their profile URLs.
- Ariga Foods' first delivery evidence was a theme favicon. Shopify delivery now requires a JavaScript or stylesheet asset; the saved pages supplied one.
- POND'S selected image was the parent-company Unilever footer logo. It is omitted rather than exported as the brand logo. The same header/home-link validation runs across the dataset.

The contact list preserves merchant spelling and explicit published phone formatting. POND'S organization metadata publishes a `+1800` number; it is retained as published, not silently rewritten to a guessed country code. That number has not been tested for reachability.

## Address exceptions

A separate targeted check inspected 27 records flagged by overseas-place or form-template words. Most had a concrete Indian office plus overseas locations, neighbourhood names or unrelated newsletter text. These flags are not automatic rejections. Notes and source URLs are in [address-review.json](../data/audit/address-review.json).

Aroma Magic is held outside the export: its contact block lists Bawal, Haryana and Bhagwanpur/Roorkee/Haridwar in Uttarakhand, while the parser selected only Haryana. The [Haridwar district site](https://haridwar.nic.in/about-district/) supports the location interpretation. The merchant's India evidence remains supported; the unresolved state is why the review hold remains.

## Packaging checks

The validator checks exact file hashes, CSV/JSON parity, unique domains and Shopify identities, all three Shopify signal families, qualifying runtime assets, source attribution, and populated-field provenance. It also rejects invalid/template emails and malformed/noncanonical profile URLs.

The real app's CSV and JSON were compared byte-for-byte with the saved files. Its ZIP was reopened and every manifest checksum verified. These are consistency checks, not proof that every merchant claim is true.
