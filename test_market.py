"""Tests for the visible TrendLab methodology."""

from __future__ import annotations

import unittest

from market import DataError, build_snapshot, build_universe, normalize_categories


def asset(rank: int, change: float, market_cap: float, stable: bool = False) -> dict:
    return {
        "id": rank,
        "name": f"Asset {rank}",
        "symbol": f"A{rank}",
        "cmc_rank": rank,
        "tags": ["stablecoin"] if stable else ["layer-1"],
        "quote": [
            {
                "symbol": "USD",
                "percent_change_24h": change,
                "market_cap": market_cap,
                "volume_24h": market_cap / 10,
                "last_updated": "2026-09-07T00:00:00.000Z",
            }
        ],
    }


def global_metrics() -> dict:
    return {
        "btc_dominance": 59.1,
        "eth_dominance": 11.2,
        "last_updated": "2026-09-07T00:00:00.000Z",
        "quote": {
            "USD": {
                "total_market_cap": 2_700_000_000_000,
                "altcoin_market_cap": 1_100_000_000_000,
                "total_volume_24h": 70_000_000_000,
            }
        },
    }


class MarketMethodologyTests(unittest.TestCase):
    def test_universe_excludes_cmc_tagged_stablecoins(self) -> None:
        listings = [asset(1, 0, 100_000_000, stable=True)]
        listings.extend(asset(rank, 1, 10_000_000) for rank in range(2, 122))

        universe = build_universe(listings)

        self.assertEqual(universe["available"], 100)
        self.assertEqual(universe["stablecoins_excluded"], 1)
        self.assertNotIn(1, [item["id"] for item in universe["assets"]])

    def test_broad_advance_requires_positive_median_and_breadth(self) -> None:
        listings = [asset(rank, 2 if rank <= 70 else -1, 1_000_000) for rank in range(1, 101)]

        snapshot = build_snapshot(listings, global_metrics())

        self.assertEqual(snapshot["breadth"]["posture"]["code"], "broad_advance")
        self.assertEqual(snapshot["breadth"]["positive_assets"], 70)

    def test_narrow_leadership_is_not_mistaken_for_broad_strength(self) -> None:
        listings = []
        for rank in range(1, 101):
            if rank <= 5:
                listings.append(asset(rank, 5, 1_000_000_000_000))
            else:
                listings.append(asset(rank, -1, 1_000_000))

        snapshot = build_snapshot(listings, global_metrics())

        self.assertEqual(snapshot["breadth"]["posture"]["code"], "narrow_leadership")
        self.assertLess(snapshot["breadth"]["percent_positive"], 50)
        self.assertGreater(snapshot["breadth"]["leadership_divergence"], 1)

    def test_insufficient_universe_does_not_create_a_confident_regime(self) -> None:
        listings = [asset(rank, 1, 1_000_000) for rank in range(1, 60)]

        with self.assertRaises(DataError):
            build_snapshot(listings, global_metrics())

    def test_category_filter_is_explicit_about_non_sector_portfolios(self) -> None:
        categories = [
            {
                "id": "portfolio",
                "name": "Example Capital Portfolio",
                "num_tokens": 12,
                "market_cap": 1_000_000_000,
                "avg_price_change": 5,
                "market_cap_change": 1,
                "volume_change": 10,
            },
            {
                "id": "sector",
                "name": "Layer 1",
                "num_tokens": 12,
                "market_cap": 1_000_000_000,
                "avg_price_change": 3,
                "market_cap_change": 1,
                "volume_change": 10,
            },
            {
                "id": "price-only",
                "name": "Price only",
                "num_tokens": 12,
                "market_cap": 1_000_000_000,
                "avg_price_change": 8,
                "market_cap_change": -1,
                "volume_change": 10,
            },
        ]

        result = normalize_categories(categories)

        self.assertEqual([category["name"] for category in result], ["Price only", "Layer 1"])
        self.assertEqual(result[0]["confirmation"], "price_only")
        self.assertEqual(result[1]["confirmation"], "confirmed")


if __name__ == "__main__":
    unittest.main()
