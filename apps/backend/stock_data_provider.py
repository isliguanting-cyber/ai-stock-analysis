from __future__ import annotations

from datetime import datetime
import logging
import os
from typing import Any

logger = logging.getLogger(__name__)


def fetch_stock_payloads(symbol: str) -> dict[str, dict[str, Any]] | None:
    """Fetch raw stock payloads for the analysis adapter.

    Returns None when real data is disabled or temporarily unavailable. The API
    layer can then fall back to the compliant demo response.
    """
    provider = os.getenv("STOCK_DATA_PROVIDER", "chart").strip().lower()
    if provider in {"", "demo", "mock", "off"}:
        return None
    if provider in {"chart", "yahoo", "yahoo_chart"}:
        return _fetch_from_yahoo_chart(symbol.strip().upper())
    if provider != "yfinance":
        raise ValueError(f"Unsupported STOCK_DATA_PROVIDER: {provider}")
    return _fetch_from_yfinance(symbol)


def _fetch_from_yfinance(symbol: str) -> dict[str, dict[str, Any]] | None:
    try:
        import pandas as pd
        import yfinance as yf
    except ImportError:
        return None

    normalized = symbol.strip().upper()
    try:
        ticker = yf.Ticker(normalized)
        info, info_warning = _safe_info(ticker)
        history, history_warning = _safe_history(ticker)
    except Exception as exc:
        logger.warning("yfinance setup failed for %s: %s", normalized, exc)
        return None

    if not info and history.empty:
        return _fetch_from_yahoo_chart(normalized)

    as_of = datetime.utcnow().isoformat() + "Z"
    warnings = [warning for warning in (info_warning, history_warning) if warning]
    current_price = _first_number(
        info.get("currentPrice"),
        info.get("regularMarketPrice"),
        info.get("previousClose"),
        _last_close(history),
    )

    return {
        "summary": _build_summary(normalized, info, current_price, as_of, warnings),
        "technicals": _build_technicals(normalized, history, current_price, as_of, pd, warnings),
        "fundamentals": _build_fundamentals(normalized, info, as_of, warnings),
    }


def _fetch_from_yahoo_chart(symbol: str) -> dict[str, dict[str, Any]] | None:
    try:
        import pandas as pd
        import requests
    except ImportError:
        return None

    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
    try:
        response = requests.get(
            url,
            params={"range": "1y", "interval": "1d"},
            headers={"User-Agent": "Mozilla/5.0"},
            timeout=10,
        )
        response.raise_for_status()
        result = (response.json().get("chart", {}).get("result") or [None])[0]
    except Exception as exc:
        logger.warning("Yahoo chart fallback failed for %s: %s", symbol, exc)
        return None

    if not result:
        return None

    meta = result.get("meta") or {}
    timestamps = result.get("timestamp") or []
    quote = ((result.get("indicators") or {}).get("quote") or [{}])[0]
    history = pd.DataFrame(
        {
            "Close": quote.get("close") or [],
            "Volume": quote.get("volume") or [],
        },
        index=pd.to_datetime(timestamps, unit="s", utc=True) if timestamps else None,
    ).dropna(subset=["Close"])

    as_of = datetime.utcnow().isoformat() + "Z"
    warnings = ["fundamentals_unavailable", "yfinance_fallback_chart"]
    current_price = _first_number(meta.get("regularMarketPrice"), _last_close(history))
    info = {
        "longName": meta.get("longName") or symbol,
        "shortName": meta.get("shortName") or symbol,
        "currency": meta.get("currency"),
        "exchange": meta.get("exchangeName"),
        "currentPrice": current_price,
        "previousClose": meta.get("chartPreviousClose") or meta.get("previousClose"),
    }

    return {
        "summary": _build_summary(
            symbol,
            info,
            current_price,
            as_of,
            warnings,
            source="yahoo_finance_chart",
        ),
        "technicals": _build_technicals(
            symbol,
            history,
            current_price,
            as_of,
            pd,
            warnings,
            source="yahoo_finance_chart",
        ),
        "fundamentals": _build_fundamentals(
            symbol,
            {},
            as_of,
            warnings,
            source="yahoo_finance_chart",
        ),
    }


def _safe_info(ticker: Any) -> tuple[dict[str, Any], str | None]:
    try:
        return ticker.info or {}, None
    except Exception as exc:
        logger.warning("yfinance info fetch failed: %s", exc)
        return {}, "info_unavailable"


