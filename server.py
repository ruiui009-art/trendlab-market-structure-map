#!/usr/bin/env python3
"""Serve TrendLab Market Structure Map and its narrow server-side CMC integration."""

from __future__ import annotations

import argparse
import json
import os
import threading
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import unquote, urlencode, urlsplit
from urllib.request import Request, urlopen

from market import DataError, build_snapshot


ROOT = Path(__file__).resolve().parent
LISTINGS = {
    "name": "Listings",
    "path": "/v3/cryptocurrency/listings/latest",
    "params": {
        "start": "1",
        "limit": "150",
        "convert": "USD",
        "aux": "tags,cmc_rank",
    },
    "ttl": 15 * 60,
    "required": True,
}
GLOBAL = {
    "name": "Global metrics",
    "path": "/v1/global-metrics/quotes/latest",
    "params": {"convert": "USD"},
    "ttl": 15 * 60,
    "required": True,
}
CATEGORIES = {
    "name": "Categories",
    "path": "/v1/cryptocurrency/categories",
    "params": {"start": "1", "limit": "500"},
    "ttl": 60 * 60,
    "required": False,
}
ALTCOIN_SEASON = {
    "name": "Altcoin Season",
    "path": "/v1/altcoin-season-index/latest",
    "params": {},
    "ttl": 60 * 60,
    "required": False,
}
SOURCES = (LISTINGS, GLOBAL, CATEGORIES, ALTCOIN_SEASON)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


class CmcRequestError(RuntimeError):
    """A safe upstream failure that never includes credentials."""

    def __init__(self, source: str, status: int | None, message: str) -> None:
        super().__init__(message)
        self.source = source
        self.status = status


@dataclass
class CachedResponse:
    payload: dict[str, Any]
    http_status: int
    fetched_at: float


@dataclass
class SourceResult:
    payload: dict[str, Any]
    http_status: int
    fetched_at: float
    state: str
    upstream_error: str | None = None

    @property
    def cache_age_seconds(self) -> int:
        return max(0, round(time.time() - self.fetched_at))


class CmcClient:
    """CMC client that retries only transient errors and keeps keys server-side."""

    def __init__(self) -> None:
        self.api_key = os.environ.get("CMC_API_KEY", "").strip()
        self.base_url = "https://pro-api.coinmarketcap.com"
        if not self.api_key:
            self.base_url += "/public-api"

    @property
    def access_mode(self) -> str:
        return "keyed" if self.api_key else "keyless"

    def request(self, source: dict[str, Any]) -> tuple[int, dict[str, Any]]:
        query = urlencode(source["params"])
        url = f"{self.base_url}{source['path']}"
        if query:
            url = f"{url}?{query}"

        headers = {
            "Accept": "application/json",
            "User-Agent": "TrendLab-Market-Structure-Map/1.0",
        }
        if self.api_key:
            headers["X-CMC_PRO_API_KEY"] = self.api_key

        for attempt in range(3):
            try:
                with urlopen(Request(url, headers=headers), timeout=20) as response:
                    status = response.status
                    body = response.read()
            except HTTPError as error:
                status = error.code
                body = error.read()
            except URLError as error:
                if attempt < 2:
                    time.sleep(2**attempt)
                    continue
                raise CmcRequestError(source["name"], None, "CoinMarketCap could not be reached.") from error

            try:
                payload = json.loads(body.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError) as error:
                raise CmcRequestError(source["name"], status, "CMC returned a non-JSON response.") from error

            status_object = payload.get("status", {}) if isinstance(payload, dict) else {}
            error_code = status_object.get("error_code")
            successful = status < 400 and str(error_code) in {"0", "None"}
            if successful:
                return status, payload

            message = status_object.get("error_message") or "CMC rejected the request."
            if status == 429 or status >= 500:
                if attempt < 2:
                    time.sleep(2**attempt)
                    continue
            raise CmcRequestError(source["name"], status, str(message))

        raise CmcRequestError(source["name"], None, "CMC retry budget exhausted.")


