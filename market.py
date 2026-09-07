"""Pure market-structure calculations for TrendLab.

The module deliberately produces a descriptive snapshot, not a prediction or a
trading signal. It has no network or environment dependencies so the methodology
can be tested independently from CoinMarketCap access.
"""

from __future__ import annotations

import math
from statistics import median
from typing import Any, Iterable, Mapping


UNIVERSE_SIZE = 100
MIN_UNIVERSE_SIZE = 60
LEADERSHIP_DIVERGENCE_PP = 1.0
CATEGORY_MIN_TOKENS = 5
CATEGORY_MIN_MARKET_CAP = 100_000_000


class DataError(ValueError):
    """Raised when an upstream response cannot support a responsible snapshot."""


def finite_number(value: Any) -> float | None:
    """Return a finite float or None without treating malformed data as zero."""

    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def usd_quote(asset: Mapping[str, Any]) -> Mapping[str, Any] | None:
    """Support both CMC's list and object quote shapes."""

    quote = asset.get("quote")
    if isinstance(quote, list):
        for item in quote:
            if isinstance(item, Mapping) and str(item.get("symbol", "")).upper() == "USD":
                return item
    if isinstance(quote, Mapping):
        candidate = quote.get("USD")
        if isinstance(candidate, Mapping):
            return candidate
    return None


def stablecoin(asset: Mapping[str, Any]) -> bool:
    """Use CMC's own tag instead of maintaining a hidden asset allowlist."""

    tags = asset.get("tags")
    return isinstance(tags, list) and any(str(tag).lower() == "stablecoin" for tag in tags)


def normalize_asset(asset: Mapping[str, Any]) -> dict[str, Any] | None:
    quote = usd_quote(asset)
    if not quote:
        return None

    change = finite_number(quote.get("percent_change_24h"))
    market_cap = finite_number(quote.get("market_cap"))
    volume = finite_number(quote.get("volume_24h"))
    rank = finite_number(asset.get("cmc_rank"))
    if change is None or market_cap is None or market_cap <= 0 or rank is None:
        return None

    return {
        "id": asset.get("id"),
        "name": str(asset.get("name", "Unknown asset")),
        "symbol": str(asset.get("symbol", "?")),
        "rank": int(rank),
        "change_24h": change,
        "market_cap": market_cap,
        "volume_24h": volume,
        "last_updated": quote.get("last_updated") or asset.get("last_updated"),
    }


