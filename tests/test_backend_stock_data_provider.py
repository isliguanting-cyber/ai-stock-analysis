import unittest
from pathlib import Path
import sys
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps" / "backend"))

from stock_data_provider import _build_fundamentals, fetch_stock_payloads


class StockDataProviderTest(unittest.TestCase):
    def test_demo_provider_returns_none(self):
        with patch.dict("os.environ", {"STOCK_DATA_PROVIDER": "demo"}):
            self.assertIsNone(fetch_stock_payloads("AAPL"))

    def test_unknown_provider_is_rejected(self):
        with patch.dict("os.environ", {"STOCK_DATA_PROVIDER": "unknown"}):
            with self.assertRaises(ValueError):
                fetch_stock_payloads("AAPL")

    def test_build_fundamentals_maps_yfinance_info(self):
        result = _build_fundamentals(
            "AAPL",
            {
                "trailingPE": 30,
                "revenueGrowth": 0.1,
                "profitMargins": 0.25,
                "freeCashflow": 100,
                "totalRevenue": 1000,
                "totalCash": 500,
                "totalDebt": 200,
                "recommendationKey": "buy",
            },
            "2026-06-21T00:00:00Z",
        )

        self.assertEqual(result["symbol"], "AAPL")
        self.assertEqual(result["valuation"]["pe_trailing"], 30.0)
        self.assertEqual(result["growth"]["revenue_yoy"], 0.1)
        self.assertEqual(result["cash_flow"]["fcf_margin"], 0.1)
        self.assertEqual(result["financial_health"]["net_cash"], 300.0)
        self.assertEqual(result["data_provenance"]["fundamentals"]["source"], "yfinance")


if __name__ == "__main__":
    unittest.main()
