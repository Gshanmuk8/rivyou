// Run through Tabbit's nodejs command against tests/e2e_server.py.
// This exercises real UI + API + SQLite + extraction with a mock HTTP transport.
const checks = [];
globalThis.qaChecks = checks;
const check = (name) => checks.push(name);
await page.goto("http://127.0.0.1:8766/", { waitUntil: "networkidle" });
await page.setViewportSize({ width: 1440, height: 1000 });
globalThis.qaErrors = [];
page.on("pageerror", (error) => globalThis.qaErrors.push(error.message));
await expect(
  page.getByRole("heading", { name: "Your first discovery starts here." }),
).toBeVisible();
await page
  .getByRole("button", { name: "Add domains to collect", exact: true })
  .click();
await expect(
  page.getByRole("heading", { name: "Import candidates", exact: true }),
).toBeVisible();
await page.getByRole("button", { name: "Close import", exact: true }).click();
await expect(page.locator("#import-dialog")).not.toBeVisible();
check("Fresh workspace offers import; pointer close works");
await page
  .getByRole("button", { name: "Add domains to collect", exact: true })
  .click();
await page.getByLabel("Domains", { exact: true }).fill("http://127.0.0.1/");
await page
  .getByLabel("Source name", { exact: true })
  .fill("Browser QA fixture");
await page
  .getByLabel("Source URL", { exact: true })
  .fill("https://source.com/qa");
await page
  .getByRole("button", { name: "Import domains", exact: false })
  .click();
await expect(page.locator("#import-result")).toContainText(
  "0 candidates added",
);
check("Unsafe import displays an error without closing the form");
const domains = Array.from(
  { length: 13 },
  (_, i) => `fixture-${String(i + 1).padStart(2, "0")}.in`,
).concat(["fixture-review.in", "fixture-blocked.in"]);
await page.getByLabel("Domains", { exact: true }).fill(domains.join("\n"));
await page
  .getByRole("button", { name: "Import domains", exact: false })
  .click();
await expect(
  page.getByRole("button", { name: "Collect 15 queued", exact: true }),
).toBeVisible();
check("Attributed import persists 15 candidates");
await page
  .getByRole("button", { name: "Import candidates", exact: true })
  .click();
await page.getByLabel("Domains", { exact: true }).fill(domains[0]);
await page
  .getByLabel("Source name", { exact: true })
  .fill("Browser QA fixture");
await page
  .getByLabel("Source URL", { exact: true })
  .fill("https://source.com/qa");
await page
  .getByRole("button", { name: "Import domains", exact: false })
  .click();
await expect(
  page
    .getByRole("status")
    .filter({ hasText: "0 candidates added · 1 already known" }),
).toBeVisible();
check("Repeated import reports duplicate without adding a record");
await page
  .getByRole("button", { name: "Collect 15 queued", exact: true })
  .click();
await page
  .getByRole("button", { name: "Start collection", exact: true })
  .click();
await page
  .getByRole("button", { name: "Pause collection", exact: true })
  .click();
await page
  .getByRole("button", { name: "Collection runs", exact: true })
  .click();
await expect(
  page.getByRole("button", { name: "Resume", exact: true }),
).toBeVisible({ timeout: 20000 });
check("Collection pauses and offers resume");
await page.reload({ waitUntil: "networkidle" });
await page
  .getByRole("button", { name: "Collection runs", exact: true })
  .click();
await page.getByRole("button", { name: "Resume", exact: true }).click();
await expect(page.locator("#runs-view .badge").first()).toHaveText(
  "Completed",
  { timeout: 25000 },
);
check("Paused run survives reload and resumes to completion");
await page.getByRole("button", { name: /^Store explorer/ }).click();
await expect(page.locator("#queue-note")).toContainText(
  "All 15 candidate domains have been checked.",
);
await expect(page.locator("#queue-note")).toContainText(
  "13 are in the verified directory",
);
check("Completed queue routes next action to importing new domains");
await page.getByRole("button", { name: "Next page", exact: true }).click();
await expect(page.locator("#results-label")).toHaveText(
  "Showing 13–15 of 15 stores",
);
await page.getByRole("button", { name: "Previous page", exact: true }).click();
await page
  .getByRole("searchbox", { name: "Search stores" })
  .fill("does-not-exist");
await expect(
  page.getByRole("heading", { name: "No stores match this view." }),
).toBeVisible();
await page
  .getByRole("button", { name: "Clear filters", exact: true })
  .first()
  .click();
await expect(page.locator("#results-label")).toHaveText(
  "Showing 1–12 of 15 stores",
);
await page
  .getByRole("combobox", { name: "Indian state", exact: true })
  .selectOption("Karnataka");
await expect(page.locator("#results-label")).toHaveText(
  "Showing 1–12 of 13 stores",
);
await page
  .getByRole("button", { name: "Clear filters", exact: true })
  .first()
  .click();
check("Pagination, empty search and state filter reset");
await page
  .getByRole("button", { name: "Inspect Fixture 01", exact: true })
  .click();
await page.getByRole("button", { name: /^Evidence ·/ }).click();
await expect(page.locator(".evidence-card").first()).toBeVisible();
await page.getByRole("button", { name: "Fetch log", exact: true }).click();
await expect(page.locator(".fetch-item").first()).toBeVisible();
await page.getByRole("button", { name: "Overview", exact: true }).click();
await page.getByLabel("Decision", { exact: true }).selectOption("excluded");
await page
  .getByLabel("What did you check?", { exact: true })
  .fill(
    "Browser fixture: exclude this test merchant to verify export filtering.",
  );
