import os
from typing import List

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from analysis_adapter import build_research_response
from stock_data_provider import fetch_stock_payloads


class AnalyzeRequest(BaseModel):
    symbol: str = Field(..., min_length=1, max_length=20)


class AnalyzeResponse(BaseModel):
    symbol: str
    as_of: str
    summary: str
    key_points: List[str]
    risks: List[str]
    disclaimer: str
    sections: List[dict[str, object]] = Field(default_factory=list)


app = FastAPI(title="AI Stock Analysis API", version="0.1.0")

frontend_origins = [
    origin.strip()
    for origin in os.getenv("FRONTEND_ORIGIN", "http://localhost:5173").split(",")
    if origin.strip()
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=frontend_origins,
    allow_origin_regex=r"https://.*\.vercel\.app",
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
    source_payloads = fetch_stock_payloads(symbol)
    return AnalyzeResponse(**build_research_response(symbol, source_payloads))
