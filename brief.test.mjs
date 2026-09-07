import assert from "node:assert/strict";
import test from "node:test";

import { buildResearchBrief } from "./brief.mjs";

const snapshot = {
  generated_at: "2026-09-07T06:00:00Z",
  market: { last_updated: "2026-09-07T05:55:00Z" },
  breadth: {
    posture: { label: "Mixed structure" },
    positive_assets: 47,
    universe: { available: 100 },
    percent_positive: 47,
    median_return: -0.2,
    weighted_return: -0.1,
    leadership_divergence: 0.1,
  },
  category_observation: {
    confirmed: {
      name: "Robotics",
      avg_price_change: 11.5,
      market_cap_change: 10.4,
      volume_change: 125.1,
    },
    price_only: {
      name: "Robinhood Memes",
      avg_price_change: 58.5,
      market_cap_change: -3,
      volume_change: 38.1,
    },
    limitation: "Cross-metric confirmation is a research lead only.",
  },
};

test("builds a timestamped research brief without a trading recommendation", () => {
  const brief = buildResearchBrief(snapshot);

  assert.match(brief, /Snapshot: 2026-09-07T05:55:00Z/);
  assert.match(brief, /Market structure: Mixed structure/);
  assert.match(brief, /Confirmed cross-metric lead: Robotics/);
  assert.match(brief, /Unconfirmed outlier: Robinhood Memes/);
  assert.match(brief, /not trading advice/);
  assert.doesNotMatch(brief, /buy|sell/i);
});