def _safe_history(ticker: Any) -> tuple[Any, str | None]:
    try:
        return ticker.history(period="1y", interval="1d", auto_adjust=True), None
    except Exception as exc:
        logger.warning("yfinance history fetch failed: %s", exc)
        try:
            import pandas as pd

            return pd.DataFrame(), "history_unavailable"
        except ImportError:
            raise exc


def _build_summary(
    symbol: str,
    info: dict[str, Any],
    current_price: float | None,
    as_of: str,
    warnings: list[str] | None = None,
    source: str = "yfinance",
) -> dict[str, Any]:
    return {
        "data_provenance": {
            "fundamentals": {
                "source": source,
                "as_of": as_of,
                "warnings": warnings or [],
            }
        },
        "symbol": symbol,
        "name": info.get("longName") or info.get("shortName") or symbol,
        "sector": info.get("sector"),
        "industry": info.get("industry"),
        "exchange": info.get("exchange"),
        "currency": info.get("currency"),
        "current_price": current_price,
        "previous_close": _to_float(info.get("previousClose")),
        "market_cap": _to_float(info.get("marketCap")),
        "avg_volume_30d": _to_float(info.get("averageVolume")),
        "shares_outstanding": _to_float(info.get("sharesOutstanding")),
        "dividend_yield": _to_float(info.get("dividendYield")),
    }


def _build_technicals(
    symbol: str,
    history: Any,
    current_price: float | None,
    as_of: str,
    pd: Any,
    warnings: list[str] | None = None,
    source: str = "yfinance",
) -> dict[str, Any]:
    close = history["Close"].dropna() if not history.empty and "Close" in history else pd.Series()
    volume = history["Volume"].dropna() if not history.empty and "Volume" in history else pd.Series()
    price = current_price or _last_close(history)
    sma_50 = _series_mean(close.tail(50))
    sma_200 = _series_mean(close.tail(200))
    rsi = _calculate_rsi(close)
    macd_line, signal_line = _calculate_macd(close)
    high_52w = _series_max(close)
    low_52w = _series_min(close)
    last_bar_date = _last_bar_date(history)

    return {
        "data_provenance": {
            "price": {
                "source": source,
                "as_of": as_of,
                "last_bar_date": last_bar_date,
                "warnings": warnings or [],
            }
        },
        "symbol": symbol,
        "current_price": price,
        "moving_averages": {
            "sma_50": sma_50,
            "sma_200": sma_200,
            "price_vs_sma50": _ratio_delta(price, sma_50),
            "price_vs_sma200": _ratio_delta(price, sma_200),
        },
        "rsi": {"value": rsi, "period": 14},
        "macd": {
            "macd_line": macd_line,
            "signal_line": signal_line,
            "rules": {
                "bearish_cross": {
                    "triggered": (
                        macd_line is not None
                        and signal_line is not None
                        and macd_line < signal_line
                    )
                }
            },
        },
        "returns": {
            "return_1m": _period_return(close, 21),
            "return_3m": _period_return(close, 63),
            "return_6m": _period_return(close, 126),
            "return_1y": _period_return(close, 252),
        },
        "volume": {
            "current": _to_float(volume.iloc[-1]) if len(volume) else None,
            "avg_20d": _series_mean(volume.tail(20)),
        },
        "price_position": {
            "week_52_high": high_52w,
            "week_52_low": low_52w,
            "from_52w_high": _ratio_delta(price, high_52w),
            "from_52w_low": _ratio_delta(price, low_52w),
        },
    }


