const $ = (selector, scope = document) => scope.querySelector(selector);
const $$ = (selector, scope = document) => [
  ...scope.querySelectorAll(selector),
];
const escape = (value) =>
  String(value ?? "").replace(
    /[&<>"']/g,
    (c) =>
      ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[
        c
      ],
  );
const icons = {
  grid: '<rect x="3" y="3" width="7" height="7" rx="1.5"/><rect x="14" y="3" width="7" height="7" rx="1.5"/><rect x="3" y="14" width="7" height="7" rx="1.5"/><rect x="14" y="14" width="7" height="7" rx="1.5"/>',
  check:
    '<path d="M9 12l2 2 4-4"/><path d="M12 3l8 4v6c0 4-8 8-8 8s-8-4-8-8V7z"/>',
  activity: '<path d="M3 12h4l3-8 4 16 3-8h4"/>',
  layers: '<path d="M12 3L2 8l10 5 10-5zM3 13l9 5 9-5M3 18l9 5 9-5"/>',
  lock: '<rect x="5" y="10" width="14" height="11" rx="2"/><path d="M8 10V7a4 4 0 018 0v3M12 14v3"/>',
  compass: '<circle cx="12" cy="12" r="9"/><path d="M16 8l-3 5-5 3 3-5z"/>',
  plus: '<path d="M12 5v14M5 12h14"/>',
  play: '<path d="M8 5l11 7-11 7z"/>',
  download: '<path d="M12 3v12m-4-4l4 4 4-4M5 16v5h14v-5"/>',
  chevron: '<path d="M7 10l5 5 5-5"/>',
  search: '<circle cx="10.5" cy="10.5" r="6.5"/><path d="M16 16l5 5"/>',
  tag: '<path d="M3 3h8l10 10-8 8L3 11z"/><circle cx="7.5" cy="7.5" r="1"/>',
  pin: '<path d="M19 10c0 5-7 11-7 11S5 15 5 10a7 7 0 1114 0z"/><circle cx="12" cy="10" r="2.5"/>',
  refresh:
    '<path d="M20 8a8 8 0 00-14-3L3 8m0-5v5h5M4 16a8 8 0 0014 3l3-3m0 5v-5h-5"/>',
  left: '<path d="M14 6l-6 6 6 6"/>',
  right: '<path d="M9 6l6 6-6 6"/>',
  arrow: '<path d="M5 12h14m-5-5l5 5-5 5"/>',
  external: '<path d="M14 3h7v7m0-7L10 14M10 3H4v17h17v-6"/>',
  shield:
    '<path d="M12 3l8 4v6c0 4-8 8-8 8s-8-4-8-8V7z"/><path d="M9 12l2 2 4-4"/>',
  globe:
    '<circle cx="12" cy="12" r="9"/><ellipse cx="12" cy="12" rx="4" ry="9"/><path d="M3 12h18"/>',
  chart: '<path d="M4 20V4m0 16h17M8 16v-5m5 5V7m5 9v-8"/>',
  clock: '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>',
  file: '<path d="M14 2H5v20h14V7zM14 2v5h5M8 12h8m-8 4h6"/>',
};
const icon = (name) =>
  `<svg class="icon" viewBox="0 0 24 24" aria-hidden="true">${icons[name] || icons.file}</svg>`;
function hydrateIcons(scope = document) {
  $$("[data-icon]", scope).forEach((el) => {
    el.innerHTML = icon(el.dataset.icon);
  });
}
hydrateIcons();

const state = {
  view: "explorer",
  status: "all",
  page: 1,
  q: "",
  category: "",
  region: "",
  overview: null,
  runs: [],
  detail: null,
  detailTab: "overview",
  requestId: 0,
};
const labels = {
  accepted: "Verified",
  review: "Needs review",
  queued: "Queued",
  blocked: "Blocked",
  unreachable: "Unreachable",
  error: "Error",
  duplicate: "Duplicate",
  excluded: "Excluded",
  stale: "Needs refresh",
  completed: "Completed",
  running: "Running",
  interrupted: "Interrupted",
  cancelled: "Paused",
  failed: "Failed",
};
const names = {
  emails: "Email",
  phones: "Phone",
  socials: "Social profiles",
  category: "Category",
  description: "Description",
  logo_url: "Brand logo",
  state: "State",
};
const fieldOrder = Object.keys(names);
const has = (value) =>
  value && (typeof value !== "object" || Object.keys(value).length > 0);
const coverage = (store) =>
  store ? fieldOrder.filter((f) => has(store[f])).length : 0;
const hostname = (url) => {
  try {
    return new URL(url).hostname.replace(/^www\./, "");
  } catch {
    return url;
  }
};
const date = (value) =>
  value
    ? new Date(value).toLocaleString(undefined, {
        month: "short",
        day: "numeric",
        hour: "2-digit",
        minute: "2-digit",
      })
    : "Not collected";
const badge = (status) =>
  `<span class="badge ${escape(status)}">${escape(labels[status] || status)}</span>`;
function link(url, label, cls = "") {
  try {
    if (!["https:", "http:"].includes(new URL(url).protocol))
      return escape(label);
  } catch {
    return escape(label);
  }
  return `<a href="${escape(url)}" target="_blank" rel="noopener noreferrer" class="${cls}">${escape(label)}</a>`;
}
function logo(row, large = false) {
  const store = row.store || {},
    letter = (store.name || hostname(row.url)).slice(0, 1).toUpperCase();
  return `<span class="store-logo ${store.logo_background === "dark" ? "dark-logo" : ""}">${store.logo_path ? `<img src="/api/logos/${escape(row.id)}?v=${escape(store.rule_version)}" alt="${escape(store.name || hostname(row.url))} logo" loading="lazy"><span class="store-monogram" hidden>${escape(letter)}</span>` : `<span class="store-monogram" aria-label="Initial placeholder">${escape(letter)}</span>`}</span>`;
}
document.addEventListener(
  "error",
  (event) => {
    if (event.target instanceof HTMLImageElement) {
      event.target.hidden = true;
      if (event.target.nextElementSibling)
        event.target.nextElementSibling.hidden = false;
    }
  },
  true,
);
async function api(path, options = {}) {
  const response = await fetch(path, {
    signal: AbortSignal.timeout(30000),
    ...options,
    headers: {
      "Content-Type": "application/json",
      "X-Rivyou-Request": "1",
      ...(options.headers || {}),
    },
  });
  if (!response.ok) {
    let problem;
    try {
      problem = await response.json();
    } catch {}
    const error = new Error(
      typeof problem?.detail === "string"
        ? problem.detail
        : Array.isArray(problem?.detail)
          ? problem.detail.map((x) => `${x.loc.at(-1)}: ${x.msg}`).join("; ")
          : `Request failed (${response.status}).`,
    );
    error.code = problem?.code;
    throw error;
  }
  return response.json();
}
let toastTimer;
function toast(message) {
  $("#toast").textContent = message;
  $("#toast").hidden = false;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => {
    $("#toast").hidden = true;
  }, 5500);
}
function errorBanner(message = "") {
  $("#connection-error").hidden = !message;
  $("#connection-error").textContent = message;
  $(".local-badge").innerHTML =
    `<span class="status-dot ${message ? "disconnected" : ""}"></span>${message ? "Reconnecting" : "Local"}`;
}
async function busy(button, fn) {
  const old = button.innerHTML;
  button.disabled = true;
  button.textContent = "Working…";
  try {
    await fn();
  } finally {
    button.disabled = false;
    button.innerHTML = old;
  }
}
function metric(label, value, caption, iconName, suffix = "") {
  return `<article class="metric"><div class="metric-top"><span>${label}</span><span class="metric-icon">${icon(iconName)}</span></div><div class="metric-value">${value}<small>${suffix}</small></div><div class="metric-caption"><span class="micro-dot"></span>${caption}</div></article>`;
}
function renderMetrics() {
  const s = state.overview;
  if (!s) return;
  const filled = Object.values(s.missingness).reduce(
    (a, x) => a + x.present,
    0,
  );
  const complete = s.accepted
    ? Math.round((100 * filled) / (s.accepted * 7))
    : null;
  const attention = [
    "review",
    "blocked",
    "unreachable",
    "error",
    "stale",
  ].reduce((n, k) => n + (s.counts[k] || 0), 0);
  $("#metrics").innerHTML =
    metric(
      "Verified stores",
      s.accepted.toLocaleString(),
      "Shopify + Indian business evidence",
      "shield",
      "/ 1,000",
    ) +
    metric(
      "Candidate domains",
      s.total.toLocaleString(),
      `${s.counts.queued || 0} waiting to be collected`,
      "globe",
    ) +
    metric(
      "Field coverage",
      complete === null ? "—" : complete,
      s.accepted
        ? "Across seven fields · verified stores"
        : "Available after stores pass both checks",
      "chart",
      complete === null ? "" : "%",
    ) +
    metric(
      "Discovery sources",
      s.sources.length,
      `${s.requests.toLocaleString()} HTTP responses recorded`,
      "layers",
    );
  $("#nav-total").textContent = s.total;
  $("#nav-review").textContent = attention;
  $("#directory-count").textContent =
    state.view === "review" ? attention : s.total;
  $("#updated-at").textContent = "Updated " + date(s.generated_at);
  const queued = s.counts.queued || 0,
    running = state.runs.some((r) => r.status === "running"),
    action = $("#run-open"),
    note = $("#queue-note");
  $("#import-open").hidden = queued === 0 && !running;
  action.disabled = running;
  action.innerHTML = running
    ? `${icon("activity")}Collection in progress`
    : queued
      ? `${icon("play")}Collect ${queued} queued`
      : `${icon("plus")}Add domains to collect`;
  note.hidden = queued > 0 || running || s.total === 0;
  if (!note.hidden)
    note.innerHTML = `<strong>All ${s.total} candidate domains have been checked.</strong> ${s.accepted} are in the verified directory. Add new candidate domains to run another collection.`;
  const starterImported = s.sources.some(
    (source) =>
      source.source_url ===
      "https://www.shopify.com/in/blog/look-good-perform-better-19-websites-built-on-shopify-that-are-a-visual-delight",
  );
  $("#starter-import").hidden = starterImported;
  $("#starter-hint").textContent = starterImported
    ? "The built-in starter list has already been imported. Add domains from another public source and include its URL."
    : "The starter list comes from a 2022 Shopify article. It contains candidates, not verified records.";
  renderTabs();
}
function renderTabs() {
  const c = state.overview?.counts || {};
  const tabs =
    state.view === "review"
      ? [
          [
            "attention",
            "All issues",
            ["review", "blocked", "unreachable", "error", "stale"].reduce(
              (n, k) => n + (c[k] || 0),
              0,
            ),
          ],
          ["review", "Needs review", c.review || 0],
          ["blocked", "Blocked", c.blocked || 0],
          ["unreachable", "Unreachable", c.unreachable || 0],
        ]
      : [
          ["all", "All stores", state.overview?.total || 0],
          ["accepted", "Verified", c.accepted || 0],
          ["review", "Needs review", c.review || 0],
          ["queued", "Queued", c.queued || 0],
          ["blocked", "Blocked", c.blocked || 0],
        ];
  $("#status-tabs").innerHTML = tabs
    .map(
      ([key, label, count]) =>
        `<button class="status-tab ${state.status === key ? "active" : ""}" data-status="${key}" aria-pressed="${state.status === key}">${label}<span>${count}</span></button>`,
    )
    .join("");
}
function renderRunBanner() {
  const active = state.runs.find((r) => r.status === "running"),
    el = $("#active-run");
  el.hidden = !active;
  if (!active) return;
  el.innerHTML = `<span class="spinner" aria-hidden="true"></span><div><strong>${active.pause_requested ? "Saving progress before pausing" : "Collecting evidence"}</strong><span> · ${active.completed} of ${active.total} candidates checked</span></div><div class="run-progress" role="progressbar" aria-label="Collection progress" aria-valuenow="${active.completed}" aria-valuemin="0" aria-valuemax="${active.total}"><span style="width:${active.total ? (100 * active.completed) / active.total : 0}%"></span></div><button class="text-action" data-pause="${active.id}" ${active.pause_requested ? "disabled" : ""}>${active.pause_requested ? "Pause requested" : "Pause collection"}</button>`;
}
function setOptions(select, values, selected, first) {
  const current = [...select.options].map((o) => o.value).join("|");
  if (current !== ["", ...values].join("|"))
    select.innerHTML =
      `<option value="">${first}</option>` +
      values
        .map((v) => `<option value="${escape(v)}">${escape(v)}</option>`)
        .join("");
  select.value = selected;
}
async function loadStores() {
  const id = ++state.requestId;
  const params = new URLSearchParams({
    q: state.q,
    status: state.status,
    category: state.category,
    state: state.region,
    page: state.page,
    per_page: 12,
  });
  const data = await api("/api/stores?" + params);
  if (id !== state.requestId) return;
  $("#clear-filters").hidden = !(state.q || state.category || state.region);
  const totalPages = Math.max(1, Math.ceil(data.total / 12));
  if (state.page > totalPages) {
    state.page = totalPages;
    return loadStores();
  }
  setOptions(
    $("#category-filter"),
    data.filters.categories,
    state.category,
    "All categories",
  );
  setOptions(
    $("#state-filter"),
    data.filters.states,
    state.region,
    "All states",
  );
  $("#store-rows").innerHTML = data.items
    .map((row, index) => {
      const store = row.store || {},
        n = coverage(store);
      return `<tr><td class="row-index">${String((state.page - 1) * 12 + index + 1).padStart(2, "0")}</td><td><div class="store-cell">${logo(row)}<button class="store-open" data-store="${row.id}" aria-label="Inspect ${escape(store.name || hostname(row.url))}"><span class="store-name">${escape(store.name || hostname(row.url))}</span><span class="store-domain">${escape(hostname(store.domain_url || row.url))}</span></button></div></td><td>${store.category ? `<span class="category-pill">${escape(store.category)}</span>` : '<span class="muted-value">Not established</span>'}</td><td>${store.state ? `<span class="location">${icon("pin")}${escape(store.state)}</span>` : '<span class="muted-value">Not established</span>'}</td><td><div class="coverage" title="${n} of 7 fields found" aria-label="${n} of 7 fields found">${fieldOrder.map((f) => `<i class="${has(store[f]) ? "filled" : ""}"></i>`).join("")}<span>${n}/7</span></div></td><td>${badge(row.status)}</td><td><button class="row-arrow" data-store="${row.id}" aria-label="Open evidence for ${escape(store.name || hostname(row.url))}">${icon("right")}</button></td></tr>`;
    })
    .join("");
  $("#empty-state").hidden = !!data.items.length;
  if (!data.items.length) {
    const empty = !state.overview?.total;
    $("#empty-state").innerHTML =
      `<div class="empty-symbol">${icon(empty ? "compass" : "search")}</div><h3>${empty ? "Your first discovery starts here." : "No stores match this view."}</h3><p>${empty ? "Import your candidate domains or start with 19 sites mentioned by Shopify. Each one will be checked before it is marked verified." : "Try another filter, or inspect all candidates to see the evidence collected so far."}</p><button class="button secondary" id="empty-action">${empty ? "Import candidates" : "Clear filters"} ${icon("arrow")}</button>`;
  }
  $("#results-label").textContent = data.total
    ? `Showing ${(state.page - 1) * 12 + 1}–${Math.min(state.page * 12, data.total)} of ${data.total} stores`
    : "No matching records";
  $("#page-number").textContent = `${state.page} / ${totalPages}`;
  $("#previous").disabled = state.page <= 1;
  $("#next").disabled = state.page >= totalPages;
}
function renderRuns() {
  const runs = state.runs;
  $("#runs-view").innerHTML =
    `<div class="content-card"><div class="section-top"><div><h2>Collection history <span class="count-badge">${runs.length}</span></h2><p>Progress and request totals are saved locally as the crawler works.</p></div></div>${
      runs.length
        ? runs
            .map((r) => {
              const seconds = Math.max(
                0,
                Math.round(
                  (new Date(r.finished_at || Date.now()) -
                    new Date(r.started_at)) /
                    1000,
                ),
              );
              return `<article class="run-card"><span>${icon("activity")}</span><div class="run-card-info"><h3>Collection ${escape(r.id.slice(0, 8))}</h3><p>${date(r.started_at)} · ${r.completed}/${r.total} candidates · ${r.requests} responses</p>${r.error ? `<p>${escape(r.error)}</p>` : ""}</div><div class="run-card-meta">${badge(r.status)}<small>${Math.floor(seconds / 60)}m ${seconds % 60}s · ${(r.bytes / 1024 / 1024).toFixed(1)} MB</small></div>${["interrupted", "cancelled", "failed"].includes(r.status) && r.completed < r.total ? `<button class="button secondary compact" data-resume="${r.id}">Resume</button>` : ""}</article>`;
            })
            .join("")
        : '<div class="empty-state"><div class="empty-symbol">' +
          icon("activity") +
          "</div><h3>No collection runs yet.</h3><p>Import some candidates, then start a bounded collection.</p></div>"
    }</div><div class="callout">Pausing saves completed pages. Resuming an interrupted run reuses its saved HTML. A completed run with missing evidence can be revisited by requeuing an individual store.</div>`;
}
function renderSources() {
  const s = state.overview;
  if (!s) return;
  $("#sources-view").innerHTML =
    `<div class="quality-grid"><section class="content-card"><h2>Field completeness</h2><p>Measured on ${s.accepted} verified records. Unknown values are not filled in.</p>${Object.entries(
      s.missingness,
    )
      .map(([key, v]) => {
        const percent = s.accepted
          ? Math.round((100 * v.present) / s.accepted)
          : 0;
        return `<div class="quality-row"><span>${names[key]}</span><div class="quality-bar"><span style="width:${percent}%"></span></div><strong>${s.accepted ? percent + "%" : "—"}</strong></div>`;
      })
      .join(
        "",
      )}</section><section class="content-card"><h2>Verification & audit</h2><p>Both platform and location need evidence before a store appears in the verified export.</p><div class="reason-box">Current status: <strong>${escape(s.audit_status)}</strong>.<br>Automated verification is not a measured accuracy score.</div><p>Download a reproducible random sample for review. It includes unfilled checks and the exact population hash.</p><a class="button secondary" href="/api/export/audit">${icon("download")}Download audit sample</a><p>Rule version ${escape(s.rule_version)} · schema ${escape(s.schema_version)}</p></section></div><section class="content-card"><h2>Where candidates came from</h2><p>Sources are leads. Every candidate must still pass current site checks. A domain found in two sources is counted in each source row.</p>${s.sources.length ? s.sources.map((source) => `<article class="source-card"><h3>${escape(source.name)}</h3><p>${source.candidates} candidates · ${source.collected} collected · ${source.accepted} currently verified</p>${link(source.source_url, "Open source ↗")}</article>`).join("") : '<div class="empty-state"><h3>No sources imported.</h3><p>A source name and URL are required with every import.</p></div>'}</section>`;
}
let pendingRefresh = null,
  lastRefresh = 0;
