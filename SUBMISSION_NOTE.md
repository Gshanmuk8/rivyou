# Local submission note

Result: `outputs/stores.csv` (also `outputs/stores.json`) — 1,033 deduplicated stores that passed the automated Shopify and Indian business-address checks.

The pipeline starts with attributed public domain leads, then checks the live merchant pages for Shopify identity/runtime/commerce evidence and an Indian business address. It extracts public contacts, socials, category, merchant description, a validated brand image and state, keeping field-level evidence and leaving unsupported values empty.

Recorded collection/enrichment run spans total 362.6 minutes; the final offline replay spanned 559.6 minutes, including an extended host pause. Development and QA were assisted by a coding agent during 29–30 September 2026; total active development time was not measured. No paid discovery API, Supabase or AI API key was used by the pipeline.

The code, README, result files and checks are in this local repository. A public GitHub URL has not been created as part of the local delivery. The dataset is automatically verified and agent-reviewed where documented, not independently human-audited.