def _build_fundamentals(
    symbol: str,
    info: dict[str, Any],
    as_of: str,
    warnings: list[str] | None = None,
    source: str = "yfinance",
) -> dict[str, Any]:
    return {
        "data_provenance": {
            "fundamentals": {
                "source": source,
                "as_of": as_of,
                "warnings": warnings or [],
            }
        },
        "symbol": symbol,
        "valuation": {
            "pe_trailing": _to_float(info.get("trailingPE")),
            "pe_forward": _to_float(info.get("forwardPE")),
            "trailing_eps": _to_float(info.get("trailingEps")),
            "ps_trailing": _to_float(info.get("priceToSalesTrailing12Months")),
            "pb_ratio": _to_float(info.get("priceToBook")),
            "peg_ratio": _to_float(info.get("pegRatio")),
            "ev_to_ebitda": _to_float(info.get("enterpriseToEbitda")),
            "ev_to_sales": _to_float(info.get("enterpriseToRevenue")),
        },
        "growth": {
            "revenue_yoy": _to_float(info.get("revenueGrowth")),
            "eps_yoy": _to_float(info.get("earningsQuarterlyGrowth")),
        },
        "profitability": {
            "gross_margin": _to_float(info.get("grossMargins")),
            "operating_margin": _to_float(info.get("operatingMargins")),
            "net_margin": _to_float(info.get("profitMargins")),
            "roe": _to_float(info.get("returnOnEquity")),
            "roa": _to_float(info.get("returnOnAssets")),
        },
        "financial_health": {
            "total_cash": _to_float(info.get("totalCash")),
            "total_debt": _to_float(info.get("totalDebt")),
            "net_cash": _net_cash(info),
            "current_ratio": _to_float(info.get("currentRatio")),
            "debt_to_equity": _to_float(info.get("debtToEquity")),
        },
        "cash_flow": {
            "operating_cf_ttm": _to_float(info.get("operatingCashflow")),
            "free_cash_flow_ttm": _to_float(info.get("freeCashflow")),
            "currency": info.get("currency"),
            "fcf_margin": _ratio(_to_float(info.get("freeCashflow")), _to_float(info.get("totalRevenue"))),
        },
        "analyst_coverage": {
            "rating": info.get("recommendationKey"),
            "num_analysts": _to_float(info.get("numberOfAnalystOpinions")),
            "price_target_mean": _to_float(info.get("targetMeanPrice")),
        },
    }


def _calculate_rsi(close: Any, period: int = 14) -> float | None:
    if len(close) <= period:
        return None
    delta = close.diff().dropna()
    gains = delta.clip(lower=0)
    losses = -delta.clip(upper=0)
    avg_gain = gains.tail(period).mean()
    avg_loss = losses.tail(period).mean()
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return round(float(100 - (100 / (1 + rs))), 2)


def _calculate_macd(close: Any) -> tuple[float | None, float | None]:
    if len(close) < 35:
        return None, None
    ema_12 = close.ewm(span=12, adjust=False).mean()
    ema_26 = close.ewm(span=26, adjust=False).mean()
    macd = ema_12 - ema_26
    signal = macd.ewm(span=9, adjust=False).mean()
    return _to_float(macd.iloc[-1]), _to_float(signal.iloc[-1])


def _period_return(close: Any, periods: int) -> float | None:
    if len(close) <= periods:
        return None
    start = _to_float(close.iloc[-periods - 1])
    end = _to_float(close.iloc[-1])
    return _ratio_delta(end, start)


def _last_close(history: Any) -> float | None:
    if history.empty or "Close" not in history:
        return None
    return _to_float(history["Close"].dropna().iloc[-1])


def _last_bar_date(history: Any) -> str | None:
    if history.empty:
        return None
    try:
        return history.index[-1].date().isoformat()
    except Exception:
        return None


def _net_cash(info: dict[str, Any]) -> float | None:
    cash = _to_float(info.get("totalCash"))
    debt = _to_float(info.get("totalDebt"))
    if cash is None or debt is None:
        return None
    return cash - debt


def _series_mean(series: Any) -> float | None:
    if len(series) == 0:
        return None
    return _to_float(series.mean())


def _series_max(series: Any) -> float | None:
    if len(series) == 0:
        return None
    return _to_float(series.max())


def _series_min(series: Any) -> float | None:
    if len(series) == 0:
        return None
    return _to_float(series.min())


def _ratio_delta(value: Any, base: Any) -> float | None:
    value_num = _to_float(value)
    base_num = _to_float(base)
    if value_num is None or base_num in (None, 0):
        return None
    return (value_num - base_num) / base_num


def _ratio(value: Any, base: Any) -> float | None:
    value_num = _to_float(value)
    base_num = _to_float(base)
    if value_num is None or base_num in (None, 0):
        return None
    return value_num / base_num


def _first_number(*values: Any) -> float | None:
    for value in values:
        number = _to_float(value)
        if number is not None:
            return number
    return None


def _to_float(value: Any) -> float | None:
    try:
        if value is None:
            return None
        return float(value)
    except (TypeError, ValueError):
        return None
