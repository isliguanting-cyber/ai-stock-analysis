from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, TimeoutError
from datetime import datetime
from functools import lru_cache
import logging
import os
from typing import Any

logger = logging.getLogger(__name__)


def fetch_stock_payloads(symbol: str) -> dict[str, dict[str, Any]] | None:
    """Fetch raw stock payloads for the analysis adapter.

    Returns None when real data is disabled or temporarily unavailable. The API
    layer can then fall back to the compliant demo response.
    """
    provider = os.getenv("STOCK_DATA_PROVIDER", "yfinance").strip().lower()
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
        fast_info, fast_info_warning = _safe_fast_info(ticker)
        info, info_warning = _safe_info(ticker)
        history, history_warning = _safe_history(ticker)
    except Exception as exc:
        logger.warning("yfinance setup failed for %s: %s", normalized, exc)
        return None

    if not info and history.empty:
        return _fetch_from_yahoo_chart(normalized)

    as_of = datetime.utcnow().isoformat() + "Z"
    profile, profile_warning = _fetch_search_profile(normalized)
    warnings = [
        warning
        for warning in (fast_info_warning, info_warning, history_warning, profile_warning)
        if warning
    ]
    current_price = _first_number(
        info.get("currentPrice"),
        info.get("regularMarketPrice"),
        info.get("previousClose"),
        fast_info.get("last_price"),
        _last_close(history),
    )
    merged_info = _merge_info(normalized, info, fast_info, profile, current_price)

    fundamentals = _build_fundamentals(normalized, merged_info, as_of, warnings)
    sec_fundamentals, sec_warning = _fetch_sec_fundamentals(
        normalized,
        current_price=current_price,
        shares_outstanding=_to_float(merged_info.get("sharesOutstanding")),
    )
    if sec_fundamentals:
        summary_overrides = sec_fundamentals.pop("summary_overrides", {}) or {}
        if summary_overrides.get("shares_outstanding") is not None:
            merged_info["sharesOutstanding"] = summary_overrides["shares_outstanding"]
        if summary_overrides.get("market_cap") is not None:
            merged_info["marketCap"] = summary_overrides["market_cap"]
        fundamentals = _merge_fundamentals(fundamentals, sec_fundamentals)
    if sec_warning:
        warnings.append(sec_warning)

    return {
        "summary": _build_summary(normalized, merged_info, current_price, as_of, warnings),
        "technicals": _build_technicals(normalized, history, current_price, as_of, pd, warnings),
        "fundamentals": fundamentals,
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
    profile, profile_warning = _fetch_search_profile(symbol)
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
    warnings = [
        warning
        for warning in ("fundamentals_unavailable", "yfinance_fallback_chart", profile_warning)
        if warning
    ]
    current_price = _first_number(meta.get("regularMarketPrice"), _last_close(history))
    info = {
        "longName": profile.get("longName") or meta.get("longName") or symbol,
        "shortName": profile.get("shortName") or meta.get("shortName") or symbol,
        "sector": profile.get("sector"),
        "industry": profile.get("industry"),
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


def _fetch_sec_fundamentals(
    symbol: str,
    *,
    current_price: float | None,
    shares_outstanding: float | None,
) -> tuple[dict[str, Any] | None, str | None]:
    try:
        import requests
    except ImportError:
        return None, "sec_unavailable"

    try:
        cik = _sec_cik_for_symbol(symbol)
        if not cik:
            return None, "sec_cik_not_found"
        response = requests.get(
            f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json",
            headers=_sec_headers(),
            timeout=20,
        )
        response.raise_for_status()
        payload = response.json()
        all_facts = payload.get("facts") or {}
        facts = all_facts.get("us-gaap") or {}
        dei_facts = all_facts.get("dei") or {}
    except Exception as exc:
        logger.warning("SEC fundamentals fetch failed for %s: %s", symbol, exc)
        return None, "sec_unavailable"

    revenue_latest, revenue_previous = _latest_annual_values(
        facts,
        "RevenueFromContractWithCustomerExcludingAssessedTax",
        "Revenues",
        "SalesRevenueNet",
    )
    net_income, _ = _latest_annual_values(facts, "NetIncomeLoss")
    operating_cf, _ = _latest_annual_values(facts, "NetCashProvidedByUsedInOperatingActivities")
    capex, _ = _latest_annual_values(facts, "PaymentsToAcquirePropertyPlantAndEquipment")
    assets = _latest_instant_value(facts, "Assets")
    liabilities = _latest_instant_value(facts, "Liabilities")
    equity = _latest_instant_value(facts, "StockholdersEquity")
    cash = _latest_instant_value(
        facts,
        "CashAndCashEquivalentsAtCarryingValue",
        "CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents",
    )
    debt = _latest_instant_value(
        facts,
        "ShortTermBorrowings",
        "ShortTermDebt",
        "LongTermDebtCurrent",
        "LongTermDebtNoncurrent",
        "LongTermDebtAndFinanceLeaseObligationsCurrent",
        "LongTermDebtAndFinanceLeaseObligationsNoncurrent",
    )
    if debt is None:
        debt = _latest_instant_value(facts, "LongTermDebtAndFinanceLeaseObligations")

    sec_shares = _latest_share_value(dei_facts, facts)
    resolved_shares = shares_outstanding or sec_shares
    market_cap = (
        current_price * resolved_shares
        if current_price is not None and resolved_shares is not None
        else None
    )
    free_cash_flow = (
        operating_cf - abs(capex)
        if operating_cf is not None and capex is not None
        else None
    )

    return {
        "data_provenance": {
            "fundamentals": {
                "source": "sec_companyfacts",
                "as_of": datetime.utcnow().isoformat() + "Z",
                "warnings": [],
            }
        },
        "valuation": {
            "pe_trailing": _ratio(market_cap, net_income),
            "trailing_eps": _ratio(net_income, resolved_shares),
            "ps_trailing": _ratio(market_cap, revenue_latest),
            "pb_ratio": _ratio(market_cap, equity),
        },
        "growth": {
            "revenue_yoy": _ratio_delta(revenue_latest, revenue_previous),
        },
        "profitability": {
            "net_margin": _ratio(net_income, revenue_latest),
            "roa": _ratio(net_income, assets),
            "roe": _ratio(net_income, equity),
        },
        "financial_health": {
            "total_cash": cash,
            "total_debt": debt,
            "net_cash": cash - debt if cash is not None and debt is not None else None,
            "debt_to_equity": _ratio(debt, equity),
        },
        "cash_flow": {
            "operating_cf_ttm": operating_cf,
            "free_cash_flow_ttm": free_cash_flow,
            "fcf_margin": _ratio(free_cash_flow, revenue_latest),
        },
        "summary_overrides": {
            "shares_outstanding": resolved_shares,
            "market_cap": market_cap,
        },
    }, None


@lru_cache(maxsize=1)
def _sec_company_tickers() -> dict[str, str]:
    import requests

    response = requests.get(
        "https://www.sec.gov/files/company_tickers.json",
        headers=_sec_headers(),
        timeout=20,
    )
    response.raise_for_status()
    rows = response.json().values()
    return {
        str(row.get("ticker", "")).upper(): str(row.get("cik_str", "")).zfill(10)
        for row in rows
        if row.get("ticker") and row.get("cik_str")
    }


def _sec_cik_for_symbol(symbol: str) -> str | None:
    return _sec_company_tickers().get(symbol.upper())


def _sec_headers() -> dict[str, str]:
    return {
        "User-Agent": os.getenv(
            "SEC_USER_AGENT",
            "ai-stock-analysis research app contact@example.com",
        )
    }


def _latest_annual_values(facts: dict[str, Any], *concepts: str) -> tuple[float | None, float | None]:
    entries: list[dict[str, Any]] = []
    for concept in concepts:
        units = ((facts.get(concept) or {}).get("units") or {})
        entries.extend(units.get("USD") or [])
    annuals = [
        item
        for item in entries
        if item.get("form") == "10-K" and item.get("fy") and item.get("val") is not None
    ]
    annuals.sort(key=lambda item: (item.get("fy") or 0, item.get("end") or ""), reverse=True)
    values = [_to_float(item.get("val")) for item in annuals]
    values = [value for value in values if value is not None]
    latest = values[0] if values else None
    previous = values[1] if len(values) > 1 else None
    return latest, previous


def _latest_instant_value(facts: dict[str, Any], *concepts: str) -> float | None:
    entries: list[dict[str, Any]] = []
    for concept in concepts:
        units = ((facts.get(concept) or {}).get("units") or {})
        entries.extend(units.get("USD") or [])
    instants = [
        item
        for item in entries
        if item.get("form") in {"10-K", "10-Q"} and item.get("val") is not None
    ]
    instants.sort(key=lambda item: item.get("end") or "", reverse=True)
    return _to_float(instants[0].get("val")) if instants else None


def _latest_share_value(dei_facts: dict[str, Any], gaap_facts: dict[str, Any]) -> float | None:
    entries: list[dict[str, Any]] = []
    for facts, concept in (
        (dei_facts, "EntityCommonStockSharesOutstanding"),
        (gaap_facts, "CommonStocksIncludingAdditionalPaidInCapital"),
    ):
        units = ((facts.get(concept) or {}).get("units") or {})
        entries.extend(units.get("shares") or [])
    instants = [
        item
        for item in entries
        if item.get("val") is not None and item.get("end")
    ]
    instants.sort(key=lambda item: item.get("end") or "", reverse=True)
    return _to_float(instants[0].get("val")) if instants else None


def _merge_fundamentals(base: dict[str, Any], fallback: dict[str, Any]) -> dict[str, Any]:
    merged = dict(base)
    for section, values in fallback.items():
        if section == "data_provenance":
            if _section_has_missing_values(base):
                merged[section] = values
            continue
        if not isinstance(values, dict):
            continue
        current = dict(merged.get(section) or {})
        for key, value in values.items():
            if current.get(key) is None and value is not None:
                current[key] = value
        merged[section] = current
    return merged


def _section_has_missing_values(payload: dict[str, Any]) -> bool:
    for section in ("valuation", "growth", "profitability", "financial_health", "cash_flow"):
        values = payload.get(section) or {}
        if any(value is None for value in values.values()):
            return True
    return False


def _safe_fast_info(ticker: Any) -> tuple[dict[str, Any], str | None]:
    try:
        timeout = float(os.getenv("YFINANCE_FAST_INFO_TIMEOUT_SECONDS", "5"))
        raw = _run_with_timeout(lambda: dict(ticker.fast_info or {}), timeout)
        return raw, None
    except TimeoutError:
        logger.warning("yfinance fast_info fetch timed out")
        return {}, "fast_info_timeout"
    except Exception as exc:
        logger.warning("yfinance fast_info fetch failed: %s", exc)
        return {}, "fast_info_unavailable"


def _safe_info(ticker: Any) -> tuple[dict[str, Any], str | None]:
    try:
        timeout = float(os.getenv("YFINANCE_INFO_TIMEOUT_SECONDS", "25"))
        return _run_with_timeout(lambda: ticker.info or {}, timeout), None
    except TimeoutError:
        logger.warning("yfinance info fetch timed out")
        return {}, "info_timeout"
    except Exception as exc:
        logger.warning("yfinance info fetch failed: %s", exc)
        return {}, "info_unavailable"


def _safe_history(ticker: Any) -> tuple[Any, str | None]:
    try:
        timeout = float(os.getenv("YFINANCE_HISTORY_TIMEOUT_SECONDS", "12"))
        return _run_with_timeout(
            lambda: ticker.history(period="1y", interval="1d", auto_adjust=True),
            timeout,
        ), None
    except TimeoutError:
        logger.warning("yfinance history fetch timed out")
        try:
            import pandas as pd

            return pd.DataFrame(), "history_timeout"
        except ImportError:
            raise
    except Exception as exc:
        logger.warning("yfinance history fetch failed: %s", exc)
        try:
            import pandas as pd

            return pd.DataFrame(), "history_unavailable"
        except ImportError:
            raise exc


def _fetch_search_profile(symbol: str) -> tuple[dict[str, Any], str | None]:
    try:
        import requests
    except ImportError:
        return {}, "search_profile_unavailable"

    try:
        response = requests.get(
            "https://query1.finance.yahoo.com/v1/finance/search",
            params={"q": symbol, "quotesCount": 1, "newsCount": 0},
            headers={"User-Agent": "Mozilla/5.0"},
            timeout=6,
        )
        response.raise_for_status()
        quotes = response.json().get("quotes") or []
        match = next((quote for quote in quotes if quote.get("symbol") == symbol), quotes[0] if quotes else {})
        return {
            "longName": match.get("longname") or match.get("shortname"),
            "shortName": match.get("shortname") or match.get("longname"),
            "sector": match.get("sectorDisp") or match.get("sector"),
            "industry": match.get("industryDisp") or match.get("industry"),
            "exchange": match.get("exchange"),
        }, None
    except Exception as exc:
        logger.warning("Yahoo search profile failed for %s: %s", symbol, exc)
        return {}, "search_profile_unavailable"


def _merge_info(
    symbol: str,
    info: dict[str, Any],
    fast_info: dict[str, Any],
    profile: dict[str, Any],
    current_price: float | None,
) -> dict[str, Any]:
    merged = dict(info)
    for source in (profile, fast_info):
        for key, value in source.items():
            if merged.get(key) in (None, "") and value not in (None, ""):
                merged[key] = value

    shares = _first_number(
        merged.get("sharesOutstanding"),
        fast_info.get("shares"),
        fast_info.get("shares_outstanding"),
    )
    if merged.get("currency") is None and fast_info.get("currency"):
        merged["currency"] = fast_info.get("currency")
    if merged.get("currentPrice") is None:
        merged["currentPrice"] = _first_number(fast_info.get("last_price"), current_price)
    if merged.get("previousClose") is None:
        merged["previousClose"] = _first_number(fast_info.get("previous_close"))
    if merged.get("marketCap") is None:
        merged["marketCap"] = _first_number(fast_info.get("market_cap"))
    if merged.get("averageVolume") is None:
        merged["averageVolume"] = _first_number(
            fast_info.get("three_month_average_volume"),
            fast_info.get("ten_day_average_volume"),
        )
    if shares is not None and merged.get("sharesOutstanding") is None:
        merged["sharesOutstanding"] = shares
    if merged.get("marketCap") is None and shares is not None and current_price is not None:
        merged["marketCap"] = shares * current_price
    merged.setdefault("symbol", symbol)
    return merged


def _run_with_timeout(fetcher: Any, timeout_seconds: float) -> Any:
    executor = ThreadPoolExecutor(max_workers=1)
    try:
        future = executor.submit(fetcher)
        return future.result(timeout=timeout_seconds)
    finally:
        executor.shutdown(wait=False, cancel_futures=True)


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
