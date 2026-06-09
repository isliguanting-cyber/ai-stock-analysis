# Backend

FastAPI 后端，第一版只提供健康检查和示例股票分析接口。

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

Render 部署后需要把 `FRONTEND_ORIGIN` 设置为 Vercel 前端域名。