function refresh() {
  if (!pendingRefresh)
    pendingRefresh = refreshWorkspace().finally(() => {
      pendingRefresh = null;
    });
  return pendingRefresh;
}
async function refreshWorkspace() {
  lastRefresh = Date.now();
  try {
    const [overview, runs] = await Promise.all([
      api("/api/overview"),
      api("/api/runs"),
    ]);
    state.overview = overview;
    state.runs = runs;
    errorBanner();
    renderMetrics();
    renderRunBanner();
    if (["explorer", "review"].includes(state.view)) await loadStores();
    else if (state.view === "runs") renderRuns();
    else renderSources();
  } catch (error) {
    errorBanner("Could not refresh the workspace. " + error.message);
  }
}
function switchView(view) {
  state.view = view;
  state.status = view === "review" ? "attention" : "all";
  state.page = 1;
  closeExport();
  const texts = {
    explorer: [
      "Store explorer",
      "Discover businesses. Check the details. Keep the evidence.",
    ],
    review: [
      "Needs attention",
      "Look at the uncertain cases before making a decision.",
    ],
    runs: [
      "Collection runs",
      "A record of what ran, what finished, and what needs another look.",
    ],
    sources: [
      "Sources & quality",
      "Understand where the data came from and what is still missing.",
    ],
  };
  $("#page-title").textContent = texts[view][0];
  $("#page-description").textContent = texts[view][1];
  $("#breadcrumb-label").textContent = texts[view][0];
  $$(".nav-item").forEach((el) => {
    el.classList.toggle("active", el.dataset.view === view);
    if (el.dataset.view === view) el.setAttribute("aria-current", "page");
    else el.removeAttribute("aria-current");
  });
  $("#explorer-view").hidden = !["explorer", "review"].includes(view);
  $("#runs-view").hidden = view !== "runs";
  $("#sources-view").hidden = view !== "sources";
  $("#table-title").innerHTML =
    (view === "review" ? "Records to inspect" : "Your store directory") +
    ' <span id="directory-count" class="count-badge">0</span>';
  renderMetrics();
  refresh();
}
function displayValue(store, field) {
  const value = store[field];
  if (!has(value))
    return `<span class="muted-value">Not found · ${escape((store.missing?.[field] || "not_collected").replaceAll("_", " "))}</span>`;
  if (field === "emails")
    return value
      .map((v) => `<a href="mailto:${escape(v)}">${escape(v)}</a>`)
      .join("");
  if (field === "phones")
    return value
      .map((v) => `<a href="tel:${escape(v)}">${escape(v)}</a>`)
      .join("");
  if (field === "socials")
    return Object.entries(value)
      .flatMap(([network, urls]) =>
        urls.map((url) => link(url, network + " ↗")),
      )
      .join("");
  return escape(value);
}
function renderDetail() {
  const row = state.detail;
  if (!row) return;
  const store = row.store || {};
  const content = $("#detail-content");
  const focusedTab = document.activeElement?.dataset.detailTab;
  let body = "";
  if (state.detailTab === "overview") {
    body = `<div class="check-grid"><div class="check-card ${store.shopify === "verified" ? "" : "unsupported"}"><small>SHOPIFY STOREFRONT</small><strong>${icon("shield")}${store.shopify === "verified" ? "Supported" : "Needs evidence"}</strong></div><div class="check-card ${store.india === "verified" ? "" : "unsupported"}"><small>INDIAN BUSINESS</small><strong>${icon("pin")}${store.india === "verified" ? "Supported" : "Needs evidence"}</strong></div></div>${store.description ? `<div class="description">“${escape(store.description)}”</div>` : ""}${["category", "state", "emails", "phones", "socials"].map((field) => `<div class="detail-field"><span class="field-label">${names[field]}</span><div class="field-value">${displayValue(store, field)}</div></div>`).join("")}<div class="detail-field"><span class="field-label">Brand logo</span><div class="field-value">${store.logo_url ? link(store.logo_url, "View original image ↗") : '<span class="muted-value">No brand logo validated</span>'}</div></div><div class="detail-field"><span class="field-label">Discovery source</span><div class="field-value">${row.sources.map((s) => link(s.source_url, s.name + " ↗")).join("")}</div></div><div class="reason-box">${escape(store.reason || "This candidate has not been collected yet.")}</div>${row.duplicate_of ? `<p class="muted">This aliases record ${escape(row.duplicate_of)} and is excluded from duplicate counting.</p>` : ""}${store.aliases?.length > 1 ? `<div class="detail-field"><span class="field-label">Observed aliases</span><div class="field-value">${store.aliases.map((a) => link(a, hostname(a))).join("")}</div></div>` : ""}${row.store ? `<button class="button secondary" id="requeue-store" ${state.runs.some((r) => r.status === "running") ? 'disabled title="Wait for the current collection to finish"' : ""}>${icon("refresh")}Requeue for collection</button><form id="review-form" class="review-form"><h3>Record a review</h3><p>A review never invents missing platform or location evidence. Your decision is saved alongside the original result.</p><label>Decision<select id="review-decision" aria-label="Decision"><option value="needs_review">Keep in review</option><option value="confirmed" ${store.shopify !== "verified" || store.india !== "verified" ? "disabled" : ""}>Confirm existing evidence</option><option value="excluded">Exclude from export</option></select></label><label>What did you check?<textarea id="review-note" minlength="10" maxlength="2000" required rows="3" placeholder="Record the page and reason for your decision."></textarea></label><button type="submit" class="button primary">Save human review</button><p>${row.review ? `Last review: ${escape(row.review.decision.replaceAll("_", " "))} · ${escape(row.review.reviewer)} · ${date(row.review.reviewed_at)}${row.review_current ? "" : " · older evidence"}<br>${escape(row.review.note)}` : "No review has been recorded."}</p></form>` : ""}`;
  } else if (state.detailTab === "evidence") {
    const evidence = store.evidence || [];
    body = evidence.length
      ? `<p class="form-hint" style="margin:0 0 18px">${evidence.length} observations tied to source pages. These are extracted facts and rule matches, not independent audit results.</p>` +
        evidence
          .map(
            (e) =>
              `<article class="evidence-card"><div class="evidence-card-head"><strong>${escape(names[e.field] || e.field)}</strong><span class="evidence-family">${escape(e.family || "extraction")}</span></div><blockquote>${escape(e.excerpt || JSON.stringify(e.value))}</blockquote>${link(e.source_url, hostname(e.source_url) + new URL(e.source_url).pathname, "external-link")}<small>${escape(e.rule)} · ${date(e.observed_at)}</small><small>Snapshot ${escape(e.content_hash.slice(0, 12))}</small></article>`,
          )
          .join("")
      : '<div class="empty-state"><div class="empty-symbol">' +
        icon("file") +
        "</div><h3>No evidence collected yet.</h3><p>Run a collection or inspect the fetch log to see what stopped it.</p></div>";
  } else {
    body = row.observations.length
      ? row.observations
          .map(
            (o) =>
              `<article class="fetch-item"><div class="fetch-top"><span class="badge ${o.outcome === "ok" ? "accepted" : "review"}">${escape(o.status_code || o.outcome)}</span><strong>${escape(o.kind)}</strong></div><span class="fetch-url">${escape(o.url)}</span><div class="fetch-meta">${date(o.observed_at)} · ${(o.bytes / 1024).toFixed(1)} KB · ${o.elapsed_ms} ms</div>${o.detail ? `<p class="fetch-url">${escape(o.detail)}</p>` : ""}</article>`,
          )
          .join("")
      : '<div class="empty-state"><h3>No requests yet.</h3><p>This candidate is waiting for a collection.</p></div>';
  }
  content.innerHTML = `<div class="drawer-head"><span class="eyebrow">STORE RECORD</span><button class="icon-button drawer-close close-dialog" aria-label="Close store details">×</button><div class="drawer-brand">${logo(row, true)}<div><h2 id="detail-title">${escape(store.name || hostname(row.url))}</h2>${link(store.domain_url || row.url, hostname(store.domain_url || row.url) + " ↗", "external-link")}</div></div><div class="drawer-summary">${badge(row.status)}<span>${coverage(store)}/7 fields · ${store.pages_checked || 0} pages checked</span></div></div><div class="drawer-tabs" role="group" aria-label="Store detail sections">${[
    ["overview", "Overview"],
    ["evidence", "Evidence"],
    ["fetches", "Fetch log"],
  ]
    .map(
      ([key, label]) =>
        `<button class="drawer-tab ${state.detailTab === key ? "active" : ""}" data-detail-tab="${key}" aria-pressed="${state.detailTab === key}">${label}${key === "evidence" ? " · " + (store.evidence?.length || 0) : ""}</button>`,
    )
    .join("")}</div><div class="drawer-body">${body}</div>`;
  content.querySelector(".drawer-close").onclick = () =>
    $("#detail-dialog").close();
  if (focusedTab)
    content.querySelector(`[data-detail-tab="${focusedTab}"]`)?.focus();
}
async function openDetail(id) {
  try {
    state.detail = await api("/api/stores/" + id);
    state.detailTab = "overview";
    renderDetail();
    if (!$("#detail-dialog").open) $("#detail-dialog").showModal();
  } catch (error) {
    toast(error.message);
  }
}
function resetFilters() {
  state.q = "";
  state.category = "";
  state.region = "";
  state.status = state.view === "review" ? "attention" : "all";
  state.page = 1;
  $("#search").value = "";
  renderTabs();
  loadStores().catch((e) => toast(e.message));
}
document.addEventListener("click", async (event) => {
  const target = event.target.closest("button");
  if (!target) return;
  try {
    if (target.dataset.view) switchView(target.dataset.view);
    if (target.dataset.status) {
      state.status = target.dataset.status;
      state.page = 1;
      renderTabs();
      await loadStores();
    }
    if (target.dataset.store) await openDetail(target.dataset.store);
    if (target.dataset.detailTab) {
      state.detailTab = target.dataset.detailTab;
      renderDetail();
    }
    if (target.dataset.pause)
      await busy(target, async () => {
        await api("/api/runs/" + target.dataset.pause + "/cancel", {
          method: "POST",
        });
        toast("Pausing after the current request. Saved pages will be kept.");
        await refresh();
      });
    if (target.dataset.resume)
      await busy(target, async () => {
        await api("/api/runs/" + target.dataset.resume + "/resume", {
          method: "POST",
        });
        toast("Collection resumed.");
        await refresh();
      });
    if (target.id === "empty-action") {
      if (!state.overview.total) $("#import-dialog").showModal();
      else resetFilters();
    }
    if (target.id === "requeue-store")
      await busy(target, async () => {
        await api("/api/stores/" + state.detail.id + "/requeue", {
          method: "POST",
        });
        toast("Candidate queued for another collection.");
        await openDetail(state.detail.id);
        await refresh();
      });
  } catch (error) {
    toast(error.message);
  }
});
$$(
  "#import-dialog .close-dialog, #run-dialog .close-dialog, #method-dialog .close-dialog",
).forEach((button) => {
  button.addEventListener("click", (event) => {
    event.preventDefault();
    button.closest("dialog").close();
  });
});
$("#import-open").onclick = () => {
  $("#import-result").hidden = true;
  $("#import-dialog").showModal();
};
$("#run-open").onclick = () => {
  if (!(state.overview?.counts.queued || 0)) {
    $("#import-result").hidden = true;
    $("#import-dialog").showModal();
    return;
  }
  $("#run-limit").value = Math.min(20, state.overview.counts.queued);
  $("#run-result").hidden = true;
  $("#run-dialog").showModal();
};
$("#method-open").onclick = () => $("#method-dialog").showModal();
$("#refresh").onclick = () => refresh();
function closeExport() {
  $("#export-menu").hidden = true;
  $("#export-open").setAttribute("aria-expanded", "false");
}
$("#export-open").onclick = () => {
  const open = $("#export-menu").hidden;
  $("#export-menu").hidden = !open;
  $("#export-open").setAttribute("aria-expanded", String(open));
  if (open) $("#export-menu a").focus();
};
$("#clear-filters").onclick = resetFilters;
$("#export-menu").addEventListener("click", (event) => {
  if (event.target.closest("a")) closeExport();
});
document.addEventListener("keydown", (event) => {
  if (event.key === "Escape" && !$("#export-menu").hidden) {
    closeExport();
    $("#export-open").focus();
  }
});
document.addEventListener("click", (event) => {
  if (!event.target.closest(".export-control")) closeExport();
});
let searchTimer;
$("#search").addEventListener("input", (event) => {
  clearTimeout(searchTimer);
  searchTimer = setTimeout(() => {
    state.q = event.target.value;
    state.page = 1;
    loadStores().catch((e) => toast(e.message));
  }, 180);
});
$("#category-filter").onchange = (event) => {
  state.category = event.target.value;
  state.page = 1;
  loadStores().catch((e) => toast(e.message));
};
$("#state-filter").onchange = (event) => {
  state.region = event.target.value;
  state.page = 1;
  loadStores().catch((e) => toast(e.message));
};
$("#previous").onclick = () => {
  state.page--;
  loadStores().catch((e) => toast(e.message));
};
$("#next").onclick = () => {
  state.page++;
  loadStores().catch((e) => toast(e.message));
};
document.addEventListener("keydown", (event) => {
  if (
    event.key === "/" &&
    !event.target.closest("input,textarea,select") &&
    !$("dialog[open]")
  ) {
    event.preventDefault();
    $("#search").focus();
  }
});
$("#import-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  await busy(event.submitter, async () => {
    try {
      const result = await api("/api/import", {
        method: "POST",
        body: JSON.stringify({
          domains: $("#import-domains").value,
          source: $("#import-source").value,
          source_url: $("#import-source-url").value,
        }),
      });
      const message = `${result.added} candidates added · ${result.duplicates} already known`;
      if (result.errors.length) {
        $("#import-result").textContent =
          message +
          "\n" +
          result.errors
            .slice(0, 5)
            .map((x) => x.url + ": " + x.error)
            .join("\n");
        $("#import-result").hidden = false;
      } else {
        $("#import-dialog").close();
        $("#import-form").reset();
        toast(message);
      }
      await refresh();
    } catch (error) {
      $("#import-result").textContent = error.message;
      $("#import-result").hidden = false;
    }
  });
});
$("#starter-import").onclick = async (event) => {
  await busy(event.currentTarget, async () => {
    try {
      const r = await api("/api/import-starter", { method: "POST" });
      $("#import-dialog").close();
      toast(
        `${r.added} starter candidates added · ${r.duplicates} already known`,
      );
      await refresh();
    } catch (e) {
      toast(e.message);
    }
  });
};
$("#run-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  await busy(event.submitter, async () => {
    try {
      const r = await api("/api/runs", {
        method: "POST",
        body: JSON.stringify({ limit: Number($("#run-limit").value) }),
      });
      $("#run-dialog").close();
      toast(`Collection started for ${r.candidates} candidates.`);
      await refresh();
    } catch (error) {
      if (error.code === "empty_queue") {
        $("#run-dialog").close();
        await refresh();
        $("#import-result").hidden = true;
        $("#import-dialog").showModal();
        toast(error.message);
      } else {
        $("#run-result").textContent = error.message;
        $("#run-result").hidden = false;
      }
    }
  });
});
document.addEventListener("submit", async (event) => {
  if (event.target.id !== "review-form") return;
  event.preventDefault();
  await busy(event.submitter, async () => {
    try {
      await api("/api/stores/" + state.detail.id + "/review", {
        method: "POST",
        body: JSON.stringify({
          decision: $("#review-decision").value,
          note: $("#review-note").value,
          reviewer: "human",
        }),
      });
      toast("Review saved with the current evidence.");
      await openDetail(state.detail.id);
      await refresh();
    } catch (error) {
      toast(error.message);
    }
  });
});
$("#store-rows").innerHTML = Array.from(
  { length: 6 },
  () =>
    '<tr class="skeleton-row">' +
    Array.from(
      { length: 7 },
      () => '<td><div class="skeleton"></div></td>',
    ).join("") +
    "</tr>",
).join("");
await refresh();
setInterval(() => {
  const interval = state.runs.some((r) => r.status === "running") ? 2000 : 8000;
  if (
    !document.hidden &&
    !$("dialog[open]") &&
    Date.now() - lastRefresh >= interval
  )
    refresh();
}, 1000);
