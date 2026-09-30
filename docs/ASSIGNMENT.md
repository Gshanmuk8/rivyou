# SDE Intern Assignment — Discover Indian Shopify Stores

## Objective

Build a pipeline that identifies **Shopify stores based in India** and extracts structured data about each one. Your goal is **1,000+ verified Indian Shopify websites**, but quality and correctness of your approach matter more than raw count — a well-reasoned pipeline that returns 700 clean, verified records is worth more than a sloppy one that returns 1,500 with junk in it.

This isn't a throwaway exercise — it mirrors a real problem we're solving at Rivyou, so a genuinely good submission has a good chance of turning into a real opportunity.

---

## What you need to find

For each store, collect:

| Field | Notes |
|---|---|
| **Domain URL** | The store's primary domain (custom domain if they have one, else `*.myshopify.com`) |
| **All contacts** | Any discoverable email(s), phone number(s) — from contact pages, footer, WHOIS, etc. |
| **Socials** | Instagram, Facebook, Twitter/X, LinkedIn, YouTube — whatever is linked from the site |
| **Category** | What the store sells (e.g. "skincare", "men's apparel", "home decor") |
| **Tagline / description** | Their own words — from meta description, About page, or homepage hero text |
| **Logo** | The actual brand logo image (not the favicon) — provide a URL or save the image file |
| **State** | Indian state the business is situated in (from address, contact page, WHOIS, or other signals) |

It's fine if a few fields are missing for some stores (not every site publishes a phone number or a clean address) — but tell us in your README how often each field was missing and why.

---

## What to submit

1. **A public GitHub repository** containing:
   - All your code (scrapers, detection logic, filtering logic, dedup logic, etc.)
   - A `README.md` in the repo explaining:
     - **Your exact approach**, step by step — how you sourced candidate domains, how you confirmed each one is a Shopify store, how you confirmed each one is Indian, and how you extracted each field
     - What data sources / seed lists / crawling techniques you used
     - How you handled false positives (e.g. a `.in` domain that isn't actually Indian, or a site that looks like Shopify but isn't)
     - Known limitations — what would break at 10x or 100x scale, what you'd do differently with more time
     - How to run your code (setup instructions, dependencies, how long a full run takes)
   - Your output data (CSV or JSON) checked into the repo, or a link to download it if it's large

2. **A result file** (CSV or JSON) with one row per store, containing all 7 fields above.

3. Send us:
   - The GitHub repo link (public)
   - The result file (or its location in the repo)
   - A short note (a few lines is fine) on the method you used and roughly how long it took

---

## Evaluation criteria

We'll be looking at:

- **Correctness** — are these actually Shopify stores? Are they actually Indian? We will spot-check a sample.
- **Data quality** — completeness and accuracy of the 7 fields, not just row count.
- **Approach & reasoning** — does your README clearly explain *why* you made the choices you did (e.g. how you defined "Indian," how you avoided duplicates, how you handled rate limits)?
- **Code quality** — readable, reasonably structured, not necessarily production-polished.
- **Judgment on edge cases** — e.g. how you treat a globally-hosted brand with Indian ownership, or an Indian brand using a `.com` domain.

---

## Constraints & suggestions

- No specific tech stack is required — use whatever language/tools you're comfortable with.
- Free/open data sources are preferred over paid ones (e.g. Common Crawl, public domain lists, search engines, Shopify's own detection signals) — but if you use a paid tool or API, disclose it and explain why.
- Respect `robots.txt` and reasonable rate limits — don't hammer any single site or service.
- There's no strict time limit, but we'd expect a focused effort to take a few days, not weeks. Document how long you actually spent.

---

## Questions

If anything here is ambiguous, use your judgment and document the assumption you made in the README — that decision-making is part of what we're evaluating.

Good luck!
