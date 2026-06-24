# Backend

FastAPI 后端，提供健康检查和股票研究快照接口。

## Local

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

## API

- `GET /health`
- `POST /api/analyze`

## Data Provider

默认优先使用 `yfinance` 拉取公司概览、基础行情、历史价格、估值、增长、盈利能力、现金流和资产负债字段，再通过 `analysis_adapter.py` 输出合规响应。`yfinance` 单项请求设有超时；如果基本面接口异常，后端会回退到 Yahoo chart 快速行情，避免无限等待。

可通过环境变量切换：

```bash
STOCK_DATA_PROVIDER=yfinance
STOCK_DATA_PROVIDER=chart
STOCK_DATA_PROVIDER=demo
```

当数据源临时失败时，接口会回退到合规示例响应，避免前端请求中断。

Render 部署后需要把 `FRONTEND_ORIGIN` 设置为 Vercel 前端域名。
