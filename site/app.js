const $ = (selector) => document.querySelector(selector);
const escapeHtml = (value) => String(value ?? "").replace(/[&<>"']/g, (char) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[char]);
const safeUrl = (value) => {
  try {
    const url = new URL(value);
    return ["https:", "http:"].includes(url.protocol) ? url.href : null;
  } catch { return null; }
};
const link = (url, label) => {
  const href = safeUrl(url);
  return href ? `<a href="${escapeHtml(href)}" target="_blank" rel="noopener noreferrer">${escapeHtml(label)} ↗</a>` : escapeHtml(label);
};
const nameOf = (store) => {
  try { return new URL(store.domain_url).hostname.replace(/^www\./, ""); }
  catch { return store.domain_url; }
};
const coverageKeys = ["emails", "phones", "socials", "category", "description", "logo_url", "state"];
const hasValue = (value) => Array.isArray(value) ? value.length > 0 : value && typeof value === "object" ? Object.keys(value).length > 0 : Boolean(value);
const coverage = (store) => coverageKeys.filter((key) => hasValue(store[key])).length;
const fmt = (value) => Number(value).toLocaleString("en-IN");
const state = { stores: [], report: null, query: "", category: "", region: "", sort: "name", page: 1, pageSize: 18, currentId: null };

function logo(store) {
  const letter = nameOf(store).slice(0, 1).toUpperCase();
  const url = safeUrl(store.logo_url);
  return `<span class="store-logo" data-fallback="${escapeHtml(letter)}">${url ? `<img src="${escapeHtml(url)}" alt="" loading="lazy" referrerpolicy="no-referrer">` : escapeHtml(letter)}</span>`;
}

function filteredStores() {
  const query = state.query.toLocaleLowerCase().trim();
  const stores = state.stores.filter((store) =>
    (!state.category || store.category === state.category) &&
    (!state.region || store.state === state.region) &&
    (!query || [nameOf(store), store.category, store.state, store.description].some((part) => String(part || "").toLocaleLowerCase().includes(query)))
  );
  stores.sort((a, b) => {
    if (state.sort === "coverage") return coverage(b) - coverage(a) || nameOf(a).localeCompare(nameOf(b));
    if (state.sort === "newest") return b.observed_at.localeCompare(a.observed_at) || nameOf(a).localeCompare(nameOf(b));
    return nameOf(a).localeCompare(nameOf(b));
  });
  return stores;
}

function renderStores() {
  const stores = filteredStores();
  const pages = Math.max(1, Math.ceil(stores.length / state.pageSize));
  state.page = Math.min(state.page, pages);
  const first = (state.page - 1) * state.pageSize;
  $("#store-grid").innerHTML = stores.slice(first, first + state.pageSize).map((store) =>
    `<article class="store-card"><div class="card-top">${logo(store)}<div class="card-name"><strong>${escapeHtml(nameOf(store))}</strong><span>${escapeHtml(store.domain_url)}</span></div><span class="verified">✓ Verified</span></div><p>${escapeHtml(store.description || "A verified Indian Shopify storefront. Open the record for extracted details and evidence.")}</p><div class="card-bottom">${store.category ? `<span class="chip" title="${escapeHtml(store.category)}">${escapeHtml(store.category)}</span>` : ""}${store.state ? `<span class="chip">${escapeHtml(store.state)}</span>` : ""}<button class="inspect" type="button" data-id="${escapeHtml(store.store_id)}" aria-label="Inspect evidence for ${escapeHtml(nameOf(store))}">Inspect evidence →</button></div></article>`
  ).join("");
  $("#empty").hidden = stores.length > 0;
  $("#result-summary").textContent = stores.length ? `Showing ${fmt(first + 1)}–${fmt(Math.min(first + state.pageSize, stores.length))} of ${fmt(stores.length)} stores` : "No matching stores";
  $("#page-label").textContent = `${state.page} / ${pages}`;
  $("#previous").disabled = state.page === 1;
  $("#next").disabled = state.page === pages;
}

function renderSummary() {
  const report = state.report;
  $("#metric-stores").textContent = fmt(report.accepted);
  $("#metric-candidates").textContent = fmt(report.total);
  $("#directory-count").textContent = fmt(report.accepted);
  const present = Object.values(report.missingness).reduce((sum, field) => sum + field.present, 0);
  $("#metric-coverage").textContent = `${Math.round(100 * present / (report.accepted * 7))}%`;
  const labels = { emails: "Emails", phones: "Phones", socials: "Social profiles", category: "Category", description: "Description", logo_url: "Brand logo", state: "State" };
  $("#coverage-bars").innerHTML = Object.entries(report.missingness).map(([key, field]) => {
    const percent = Math.round(100 * field.present / report.accepted);
    return `<div class="coverage-row"><span>${labels[key]}</span><progress max="100" value="${percent}" aria-label="${labels[key]} coverage"></progress><b>${percent}%</b></div>`;
  }).join("");
  $("#source-list").innerHTML = report.sources.map((source) => `<div class="source-item">${link(source.source_url, source.name)}<span>${fmt(source.candidates)} candidates · ${fmt(source.accepted)} accepted</span></div>`).join("");
  for (const [selector, field] of [["#category", "category"], ["#state", "state"]]) {
    const select = $(selector);
    const values = [...new Set(state.stores.map((store) => store[field]).filter(Boolean))].sort((a, b) => a.localeCompare(b));
    for (const value of values) select.add(new Option(value, value));
  }
}

function valuesHtml(values, kind) {
  if (!hasValue(values)) return `<p>Not found in the allowed pages.</p>`;
  if (kind === "emails") return `<div class="value">${values.map((value) => `<a href="mailto:${escapeHtml(value)}">${escapeHtml(value)}</a>`).join("")}</div>`;
  if (kind === "phones") return `<div class="value">${values.map((value) => `<a href="tel:${escapeHtml(value)}">${escapeHtml(value)}</a>`).join("")}</div>`;
  if (kind === "socials") return `<div class="value">${Object.entries(values).flatMap(([network, urls]) => urls.map((url) => link(url, network))).join("")}</div>`;
  return `<div class="value"><span>${escapeHtml(values)}</span></div>`;
}

function evidenceHtml(item) {
  return `<article class="evidence-item"><div><span>${escapeHtml(item.field)}</span><small>${escapeHtml(item.rule)}</small></div><p>${escapeHtml(item.excerpt || JSON.stringify(item.value))}</p>${link(item.source_url, "Open merchant page")} <small>· ${escapeHtml((item.observed_at || "").slice(0, 10))} · hash ${escapeHtml((item.content_hash || "").slice(0, 12))}</small></article>`;
}

async function openDetail(storeId) {
  const store = state.stores.find((entry) => entry.store_id === storeId);
  if (!store) return;
  state.currentId = storeId;
  const dialog = $("#detail");
  const body = $("#detail-body");
  body.innerHTML = `<div class="detail-heading">${logo(store)}<div><h2>${escapeHtml(nameOf(store))}</h2>${link(store.domain_url, "Visit store")}</div></div><div class="detail-status"><span>✓ Shopify storefront</span><span>✓ Indian business evidence</span><span>${coverage(store)}/7 fields present</span><span>Observed ${escapeHtml(store.observed_at.slice(0, 10))}</span></div>${store.description ? `<blockquote class="detail-description">“${escapeHtml(store.description)}”</blockquote>` : ""}<div class="detail-grid"><div class="detail-block"><h3>Category</h3>${valuesHtml(store.category, "category")}</div><div class="detail-block"><h3>Indian state</h3>${valuesHtml(store.state, "state")}</div><div class="detail-block"><h3>Email contacts</h3>${valuesHtml(store.emails, "emails")}</div><div class="detail-block"><h3>Phone contacts</h3>${valuesHtml(store.phones, "phones")}</div><div class="detail-block"><h3>Social profiles</h3>${valuesHtml(store.socials, "socials")}</div><div class="detail-block"><h3>Brand logo</h3>${store.logo_url ? link(store.logo_url, "View original image") : "<p>Not found in the allowed pages.</p>"}</div></div><section class="detail-evidence"><h3>Source evidence</h3><div class="loading" id="evidence-list">Loading merchant page evidence…</div></section>`;
  if (!dialog.open) dialog.showModal();
  try {
    const response = await fetch(`data/evidence/${encodeURIComponent(storeId)}.json`);
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const record = await response.json();
    if (state.currentId !== storeId) return;
    const sources = record.sources || [];
    $("#evidence-list").innerHTML = `<p>${fmt((record.evidence || []).length)} observations from merchant pages. These are rule matches, not a human audit.</p><div class="detail-block"><h3>Discovery sources</h3><div class="value">${sources.map((source) => link(source.source_url, source.name)).join("")}</div></div>${(record.evidence || []).map(evidenceHtml).join("")}`;
  } catch {
    if (state.currentId === storeId) $("#evidence-list").textContent = "Evidence could not be loaded. The complete JSONL is available in Downloads.";
  }
}

function clearFilters() {
  state.query = state.category = state.region = "";
  state.page = 1;
  $("#search").value = "";
  $("#category").value = "";
  $("#state").value = "";
  renderStores();
}

document.addEventListener("click", (event) => {
  const button = event.target.closest("button[data-id]");
  if (button) openDetail(button.dataset.id);
});
document.addEventListener("error", (event) => {
  if (event.target instanceof HTMLImageElement && event.target.closest(".store-logo")) {
    const parent = event.target.closest(".store-logo");
    parent.textContent = parent.dataset.fallback;
  }
}, true);
$("#detail-close").addEventListener("click", () => $("#detail").close());
$("#detail").addEventListener("click", (event) => { if (event.target === $("#detail")) $("#detail").close(); });
$("#search").addEventListener("input", (event) => { state.query = event.target.value; state.page = 1; renderStores(); });
$("#category").addEventListener("change", (event) => { state.category = event.target.value; state.page = 1; renderStores(); });
$("#state").addEventListener("change", (event) => { state.region = event.target.value; state.page = 1; renderStores(); });
$("#sort").addEventListener("change", (event) => { state.sort = event.target.value; state.page = 1; renderStores(); });
$("#clear").addEventListener("click", clearFilters);
$("#empty-clear").addEventListener("click", clearFilters);
$("#previous").addEventListener("click", () => { state.page--; renderStores(); $("#directory").scrollIntoView(); });
$("#next").addEventListener("click", () => { state.page++; renderStores(); $("#directory").scrollIntoView(); });

async function init() {
  try {
    const [storesResponse, reportResponse] = await Promise.all([fetch("data/stores.json"), fetch("data/run-report.json")]);
    if (!storesResponse.ok || !reportResponse.ok) throw new Error("Snapshot files were not available.");
    state.stores = await storesResponse.json();
    state.report = await reportResponse.json();
    if (state.stores.length !== state.report.accepted) throw new Error("Snapshot count mismatch.");
    renderSummary();
    renderStores();
  } catch (error) {
    $("#result-summary").textContent = `Could not load the published snapshot: ${error.message}`;
    $("#store-grid").innerHTML = `<div class="empty"><strong>Dataset unavailable</strong><p>Please use the files in the GitHub repository.</p></div>`;
  }
}
init();
