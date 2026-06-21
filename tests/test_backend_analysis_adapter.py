import unittest
from datetime import datetime
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps" / "backend"))

from analysis_adapter import build_research_response, sanitize_recommendation_language


class AnalysisAdapterTest(unittest.TestCase):
    def test_sanitizes_action_oriented_language(self):
        text = "Analyst rating says buy, hold, or sell. strong buy is also possible."

        result = sanitize_recommendation_language(text)

        self.assertNotIn("buy", result.lower())
        self.assertNotIn("sell", result.lower())
        self.assertNotIn("hold", result.lower())
        self.assertIn("研究信号", result)

    def test_builds_compliant_response_from_source_payloads(self):
        response = build_research_response(
            "aapl",
            {
                "summary": {
                    "data_provenance": {
                        "fundamentals": {
                            "source": "yfinance",
                            "as_of": "2026-06-21T15:39:29Z",
                        }
                    },
                    "name": "Apple Inc.",
                    "sector": "Technology",
                    "currency": "USD",
                    "current_price": 298.01,
                    "market_cap": 4_376_979_046_400,
                },
                "technicals": {
                    "data_provenance": {
                        "price": {
                            "source": "yfinance",
                            "as_of": "2026-06-21T15:39:32Z",
                        }
                    },
                    "moving_averages": {
                        "price_vs_sma50": 0.0325,
                        "price_vs_sma200": 0.1128,
                    },
                    "rsi": {"value": 51.0},
                    "macd": {"rules": {"bearish_cross": {"triggered": True}}},
                    "returns": {"return_3m": 0.1981},
                },
                "fundamentals": {
                    "data_provenance": {
                        "fundamentals": {
                            "source": "yfinance",
                            "as_of": "2026-06-21T15:39:42Z",
                        }
                    },
                    "valuation": {"pe_trailing": 36.12},
                    "growth": {"revenue_yoy": 0.166},
                    "profitability": {"net_margin": 0.2715},
                    "cash_flow": {"free_cash_flow_ttm": 129_174_000_000},
                    "financial_health": {"net_cash": -16_203_997_184, "current_ratio": 1.07},
                },
            },
            generated_at=datetime(2026, 6, 21, 12, 0, 0),
        )

        self.assertEqual(response["symbol"], "AAPL")
        self.assertEqual(response["as_of"], "2026-06-21")
        self.assertIn("Apple Inc.", response["summary"])
        self.assertIn("不构成投资建议", response["disclaimer"])
        self.assertGreaterEqual(len(response["key_points"]), 3)
        self.assertGreaterEqual(len(response["risks"]), 2)

    def test_empty_payload_keeps_demo_response_compliant(self):
        response = build_research_response(
            "msft",
            generated_at=datetime(2026, 6, 21, 12, 0, 0),
        )

        self.assertEqual(response["symbol"], "MSFT")
        self.assertEqual(response["as_of"], "2026-06-21")
        self.assertIn("不构成投资建议", response["disclaimer"])
        self.assertTrue(response["key_points"])
        self.assertTrue(response["risks"])


if __name__ == "__main__":
    unittest.main()
