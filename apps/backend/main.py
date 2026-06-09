from datetime import datetime
import os
from typing import List

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field


class AnalyzeRequest(BaseModel):
    symbol: str = Field(..., min_length=1, max_length=20)


class AnalyzeResponse(BaseModel):
    symbol: str
    as_of: str
    summary: str
    key_points: List[str]
    risks: List[str]
    disclaimer: str


app = FastAPI(title="AI Stock Analysis API", version="0.1.0")

frontend_origin = os.getenv("FRONTEND_ORIGIN", "http://localhost:5173")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[frontend_origin],
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/api/analyze", response_model=AnalyzeResponse)
def analyze(payload: AnalyzeRequest):
    symbol = payload.symbol.strip().upper()
    today = datetime.utcnow().strftime("%Y-%m-%d")

    return AnalyzeResponse(
        symbol=symbol,
        as_of=today,
        summary=(
            f"{symbol} 的第一版分析结果为示例数据，用于验证前端、后端和部署链路。"
            "接入真实行情和财报数据后，应替换为可追溯来源的分析结论。"
        ),
        key_points=[
            "已完成股票代码输入、API 请求和结构化结果返回。",
            "当前结果不包含实时行情、估值或财务数据。",
            "后续可扩展接入 SEC EDGAR、公司公告和行情数据源。",
        ],
        risks=[
            "示例分析不代表真实市场判断。",
            "真实分析需要标注数据日期、来源和报告期。",
            "股票价格可能受宏观、行业、公司事件和市场情绪影响。",
        ],
        disclaimer="仅供研究和信息参考，不构成投资建议。",
    )

