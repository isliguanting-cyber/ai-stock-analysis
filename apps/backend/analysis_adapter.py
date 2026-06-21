from __future__ import annotations

from datetime import datetime
import re
from typing import Any


DISCLAIMER = "仅供研究和信息参考，不构成投资建议。"

ACTION_WORDS = {
    "strong buy": "强正面研究信号",
    "buy": "正面研究信号",
    "sell": "风险降低信号",
    "hold": "中性观察信号",
    "avoid": "高风险观察信号",
    "starter position": "小仓位情景测算",
    "position sizing": "风险暴露测算",
    "买入": "正面研究信号",
    "卖出": "风险降低信号",
    "持有": "中性观察信号",
}


def sanitize_recommendation_language(text: str) -> str:
    """Rewrite action-oriented labels into research-oriented language."""
    sanitized = text
    for source, target in sorted(ACTION_WORDS.items(), key=lambda item: len(item[0]), reverse=True):
        sanitized = re.sub(re.escape(source), target, sanitized, flags=re.IGNORECASE)
    return sanitized


def build_research_response(
    symbol: str,
    source_payloads: dict[str, dict[str, Any]] | None = None,
    *,
    generated_at: datetime | None = None,
) -> dict[str, Any]:
    """Convert raw stock data payloads into the public API response shape."""
    normalized_symbol = symbol.strip().upper()
    payloads = source_payloads or {}
    now = generated_at or datetime.utcnow()

    if not payloads:
        return {
            "symbol": normalized_symbol,
            "as_of": now.strftime("%Y-%m-%d"),
            "summary": (
                f"{normalized_symbol} 的当前结果为研究框架示例。"
                "真实数据接入后，将展示可追溯来源、数据日期、关键指标和风险提示。"
            ),
            "key_points": [
                "已完成股票代码输入、API 请求和结构化结果返回。",
                "后端已预留外部数据 adapter，可接入 MCP、yfinance、OpenBB 或付费数据源。",
                "公开输出会过滤买卖指令式措辞，统一改写为研究信号和风险提示。",
            ],
            "risks": [
                "当前示例结果不包含实时行情、估值或财务数据。",
                "真实分析需要核验数据日期、来源、报告期和数据质量。",
                "股票价格可能受宏观、行业、公司事件和市场情绪影响。",
            ],
            "disclaimer": DISCLAIMER,
        }

    summary = payloads.get("summary", {})
    technicals = payloads.get("technicals", {})
    fundamentals = payloads.get("fundamentals", {})

    as_of = _latest_as_of(summary, technicals, fundamentals) or now.strftime("%Y-%m-%d")
    company_name = summary.get("name") or normalized_symbol
    sector = summary.get("sector") or "行业未知"
    price = _fmt_price(summary.get("current_price"), summary.get("currency"))
    market_cap = _fmt_large_number(summary.get("market_cap"))

    key_points = [
        _company_point(company_name, sector, price, market_cap),
        _technical_point(technicals),
        _fundamental_point(fundamentals),
        _cash_flow_point(fundamentals),
    ]
    key_points = [sanitize_recommendation_language(point) for point in key_points if point]

    risks = [
        _valuation_risk(fundamentals),
        _technical_risk(technicals),
        "数据主要来自第三方行情与财务接口，可能存在延迟、缺失或口径差异。",
    ]
    risks = [sanitize_recommendation_language(risk) for risk in risks if risk]

    return {
        "symbol": normalized_symbol,
        "as_of": as_of,
        "summary": sanitize_recommendation_language(
            f"{normalized_symbol}（{company_name}）研究快照：当前价格 {price}，"
            f"所属行业为 {sector}。以下结论基于已接入数据源的指标整理，"
            "用于辅助研究，不代表确定性判断。"
        ),
        "key_points": key_points,
        "risks": risks,
        "disclaimer": DISCLAIMER,
    }


def _latest_as_of(*payloads: dict[str, Any]) -> str | None:
    dates: list[str] = []
    for payload in payloads:
        provenance = payload.get("data_provenance")
        if not isinstance(provenance, dict):
            continue
        for item in provenance.values():
            if isinstance(item, dict) and item.get("as_of"):
                dates.append(str(item["as_of"]))
    return max(dates)[:10] if dates else None


