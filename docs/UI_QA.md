# UI verification

30 September 2026. The visual reference is Rivyou's public site. This pass covers the local interface and its connection to the pipeline; it does not establish the accuracy of a 1,000-store dataset.

## Automated checks

- 90 Python tests pass. These cover extraction, network restrictions, robots handling, source attribution, exports, reviews, empty queues, and run recovery.
- The new pause test stops after a homepage has been saved, resumes the same run, and proves the homepage was requested only once.
- Another regression uses two database connections to verify that an API pause reaches a separately owned worker.
- Ruff passes. JavaScript passes Node's syntax check. The HTML, CSS and JavaScript were formatted with Prettier 3.9.9.
- The test runner reports one upstream Starlette/httpx deprecation warning. It does not affect the passing assertions.

Three full browser runs passed all 16 workflow groups. The first two took 91.1 seconds each; the latest took 92.2 seconds. All three reported zero JavaScript page errors. Saved browser ZIPs were reopened: each contained the expected 13 fixture records and passed every manifest checksum. Earlier attempts exposed the review-selector labelling issue and browser-adapter differences; those were addressed before the complete repeats.

The final visual check also caught a white SVG logo using CSS class rules. The preview classifier now reads those colours and selects a dark background. A regression covers this case.

## Browser setup

`tests/e2e_server.py` creates a separate temporary SQLite database for each invocation. Its HTTP transport serves deterministic fixture merchants. There is no path from this fixture transport to a real merchant request. The actual fetcher, robots parser, extraction rules, database, API and interface are exercised together.

The browser test imports 15 fixture candidates: 13 with Shopify and Indian address evidence, one without an address, and one blocked by robots. These are test-only records. They are never included in the real result file.

The repeatable browser program is `tests/browser_flows.js`. It uses the installed Tabbit CLI's Playwright interface. Start a fresh test server for each full run:

```powershell
.\.venv\Scripts\python.exe tests\e2e_server.py --port 8766
```

In a second terminal, pass the JavaScript file through CMD stdin, as required by Tabbit on Windows:

```powershell
$cli = "$env:LOCALAPPDATA\Tabbit\LocalAgent\bin\tabbit-cli.exe"
$program = Join-Path (Get-Location) 'tests\browser_flows.js'
cmd.exe /d /c "`"$cli`" nodejs --task `"Rivyou browser QA`" --request-id run-one --timeout-ms 120000 < `"$program`""
```

Use a new request ID each time. Restart the test server before repeating; it creates a fresh database. Use Tabbit's `finish` command when the browser work is complete. The test script expects the deliberately isolated server on port 8766, not the working app on 8765.

## Flows exercised

1. Open a fresh workspace, import dialog, and close it with a pointer.
2. Reject a localhost candidate and keep the import error visible.
3. Import 15 attributed candidates; import one again and report the duplicate.
4. Start collection, pause it, reload the app, and resume to completion.
5. Explain a completed queue and offer the next useful action.
6. Move between result pages, search for a nonexistent store, and clear filters.
7. Filter by Indian state and reset the view.
8. Open store details, page evidence and fetch history.
9. Exclude a store, save the review note, reload, and verify persistence.
10. Confirm existing evidence, requeue the store, and collect it again.
11. Keep unresolved/robots-blocked records in Needs attention; prevent confirmation without evidence.
12. Open source attribution and completeness reports.
13. Dismiss the export popup with Escape and return focus to its trigger.
14. Fetch all six export formats and verify attachment headers and nonempty bodies.
15. Activate the ZIP export link and save its response through the browser-network API.
16. Simulate an unavailable overview endpoint, show a connection error, then recover with Refresh.

The browser adapter does not emit native Playwright download events. The ZIP check therefore uses the link's observed URL and Tabbit's browser-network file API. A native ZIP downloaded during the initial check was also found in the local Downloads folder. A test assertion that relied on a native download event was corrected; the app's endpoint had already returned the file.

## Layout and keyboard

Checked widths: 360, 390, 430, 768, 1280 and 1440 pixels. None produced horizontal page overflow. At phone widths the table becomes store cards. All four navigation choices remain visible in two rows.

Named dialogs, focus containment, Escape dismissal, methodology open/close, and evidence-tab focus preservation were checked in the browser. These checks are useful coverage, not a full screen-reader certification or an automated WCAG conformance claim.

## Real workspace

The original interface pass used 17 accepted records from 26 candidates (snapshot `d486e92bf655e233`). Subsequent collection has expanded the real dataset; see `outputs/manifest.json` for the current count and snapshot. The third complete browser pass used a separate fixture server and did not write to the real database.

Real merchant sites can still time out, block requests, change markup, or omit business information. The app keeps those outcomes visible instead of reporting a false verification. Collection and dataset review are documented separately from these interface tests. An independent human audit is not claimed.
## Saved-file correction

The final delivery check found that Windows text-mode writes translated newlines in CLI exports, so on-disk bytes did not match the manifest. Browser ZIP bytes were unaffected. CLI exports now write UTF-8 bytes directly, and Git attributes preserve those bytes. A CLI regression reads every exported file back from disk and checks its hash. That 17-record snapshot was regenerated and passed every checksum. All subsequent exports use the corrected writer. The latest suite has 90 passing tests.


## Check during expanded collection

With 844 candidate records in the local database, overview, stores and run-history requests all returned HTTP 200 while collection was active. One sequential check measured 0.597 s, 0.453 s and 0.347 s respectively, including client setup. This is a small local check, not a load-test result or a latency guarantee.


## Final local delivery

The final real workspace contains 2,339 checked candidates and 1,033 verified stores, with no queued candidates or active run. Snapshot `96232f7c659ca586` passes the strengthened standalone validator. Real API CSV/JSON responses match the saved files byte-for-byte, and the complete ZIP passes every checksum.

Desktop (1440px) and phone (390px) views were checked again with the final dataset, including the verified filter and completed-queue message. Neither had horizontal page overflow. The current screenshots are in `docs/images/`. The three earlier complete fixture browser runs remain the full workflow checks; final rule changes additionally have extraction/migration regression coverage. The latest full Python suite has 90 passing tests and the one upstream deprecation warning. Its measured 636.6-second span included a host pause and is not a normal test-runtime benchmark.

During manual logo inspection, replacing the app DOM with a temporary gallery triggered the old page's polling timer. That was a review-harness artifact. Fresh normal app navigation and the final desktop/mobile captures had no reported script issues. A browser assertion also initially expected the directory heading to show the filtered count; inspection confirmed that heading displays all candidates while the selected filter and result rows correctly reflect verified stores.
