# Interface design

I used [rivyou.co](https://rivyou.co/) as the visual reference on 30 September 2026. This is a local research tool built for the assignment, not Rivyou's consumer app.

## What comes from the reference

The live site uses Outfit for headings, DM Sans for body text, teal `#22A08B`, navy `#0F172A`, mint `#F0F9F8`, and pill-shaped buttons. Its wordmark is the SVG at `https://rivyou.co/rivyoo_logo.svg`.

The workbench uses those colours, fonts and wordmark. Fonts are served locally with their SIL Open Font Licenses in `src/rivyou/static/brand/`. The logo remains Rivyou's brand asset. No external font request is needed to open the app.

## Changes for a data-heavy tool

- The primary action uses a darker teal, `#157D6D`, so small white button labels remain readable. The brighter brand teal is used for accents and progress bars.
- Text uses navy or slate. Colour is accompanied by a status label: Verified, Needs review, Blocked, Queued, and so on.
- Desktop has a persistent sidebar, four summary cards, and a store table. Below 700px the navigation becomes a horizontal strip and each store becomes a card. The page itself should not scroll horizontally.
- Tables use compact text. Forms and descriptions get more space. The main controls are at least 44px high; desktop pagination is 36px and expands on mobile.
- Cards use an 18px radius, dialogs 24px, and buttons a full pill. Spacing mainly follows 4/8px increments.
- Motion is limited to loading feedback and hover transitions. Reduced-motion preferences disable it.

The tokens are at the top of `src/rivyou/static/app.css`. Component styles use them so a colour change does not require editing every screen.

## States that need to make sense

| Situation | What the user sees |
| --- | --- |
| Fresh database | An import action and an explanation of the starter list |
| Candidates waiting | Collect N queued, with a bounded run dialog |
| Collection running | Saved progress, a pause action, and no second start action |
| Pause requested | Saving-progress text; the same action cannot be submitted twice |
| Interrupted or paused run | Resume in collection history, when there is unfinished work |
| All candidates checked | Add domains to collect, with counts explaining what happened |
| Search has no matches | Clear filters; existing data is retained |
| API unreachable | A visible error and Reconnecting status; refresh can recover |
| Store lacks evidence | Missing values and unsupported checks are explicit |
| Rejected import line | Error stays in the form; accepted lines and duplicates are counted |

Native dialogs provide focus containment and Escape dismissal. Each dialog has a heading as its accessible name. The export popup supports Escape and returns focus to its trigger. Evidence-tab updates preserve keyboard focus. The interface includes a skip link, labelled form controls, visible focus rings, and text descriptions of progress.

## Services

SQLite is enough for this single-user local workflow. Supabase is not required. A shared hosted version would need authentication, worker ownership, a job queue, and a storage/database migration before enabling remote access.

An AI API is also optional. Verification currently uses inspectable rules and source pages. If an extraction model is added later, its output must retain source evidence and pass the same acceptance checks; a model's guess must never become proof that a business is Indian or uses Shopify.