class SnapshotService:
    """Caches upstream data and returns a purpose-built UI payload, not a raw proxy."""

    def __init__(self, client: CmcClient) -> None:
        self.client = client
        self.cache: dict[str, CachedResponse] = {}
        self.lock = threading.Lock()

    def source(self, definition: dict[str, Any]) -> SourceResult:
        key = definition["name"]
        with self.lock:
            cached = self.cache.get(key)
            if cached and time.time() - cached.fetched_at < definition["ttl"]:
                return SourceResult(cached.payload, cached.http_status, cached.fetched_at, "cached")

        try:
            status, payload = self.client.request(definition)
        except CmcRequestError as error:
            with self.lock:
                cached = self.cache.get(key)
            if cached:
                return SourceResult(
                    cached.payload,
                    cached.http_status,
                    cached.fetched_at,
                    "stale",
                    str(error),
                )
            raise

        entry = CachedResponse(payload, status, time.time())
        with self.lock:
            self.cache[key] = entry
        return SourceResult(payload, status, entry.fetched_at, "fresh")

    def snapshot(self) -> dict[str, Any]:
        results: dict[str, SourceResult] = {}
        optional_errors: dict[str, str] = {}

        for source in SOURCES:
            try:
                results[source["name"]] = self.source(source)
            except CmcRequestError as error:
                if source["required"]:
                    raise
                optional_errors[source["name"]] = str(error)

        listings_data = results[LISTINGS["name"]].payload.get("data", [])
        global_data = results[GLOBAL["name"]].payload.get("data", {})
        category_data = results.get(CATEGORIES["name"])
        altcoin_data = results.get(ALTCOIN_SEASON["name"])

        snapshot = build_snapshot(
            listings_data,
            global_data,
            category_data.payload.get("data", []) if category_data else None,
            altcoin_data.payload.get("data", {}) if altcoin_data else None,
        )
        snapshot.update(
            {
                "generated_at": utc_now(),
                "access_mode": self.client.access_mode,
                "partial": bool(optional_errors) or any(
                    result.state == "stale" for result in results.values()
                ),
                "sources": [
                    evidence_for(source, results.get(source["name"]), optional_errors.get(source["name"]))
                    for source in SOURCES
                ],
            }
        )
        return snapshot


def response_excerpt(source: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
    """Expose enough real response data for auditability without becoming a data API."""

    data = payload.get("data")
    status = payload.get("status", {})
    excerpt: dict[str, Any] = {
        "status": {
            "timestamp": status.get("timestamp"),
            "error_code": status.get("error_code"),
            "credit_count": status.get("credit_count"),
        }
    }
    if source["name"] == "Listings" and isinstance(data, list):
        first = data[0] if data else {}
        quote = first.get("quote", [{}]) if isinstance(first, dict) else [{}]
        usd = quote[0] if isinstance(quote, list) and quote else {}
        excerpt["items_returned"] = len(data)
        excerpt["first_asset"] = {
            "id": first.get("id"),
            "name": first.get("name"),
            "symbol": first.get("symbol"),
            "cmc_rank": first.get("cmc_rank"),
            "percent_change_24h": usd.get("percent_change_24h"),
            "market_cap": usd.get("market_cap"),
        }
    elif source["name"] == "Categories" and isinstance(data, list):
        excerpt["items_returned"] = len(data)
        excerpt["first_category"] = data[0] if data else {}
    else:
        excerpt["data"] = data
    return excerpt


def evidence_for(
    source: dict[str, Any], result: SourceResult | None, error: str | None
) -> dict[str, Any]:
    evidence = {
        "name": source["name"],
        "endpoint": source["path"],
        "parameters": source["params"],
        "cache_ttl_seconds": source["ttl"],
    }
    if result is None:
        evidence.update({"state": "unavailable", "error": error})
        return evidence

    evidence.update(
        {
            "state": result.state,
            "http_status": result.http_status,
            "cache_age_seconds": result.cache_age_seconds,
            "upstream_error": result.upstream_error,
            "response_excerpt": response_excerpt(source, result.payload),
        }
    )
    return evidence


class AppHandler(SimpleHTTPRequestHandler):
    service: SnapshotService

    def do_GET(self) -> None:  # noqa: N802 - required HTTP handler name
        path = unquote(urlsplit(self.path).path)
        if path == "/api/market-structure":
            self.serve_snapshot()
            return
        if any(part.startswith(".") for part in path.split("/") if part):
            self.send_error(404)
            return
        super().do_GET()

    def serve_snapshot(self) -> None:
        try:
            self.send_json(200, self.service.snapshot())
        except CmcRequestError as error:
            status = 503 if error.status in {429, 500, 502, 503, 504, None} else 502
            self.send_json(
                status,
                {
                    "error": "Core market data is temporarily unavailable.",
                    "source": error.source,
                    "upstream_status": error.status,
                },
            )
        except DataError as error:
            self.send_json(503, {"error": "CMC data is incomplete for this methodology.", "detail": str(error)})

    def send_json(self, status: int, payload: dict[str, Any]) -> None:
        body = json.dumps(payload, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(body)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", default=int(os.environ.get("PORT", "4174")), type=int)
    args = parser.parse_args()

    client = CmcClient()
    AppHandler.service = SnapshotService(client)
    handler = partial(AppHandler, directory=str(ROOT))
    server = ThreadingHTTPServer((args.host, args.port), handler)
    print(f"TrendLab Market Structure Map: http://{args.host}:{args.port} ({client.access_mode} CMC)")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