def _company_point(company_name: str, sector: str, price: str, market_cap: str) -> str:
    return f"公司与行情：{company_name}，行业 {sector}，当前价格 {price}，市值约 {market_cap}。"


def _technical_point(technicals: dict[str, Any]) -> str | None:
    ma = technicals.get("moving_averages") or {}
    rsi = technicals.get("rsi") or {}
    returns = technicals.get("returns") or {}
    if not ma and not rsi and not returns:
        return None
    return (
        "技术面：价格相对 50 日均线 "
        f"{_fmt_pct(ma.get('price_vs_sma50'))}，相对 200 日均线 {_fmt_pct(ma.get('price_vs_sma200'))}；"
        f"RSI 为 {_fmt_number(rsi.get('value'))}；近 3 个月收益 {_fmt_pct(returns.get('return_3m'))}。"
    )


def _fundamental_point(fundamentals: dict[str, Any]) -> str | None:
    valuation = fundamentals.get("valuation") or {}
    growth = fundamentals.get("growth") or {}
    profitability = fundamentals.get("profitability") or {}
    if not valuation and not growth and not profitability:
        return None
    return (
        "基本面：滚动市盈率 "
        f"{_fmt_number(valuation.get('pe_trailing'))}，营收同比 {_fmt_pct(growth.get('revenue_yoy'))}，"
        f"净利率 {_fmt_pct(profitability.get('net_margin'))}。"
    )


def _cash_flow_point(fundamentals: dict[str, Any]) -> str | None:
    cash_flow = fundamentals.get("cash_flow") or {}
    health = fundamentals.get("financial_health") or {}
    if not cash_flow and not health:
        return None
    return (
        "现金流与资产负债：自由现金流 "
        f"{_fmt_large_number(cash_flow.get('free_cash_flow_ttm'))}，"
        f"净现金 {_fmt_large_number(health.get('net_cash'))}，"
        f"流动比率 {_fmt_number(health.get('current_ratio'))}。"
    )


def _valuation_risk(fundamentals: dict[str, Any]) -> str | None:
    valuation = fundamentals.get("valuation") or {}
    pe = valuation.get("pe_trailing")
    if pe is None:
        return "估值数据不足，无法判断估值相对水平。"
    if _to_float(pe) and _to_float(pe) > 30:
        return f"估值风险：滚动市盈率约 {_fmt_number(pe)}，若增长不及预期，估值可能承压。"
    return f"估值观察：滚动市盈率约 {_fmt_number(pe)}，仍需结合行业和增长质量比较。"


def _technical_risk(technicals: dict[str, Any]) -> str | None:
    macd = technicals.get("macd") or {}
    price_position = technicals.get("price_position") or {}
    bearish_cross = ((macd.get("rules") or {}).get("bearish_cross") or {}).get("triggered")
    from_high = price_position.get("from_52w_high")
    if bearish_cross:
        return "技术风险：MACD 显示偏弱信号，短期走势仍需观察成交量和均线变化。"
    if from_high is not None:
        return f"价格位置风险：当前距离 52 周高点 {_fmt_pct(from_high)}，需关注回撤与波动扩大。"
    return None


def _fmt_price(value: Any, currency: Any = None) -> str:
    number = _to_float(value)
    if number is None:
        return "未知"
    suffix = f" {currency}" if currency else ""
    return f"{number:,.2f}{suffix}"


def _fmt_large_number(value: Any) -> str:
    number = _to_float(value)
    if number is None:
        return "未知"
    abs_number = abs(number)
    if abs_number >= 1_000_000_000_000:
        return f"{number / 1_000_000_000_000:.2f} 万亿"
    if abs_number >= 100_000_000:
        return f"{number / 100_000_000:.2f} 亿"
    if abs_number >= 10_000:
        return f"{number / 10_000:.2f} 万"
    return f"{number:.2f}"


def _fmt_pct(value: Any) -> str:
    number = _to_float(value)
    if number is None:
        return "未知"
    return f"{number * 100:.2f}%"


def _fmt_number(value: Any) -> str:
    number = _to_float(value)
    if number is None:
        return "未知"
    return f"{number:.2f}"


def _to_float(value: Any) -> float | None:
    try:
        if value is None:
            return None
        return float(value)
    except (TypeError, ValueError):
        return None
