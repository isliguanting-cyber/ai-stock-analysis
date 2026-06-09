import unittest
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ai_stock_analysis import check_report_text


class ComplianceTest(unittest.TestCase):
    def test_template_like_report_passes_core_checks(self):
        text = """
> 数据截止：2026-06-09 21:00 Asia/Shanghai
> 资料来源：SEC EDGAR，公司公告
> 免责声明：本文仅供研究和信息参考，不构成投资建议。

## 核心结论
## 关键依据
## 财务与估值
## 主要风险
## 后续观察指标
"""

        checks = check_report_text(text)

        self.assertTrue(all(check.passed for check in checks))

    def test_missing_disclaimer_is_flagged(self):
        text = """
## 核心结论
## 关键依据
## 财务与估值
## 主要风险
## 后续观察指标
数据日期：2026-06-09
资料来源：公司公告
"""

        checks = check_report_text(text)

        self.assertTrue(
            any(check.name == "disclaimer" and not check.passed for check in checks)
        )


if __name__ == "__main__":
    unittest.main()