def build_universe(listings: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    """Build the top non-stable CMC universe used by every breadth calculation."""

    candidates: list[dict[str, Any]] = []
    stablecoins_excluded = 0
    invalid_excluded = 0

    for asset in listings:
        if stablecoin(asset):
            stablecoins_excluded += 1
            continue
        normalized = normalize_asset(asset)
        if normalized is None:
            invalid_excluded += 1
            continue
        candidates.append(normalized)

    candidates.sort(key=lambda asset: asset["rank"])
    assets = candidates[:UNIVERSE_SIZE]
    if len(assets) < MIN_UNIVERSE_SIZE:
        raise DataError(
            f"Only {len(assets)} eligible non-stable assets were available; "
            f"need at least {MIN_UNIVERSE_SIZE}."
        )

    return {
        "assets": assets,
        "available": len(assets),
        "stablecoins_excluded": stablecoins_excluded,
        "invalid_excluded": invalid_excluded,
        "universe_label": f"Top {len(assets)} non-stable CMC assets by market-cap rank",
    }


def classify(breadth: float, median_return: float, weighted_return: float) -> dict[str, str]:
    """Classify a descriptive market posture using visible, fixed thresholds."""

    divergence = weighted_return - median_return
    if breadth >= 65 and median_return > 0:
        return {
            "code": "broad_advance",
            "label": "Broad advance",
            "tone": "positive",
            "summary": (
                "Most assets in the normalized snapshot are positive. "
                "The move is broad rather than isolated to a few leaders."
            ),
        }
    if weighted_return > 0 and breadth < 50 and divergence >= LEADERSHIP_DIVERGENCE_PP:
        return {
            "code": "narrow_leadership",
            "label": "Narrow large-cap leadership",
            "tone": "warning",
            "summary": (
                "Large assets keep the weighted snapshot positive, while most "
                "assets do not participate. A green headline is not broad confirmation."
            ),
        }
    if breadth <= 35 and median_return < 0:
        return {
            "code": "broad_weakness",
            "label": "Broad weakness",
            "tone": "negative",
            "summary": (
                "Losses are distributed across most assets in the normalized snapshot. "
                "The weakness is broad, not limited to a few names."
            ),
        }
    return {
        "code": "mixed",
        "label": "Mixed structure",
        "tone": "neutral",
        "summary": (
            "Breadth and leadership do not support a strong structural conclusion. "
            "Treat the snapshot as mixed rather than directional."
        ),
    }


def build_breadth(universe: Mapping[str, Any]) -> dict[str, Any]:
    assets = universe["assets"]
    changes = [asset["change_24h"] for asset in assets]
    total_market_cap = sum(asset["market_cap"] for asset in assets)
    if total_market_cap <= 0:
        raise DataError("The eligible universe has no positive market-cap weight.")

    positive = sum(change > 0 for change in changes)
    breadth = positive / len(changes) * 100
    median_return = float(median(changes))
    weighted_return = sum(
        asset["market_cap"] * asset["change_24h"] for asset in assets
    ) / total_market_cap
    divergence = weighted_return - median_return
    posture = classify(breadth, median_return, weighted_return)

    leaders = sorted(assets, key=lambda asset: asset["change_24h"], reverse=True)[:5]
    laggards = sorted(assets, key=lambda asset: asset["change_24h"])[:5]

    return {
        "universe": {
            key: universe[key]
            for key in ("available", "stablecoins_excluded", "invalid_excluded", "universe_label")
        },
        "positive_assets": positive,
        "percent_positive": breadth,
        "median_return": median_return,
        "weighted_return": weighted_return,
        "leadership_divergence": divergence,
        "posture": posture,
        "assets": assets,
        "leaders": leaders,
        "laggards": laggards,
    }


def normalize_market(global_metrics: Mapping[str, Any]) -> dict[str, Any]:
    quote = global_metrics.get("quote")
    usd = quote.get("USD") if isinstance(quote, Mapping) else None
    if not isinstance(usd, Mapping):
        raise DataError("CMC global metrics did not return a USD quote.")

    fields = {
        "btc_dominance": global_metrics.get("btc_dominance"),
        "eth_dominance": global_metrics.get("eth_dominance"),
        "total_market_cap": usd.get("total_market_cap"),
        "altcoin_market_cap": usd.get("altcoin_market_cap"),
        "total_volume_24h": usd.get("total_volume_24h"),
    }
    normalized = {key: finite_number(value) for key, value in fields.items()}
    if any(value is None for value in normalized.values()):
        raise DataError("CMC global metrics omitted a field required by the interface.")

    normalized["last_updated"] = (
        global_metrics.get("last_updated") or usd.get("last_updated")
    )
    return normalized


def normalize_categories(categories: Iterable[Mapping[str, Any]] | None) -> list[dict[str, Any]]:
    """Keep reproducibly liquid, multi-token categories; portfolio labels are not sectors."""

    if not categories:
        return []

    normalized: list[dict[str, Any]] = []
    for category in categories:
        name = str(category.get("name", "Unknown category"))
        if "portfolio" in name.lower():
            continue

        tokens = finite_number(category.get("num_tokens"))
        market_cap = finite_number(category.get("market_cap"))
        average_change = finite_number(category.get("avg_price_change"))
        market_cap_change = finite_number(category.get("market_cap_change"))
        volume_change = finite_number(category.get("volume_change"))
        if (
            tokens is None
            or market_cap is None
            or average_change is None
            or market_cap_change is None
            or volume_change is None
            or tokens < CATEGORY_MIN_TOKENS
            or market_cap < CATEGORY_MIN_MARKET_CAP
        ):
            continue

        normalized.append(
            {
                "id": category.get("id"),
                "name": name,
                "num_tokens": int(tokens),
                "market_cap": market_cap,
                "avg_price_change": average_change,
                "market_cap_change": market_cap_change,
                "volume_change": volume_change,
                "last_updated": category.get("last_updated"),
            }
        )

    normalized.sort(
        key=lambda category: (category["avg_price_change"], category["volume_change"]),
        reverse=True,
    )
    return normalized[:8]


def normalize_altcoin_season(data: Mapping[str, Any] | None) -> dict[str, Any] | None:
    if not data:
        return None

    index = finite_number(data.get("altcoin_index"))
    if index is None:
        return None

    if index > 75:
        label = "Altcoin season range"
    elif index < 25:
        label = "Bitcoin season range"
    else:
        label = "Transition range"

    return {
        "index": int(index),
        "label": label,
        "yearly_high": finite_number(data.get("yearly_high")),
        "yearly_low": finite_number(data.get("yearly_low")),
        "snapshot_time": data.get("snapshot_time"),
    }


def build_snapshot(
    listings: Iterable[Mapping[str, Any]],
    global_metrics: Mapping[str, Any],
    categories: Iterable[Mapping[str, Any]] | None = None,
    altcoin_season: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Produce the full UI payload from four already-authenticated CMC responses."""

    universe = build_universe(listings)
    breadth = build_breadth(universe)
    return {
        "market": normalize_market(global_metrics),
        "breadth": breadth,
        "categories": normalize_categories(categories),
        "altcoin_season": normalize_altcoin_season(altcoin_season),
        "methodology": {
            "version": "1.0",
            "universe": universe["universe_label"],
            "broad_advance": "breadth >= 65% and median return > 0",
            "narrow_leadership": (
                "weighted return > 0, breadth < 50%, and weighted-minus-median >= 1pp"
            ),
            "broad_weakness": "breadth <= 35% and median return < 0",
        },
    }
