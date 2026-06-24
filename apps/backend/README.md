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

默认使用 Yahoo chart 快速接口拉取基础行情和历史价格，再通过 `analysis_adapter.py` 输出合规响应。这样可以避免部分环境中 `yfinance` 基本面接口响应过慢导致前端长时间等待。

可通过环境变量切换：

```bash
STOCK_DATA_PROVIDER=chart
STOCK_DATA_PROVIDER=yfinance
STOCK_DATA_PROVIDER=demo
```

当数据源临时失败时，接口会回退到合规示例响应，避免前端请求中断。

Render 部署后需要把 `FRONTEND_ORIGIN` 设置为 Vercel 前端域名。
