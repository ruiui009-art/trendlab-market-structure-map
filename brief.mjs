function percent(value) {
  const number = Number(value);
  if (!Number.isFinite(number)) return "--";
  return `${number > 0 ? "+" : ""}${number.toFixed(1)}%`;
}

function categoryLine(category, label) {
  if (!category) return null;
  return `${label}: ${category.name} (${percent(category.avg_price_change)} average price, ${percent(category.market_cap_change)} market cap, ${percent(category.volume_change)} volume).`;
}

export function buildResearchBrief(snapshot) {
  const { breadth, category_observation: observation, market } = snapshot;
  const lines = [
    "TRENDLAB / CMC MARKET STRUCTURE BRIEF",
    `Snapshot: ${market.last_updated || snapshot.generated_at || "timestamp unavailable"}`,
    "",
    `Market structure: ${breadth.posture.label}.`,
    `Breadth: ${breadth.positive_assets} of ${breadth.universe.available} non-stable CMC assets positive (${percent(breadth.percent_positive)}).`,
    `Median 24h return: ${percent(breadth.median_return)}. Market-cap-weighted return: ${percent(breadth.weighted_return)}. Leadership divergence: ${percent(breadth.leadership_divergence)}.`,
  ];

  if (observation) {
    const confirmed = categoryLine(observation.confirmed, "Confirmed cross-metric lead");
    const priceOnly = categoryLine(observation.price_only, "Unconfirmed outlier");
    if (confirmed) lines.push(confirmed);
    if (priceOnly) lines.push(priceOnly);
    lines.push(observation.limitation);
  }

  lines.push(
    "Editorial use: treat this as a timestamped research context. It does not prove capital flow, causality, or future returns and is not trading advice.",
    "Sources: CoinMarketCap listings, global metrics, categories, and Altcoin Season Index.",
  );
  return lines.join("\n");
}
