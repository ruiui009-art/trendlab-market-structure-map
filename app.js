import { buildResearchBrief } from "./brief.mjs";

const $ = (id) => document.getElementById(id);
const svgNs = "http://www.w3.org/2000/svg";
let timer;
let methodology = null;
let currentBrief = "";

function formatPercent(value, digits = 1) {
  const number = Number(value);
  if (!Number.isFinite(number)) return "--";
  return `${number > 0 ? "+" : ""}${number.toFixed(digits)}%`;
}

function formatUnsignedPercent(value, digits = 1) {
  const number = Number(value);
  return Number.isFinite(number) ? `${number.toFixed(digits)}%` : "--";
}

function formatUsd(value) {
  const number = Number(value);
  if (!Number.isFinite(number)) return "--";
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    notation: "compact",
    maximumFractionDigits: 1,
  }).format(number);
}

function formatTime(value) {
  if (!value) return "Timestamp unavailable";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "Timestamp unavailable";
  return `CMC snapshot ${new Intl.DateTimeFormat("en-GB", {
    dateStyle: "medium",
    timeStyle: "medium",
    timeZone: "UTC",
  }).format(date)} UTC`;
}

function setText(id, value) {
  $(id).textContent = value;
}

function toneFor(value) {
  return Number(value) > 0 ? "positive" : Number(value) < 0 ? "negative" : "neutral";
}

function setSigned(id, value) {
  const element = $(id);
  element.textContent = formatPercent(value);
  element.dataset.tone = toneFor(value);
}

function cap(value, floor, ceiling) {
  return Math.min(Math.max(value, floor), ceiling);
}

function clear(node) {
  node.replaceChildren();
}

function renderBreadthPlot(assets) {
  const plot = $("breadth-plot");
  clear(plot);

  [50, 250, 450, 550, 750, 950].forEach((x) => {
    const guide = document.createElementNS(svgNs, "line");
    guide.setAttribute("x1", x);
    guide.setAttribute("x2", x);
    guide.setAttribute("y1", "0");
    guide.setAttribute("y2", "128");
    guide.setAttribute("class", x === 500 ? "plot-zero" : "plot-guide");
    plot.append(guide);
  });

  assets.forEach((asset, index) => {
    const change = Number(asset.change_24h);
    const circle = document.createElementNS(svgNs, "circle");
    circle.setAttribute("cx", String(500 + cap(change, -10, 10) * 45));
    circle.setAttribute("cy", String(12 + (index % 8) * 15));
    circle.setAttribute("r", String(asset.rank <= 10 ? 5 : 3.5));
    circle.setAttribute("class", `plot-dot ${toneFor(change)}`);
    const title = document.createElementNS(svgNs, "title");
    title.textContent = `${asset.name} (${asset.symbol}) ${formatPercent(change)}`;
    circle.append(title);
    plot.append(circle);
  });
}

function renderAssetList(id, assets) {
  const list = $(id);
  clear(list);
  for (const asset of assets) {
    const item = document.createElement("li");
    const identity = document.createElement("span");
    const symbol = document.createElement("strong");
    symbol.textContent = asset.symbol;
    const name = document.createElement("small");
    name.textContent = `#${asset.rank} ${asset.name}`;
    identity.append(symbol, name);
    const change = document.createElement("b");
    change.textContent = formatPercent(asset.change_24h);
    change.dataset.tone = toneFor(asset.change_24h);
    item.append(identity, change);
    list.append(item);
  }
}

function renderCategories(categories) {
  const body = $("category-rows");
  clear(body);
  if (!categories.length) {
    const row = document.createElement("tr");
    const cell = document.createElement("td");
    cell.colSpan = 6;
    cell.textContent = "Category data is currently unavailable; no category conclusion is shown.";
    row.append(cell);
    body.append(row);
    return;
  }

  for (const category of categories) {
    const row = document.createElement("tr");
    const name = document.createElement("td");
    name.textContent = category.name;
    row.append(name);

    const signal = document.createElement("td");
    const signalChip = document.createElement("span");
    signalChip.className = `state-chip ${category.confirmation === "confirmed" ? "positive" : category.confirmation === "price_only" ? "warning" : "negative"}`;
    signalChip.textContent = category.confirmation === "confirmed" ? "Confirmed" : category.confirmation === "price_only" ? "Price only" : "Negative";
    signal.append(signalChip);
    row.append(signal);

    const values = [
      String(category.num_tokens),
      formatPercent(category.avg_price_change),
      formatPercent(category.market_cap_change),
      formatPercent(category.volume_change),
    ];
    values.forEach((value, index) => {
      const cell = document.createElement("td");
      cell.textContent = value;
      if (index > 0) cell.dataset.tone = toneFor([category.avg_price_change, category.market_cap_change, category.volume_change][index - 1]);
      row.append(cell);
    });
    body.append(row);
  }
}

