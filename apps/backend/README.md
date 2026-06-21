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

默认使用 `yfinance` 拉取基础行情、历史价格、估值、增长、盈利能力和现金流字段，再通过 `analysis_adapter.py` 输出合规响应。

可通过环境变量切换：

```bash
STOCK_DATA_PROVIDER=yfinance
STOCK_DATA_PROVIDER=demo
```

当数据源临时失败时，接口会回退到合规示例响应，避免前端请求中断。

Render 部署后需要把 `FRONTEND_ORIGIN` 设置为 Vercel 前端域名。