await page
  .getByRole("button", { name: "Save human review", exact: true })
  .click();
await expect(page.locator("#detail-dialog .drawer-summary")).toContainText(
  "Excluded",
);
await expect(page.locator("#review-form")).toContainText(
  "Browser fixture: exclude this test merchant",
);
await page.getByRole("button", { name: "Close store details" }).click();
await page.reload({ waitUntil: "networkidle" });
await page
  .getByRole("searchbox", { name: "Search stores" })
  .fill("fixture-01.in");
await page
  .getByRole("button", { name: "Inspect Fixture 01", exact: true })
  .click();
await expect(page.locator("#detail-dialog .drawer-summary")).toContainText(
  "Excluded",
);
check(
  "Evidence and fetch log display; review decision and note survive reload",
);
await page.getByLabel("Decision", { exact: true }).selectOption("confirmed");
await page
  .getByLabel("What did you check?", { exact: true })
  .fill("Browser fixture: both required evidence checks are present.");
await page
  .getByRole("button", { name: "Save human review", exact: true })
  .click();
await expect(page.locator("#detail-dialog .drawer-summary")).toContainText(
  "Verified",
);
await page
  .getByRole("button", { name: "Requeue for collection", exact: true })
  .click();
await expect(page.locator("#detail-dialog .drawer-summary")).toContainText(
  "Queued",
);
await page.getByRole("button", { name: "Close store details" }).click();
await page
  .getByRole("button", { name: "Collect 1 queued", exact: true })
  .click();
await page
  .getByRole("button", { name: "Start collection", exact: true })
  .click();
await expect(
  page.getByRole("button", { name: "Add domains to collect", exact: true }),
).toBeVisible({ timeout: 20000 });
await page
  .getByRole("button", { name: "Clear filters", exact: true })
  .first()
  .click();
check("Confirm, requeue and recollect a store");
await page.getByRole("button", { name: /^Needs attention/ }).click();
await expect(page.locator("#results-label")).toHaveText(
  "Showing 1–2 of 2 stores",
);
await page
  .getByRole("button", { name: "Inspect Fixture Review", exact: true })
  .click();
await expect(page.locator("#detail-title")).toHaveText("Fixture Review");
await expect(
  page.locator('#review-decision option[value="confirmed"]'),
).toHaveAttribute("disabled", "");
await page.keyboard.press("Escape");
await expect(page.locator("#detail-dialog")).not.toBeVisible();
check(
  "Uncertain and robots-blocked records stay in attention; cannot confirm missing evidence",
);
await page
  .getByRole("button", { name: "Sources & quality", exact: true })
  .click();
await expect(
  page.getByRole("heading", { name: "Field completeness", exact: true }),
).toBeVisible();
await expect(
  page.getByRole("heading", { name: "Browser QA fixture", exact: true }),
).toBeVisible();
check("Sources and completeness views load");
await page.getByRole("button", { name: /^Store explorer/ }).click();
await page.getByRole("button", { name: "Export data", exact: false }).click();
await page.keyboard.press("Escape");
await expect(
  page.getByRole("button", { name: "Export data", exact: false }),
).toBeFocused();
await expect(page.locator("#export-menu")).not.toBeVisible();
check("Export popup supports keyboard dismissal and restores focus");
const exports = await page.evaluate(async () => {
  const results = [];
  for (const f of ["bundle", "csv", "json", "evidence", "report", "audit"]) {
    const r = await fetch("/api/export/" + f);
    results.push({
      format: f,
      status: r.status,
      bytes: (await r.arrayBuffer()).byteLength,
      attachment: r.headers.get("content-disposition"),
    });
  }
  return results;
});
for (const e of exports) {
  assert.equal(e.status, 200);
  assert.ok(e.bytes > 20);
  assert.ok(e.attachment.includes("attachment"));
}
check("All six export formats return nonempty attachments");
await page.getByRole("button", { name: "Export data", exact: false }).click();
const bundleLink = page.getByRole("link", {
  name: "Complete snapshot · ZIP",
  exact: true,
});
const bundleUrl = await bundleLink.getAttribute("href");
await bundleLink.click();
// Tabbit exposes downloads through browser-network fetch, not Playwright events.
const artifact = await page.fetch(bundleUrl, {
  as: "file",
  savePath: artifactPath(`qa-snapshot-${Date.now()}.zip`),
});
assert.ok(artifact.ok);
check("ZIP link is actionable and its attachment saves successfully");
await page.route("**/api/overview", (route) => route.abort("failed"));
await page.getByRole("button", { name: "Refresh data", exact: true }).click();
await expect(page.locator("#connection-error")).toContainText(
  "Could not refresh",
);
await expect(page.locator(".local-badge")).toContainText("Reconnecting");
await page.unroute("**/api/overview");
await page.getByRole("button", { name: "Refresh data", exact: true }).click();
await expect(page.locator("#connection-error")).not.toBeVisible();
check("Connection failure is visible and recovers without reload");
assert.equal(globalThis.qaErrors.length, 0);
return { checks, exports, pageErrors: globalThis.qaErrors };
