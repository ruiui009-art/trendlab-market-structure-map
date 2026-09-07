"""Service-level tests that do not need a real CMC key or network access."""

from __future__ import annotations

from functools import partial
from http.server import ThreadingHTTPServer
import json
from pathlib import Path
import threading
import unittest
from urllib.error import HTTPError
from urllib.request import urlopen

from server import AppHandler, SnapshotService


def asset(rank: int, change: float, market_cap: float) -> dict:
    return {
        "id": rank,
        "name": f"Asset {rank}",
        "symbol": f"A{rank}",
        "cmc_rank": rank,
        "tags": ["layer-1"],
        "quote": [
            {
                "symbol": "USD",
                "percent_change_24h": change,
                "market_cap": market_cap,
                "volume_24h": market_cap / 10,
            }
        ],
    }


class FakeCmcClient:
    access_mode = "keyed"

    def request(self, source: dict) -> tuple[int, dict]:
        common_status = {"timestamp": "2026-09-07T00:00:00.000Z", "error_code": 0, "credit_count": 1}
        if source["name"] == "Listings":
            return 200, {
                "data": [asset(rank, 1 if rank <= 70 else -1, 1_000_000) for rank in range(1, 101)],
                "status": common_status,
            }
        if source["name"] == "Global metrics":
            return 200, {
                "data": {
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
                },
                "status": common_status,
            }
        if source["name"] == "Categories":
            return 200, {
                "data": [
                    {
                        "id": "layer-1",
                        "name": "Layer 1",
                        "num_tokens": 20,
                        "market_cap": 1_000_000_000,
                        "avg_price_change": 2,
                        "market_cap_change": 1,
                        "volume_change": 5,
                    }
                ],
                "status": common_status,
            }
        return 200, {
            "data": {"altcoin_index": 42, "yearly_low": 14, "yearly_high": 78, "snapshot_time": "2026-09-07T00:00:00Z"},
            "status": common_status,
        }


class QuietAppHandler(AppHandler):
    def log_message(self, format: str, *args: object) -> None:
        pass


class SnapshotServiceTests(unittest.TestCase):
    def test_snapshot_is_a_narrow_evidence_payload_not_a_raw_cmc_proxy(self) -> None:
        snapshot = SnapshotService(FakeCmcClient()).snapshot()

        self.assertEqual(snapshot["access_mode"], "keyed")
        self.assertEqual(snapshot["breadth"]["posture"]["code"], "broad_advance")
        self.assertEqual(len(snapshot["sources"]), 4)
        self.assertEqual(snapshot["sources"][0]["endpoint"], "/v3/cryptocurrency/listings/latest")
        self.assertIn("response_excerpt", snapshot["sources"][0])
        self.assertNotIn("CMC_API_KEY", str(snapshot))


class AppHandlerTests(unittest.TestCase):
    def setUp(self) -> None:
        QuietAppHandler.service = SnapshotService(FakeCmcClient())
        handler = partial(QuietAppHandler, directory=str(Path(__file__).resolve().parent))
        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), handler)
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        self.thread.start()
        self.base_url = f"http://127.0.0.1:{self.httpd.server_port}"

    def tearDown(self) -> None:
        self.httpd.shutdown()
        self.httpd.server_close()
        self.thread.join()

    def test_narrow_endpoint_returns_a_snapshot(self) -> None:
        with urlopen(f"{self.base_url}/api/market-structure", timeout=5) as response:
            payload = json.load(response)

        self.assertEqual(response.status, 200)
        self.assertEqual(payload["breadth"]["posture"]["code"], "broad_advance")
        self.assertNotIn("data", payload["sources"][0])

    def test_encoded_dotfiles_are_not_served(self) -> None:
        with self.assertRaises(HTTPError) as error:
            urlopen(f"{self.base_url}/%2eenv", timeout=5)

        self.assertEqual(error.exception.code, 404)


if __name__ == "__main__":
    unittest.main()