function renderCategoryObservation(observation) {
  const element = $("category-observation");
  if (!observation) {
    element.textContent = "Category data is unavailable, so no cross-metric observation is shown.";
    element.dataset.tone = "neutral";
    return;
  }

  const parts = [];
  if (observation.confirmed) {
    const category = observation.confirmed;
    parts.push(`Confirmed cross-metric lead: ${category.name} (${formatPercent(category.avg_price_change)} average price, ${formatPercent(category.market_cap_change)} market cap, ${formatPercent(category.volume_change)} volume).`);
  }
  if (observation.price_only) {
    const category = observation.price_only;
    parts.push(`Unconfirmed outlier: ${category.name} has ${formatPercent(category.avg_price_change)} average price change without all three metrics confirming.`);
  }
  parts.push(observation.limitation);
  element.textContent = parts.join(" ");
  element.dataset.tone = observation.confirmed ? "positive" : "warning";
}

function renderResearchBrief(snapshot) {
  currentBrief = buildResearchBrief(snapshot);
  $("brief-output").textContent = currentBrief;
  $("brief-status").textContent = "";
}

async function copyResearchBrief() {
  const button = $("copy-brief");
  const status = $("brief-status");
  if (!currentBrief) {
    status.textContent = "A live snapshot is required before a brief can be copied.";
    return;
  }

  try {
    await navigator.clipboard.writeText(currentBrief);
    status.textContent = "Copied. Review the source data before publishing any claim.";
    button.textContent = "Copied";
    window.setTimeout(() => {
      button.textContent = "Copy research brief";
    }, 1600);
  } catch {
    status.textContent = "Clipboard access was blocked. Select the brief text manually.";
  }
}

function renderEvidence(sources) {
  const list = $("evidence");
  clear(list);
  for (const source of sources) {
    const details = document.createElement("details");
    details.className = "evidence-item";
    const summary = document.createElement("summary");
    const identity = document.createElement("span");
    const name = document.createElement("strong");
    name.textContent = source.name;
    const endpoint = document.createElement("code");
    endpoint.textContent = source.endpoint;
    identity.append(name, endpoint);
    const status = document.createElement("span");
    status.className = `state-chip ${source.state === "fresh" ? "positive" : source.state === "stale" ? "warning" : source.state === "unavailable" ? "negative" : "neutral"}`;
    status.textContent = source.state;
    summary.append(identity, status);

    const content = document.createElement("div");
    content.className = "evidence-content";
    const metadata = document.createElement("p");
    const statusText = source.http_status ? `HTTP ${source.http_status}` : "No HTTP response";
    metadata.textContent = `${statusText} · cache age ${source.cache_age_seconds ?? "--"}s · TTL ${source.cache_ttl_seconds}s`;
    const pre = document.createElement("pre");
    pre.textContent = JSON.stringify(
      {
        endpoint: source.endpoint,
        parameters: source.parameters,
        response_excerpt: source.response_excerpt || null,
        upstream_error: source.upstream_error || source.error || null,
      },
      null,
      2,
    );
    content.append(metadata, pre);
    details.append(summary, content);
    list.append(details);
  }
}

function renderMethodology(method) {
  methodology = method;
  setText("methodology-summary", `${method.universe}. The same universe is used for breadth, median return, and weighted return.`);
  $("methodology-detail").textContent = [
    `Universe: ${method.universe}`,
    `Broad advance: ${method.broad_advance}`,
    `Narrow leadership: ${method.narrow_leadership}`,
    `Broad weakness: ${method.broad_weakness}`,
  ].join("\n");
}

