"""Lightweight report checks for research hygiene."""

from __future__ import annotations

from dataclasses import dataclass
import re


@dataclass(frozen=True)
class ReportCheck:
    name: str
    passed: bool
    message: str


REQUIRED_SECTIONS = (
    "核心结论",
    "关键依据",
    "财务与估值",
    "主要风险",
    "后续观察指标",
)


def check_report_text(text: str) -> list[ReportCheck]:
    """Return simple checks for source, date, risk, and disclaimer coverage."""
    checks: list[ReportCheck] = []

    for section in REQUIRED_SECTIONS:
        marker = f"## {section}"
        checks.append(
            ReportCheck(
                name=f"section:{section}",
                passed=marker in text,
                message=f"包含章节：{section}" if marker in text else f"缺少章节：{section}",
            )
        )

    has_date = bool(re.search(r"20\d{2}-\d{2}-\d{2}", text))
    checks.append(
        ReportCheck(
            name="date",
            passed=has_date,
            message="包含明确日期" if has_date else "缺少 YYYY-MM-DD 格式日期",
        )
    )

    has_source = any(keyword in text for keyword in ("来源", "资料来源", "数据来源"))
    checks.append(
        ReportCheck(
            name="source",
            passed=has_source,
            message="包含来源说明" if has_source else "缺少来源说明",
        )
    )

    has_risk = "风险" in text
    checks.append(
        ReportCheck(
            name="risk",
            passed=has_risk,
            message="包含风险提示" if has_risk else "缺少风险提示",
        )
    )

    has_disclaimer = "不构成投资建议" in text
    checks.append(
        ReportCheck(
            name="disclaimer",
            passed=has_disclaimer,
            message="包含免责声明" if has_disclaimer else "缺少“不构成投资建议”免责声明",
        )
    )

    return checks