function renderSnapshot(snapshot) {
  const { breadth, market, altcoin_season: season } = snapshot;
  const posture = breadth.posture;
  document.body.dataset.tone = posture.tone;

  setText("posture", posture.label);
  setText("posture-summary", posture.summary);
  setText("snapshot-time", formatTime(market.last_updated));
  setText("breadth-value", formatUnsignedPercent(breadth.percent_positive, 0));
  setText("breadth-count", `${breadth.positive_assets} of ${breadth.universe.available} assets`);
  setText("universe-note", `${breadth.universe.stablecoins_excluded} stablecoins excluded`);
  setText("btc-dominance", formatUnsignedPercent(market.btc_dominance));
  setText("eth-dominance", formatUnsignedPercent(market.eth_dominance));
  setText("total-market-cap", formatUsd(market.total_market_cap));
  setText("total-volume", formatUsd(market.total_volume_24h));

  setSigned("weighted-return", breadth.weighted_return);
  setSigned("median-return", breadth.median_return);
  const divergence = breadth.leadership_divergence;
  const badge = $("divergence-badge");
  badge.textContent = `${formatPercent(divergence)} divergence`;
  badge.className = `state-chip ${toneFor(divergence)}`;
  $("weighted-bar").style.width = `${cap(Math.abs(breadth.weighted_return) * 10 + 14, 8, 100)}%`;
  $("weighted-bar").dataset.tone = toneFor(breadth.weighted_return);
  $("median-bar").style.width = `${cap(Math.abs(breadth.median_return) * 10 + 14, 8, 100)}%`;
  $("median-bar").dataset.tone = toneFor(breadth.median_return);
  setText("leadership-note", `A ${formatPercent(divergence)} gap between weighted and median return is the leadership divergence. It is descriptive, not a forecast.`);

  renderBreadthPlot(breadth.assets);
  renderAssetList("leaders", breadth.leaders);
  renderAssetList("laggards", breadth.laggards);
  renderCategories(snapshot.categories);
  renderCategoryObservation(snapshot.category_observation);
  renderResearchBrief(snapshot);
  renderEvidence(snapshot.sources);
  renderMethodology(snapshot.methodology);

  if (season) {
    setText("altcoin-index", String(season.index));
    setText("altcoin-label", season.label);
    setText("altcoin-range", `Yearly range: ${season.yearly_low ?? "--"} to ${season.yearly_high ?? "--"}. CMC snapshot ${season.snapshot_time || "unavailable"}.`);
    document.querySelector(".season-scale i").style.width = `${cap(season.index, 0, 100)}%`;
  } else {
    setText("altcoin-index", "--");
    setText("altcoin-label", "Unavailable");
  }

  const state = $("snapshot-state");
  state.className = `state-chip ${snapshot.partial ? "warning" : "positive"}`;
  state.textContent = snapshot.partial ? "Partial or cached data" : "All sources available";
  setText("access-mode", `${snapshot.access_mode.toUpperCase()} CMC`);
}

function showError(message) {
  $("error").hidden = false;
  setText("error-message", message);
  setText("snapshot-state", "Unavailable");
  $("snapshot-state").className = "state-chip negative";
}

async function load() {
  window.clearTimeout(timer);
  const button = $("refresh");
  button.disabled = true;
  button.textContent = "Refreshing...";
  $("error").hidden = true;
  try {
    const response = await fetch("/api/market-structure", { headers: { Accept: "application/json" } });
    const payload = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(payload.error || "The CMC snapshot could not be loaded.");
    renderSnapshot(payload);
  } catch (error) {
    showError(error.message);
  } finally {
    button.disabled = false;
    button.textContent = "Refresh snapshot";
    timer = window.setTimeout(load, 60_000);
  }
}

$("refresh").addEventListener("click", load);
$("copy-brief").addEventListener("click", copyResearchBrief);
$("methodology-toggle").addEventListener("click", () => {
  const detail = $("methodology-detail");
  detail.hidden = !detail.hidden;
  const open = !detail.hidden;
  $("methodology-toggle").setAttribute("aria-expanded", String(open));
  $("methodology-toggle").textContent = open ? "Hide classification thresholds" : "Show classification thresholds";
});

load();
