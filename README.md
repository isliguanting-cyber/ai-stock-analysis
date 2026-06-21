# AI 股票分析

用于沉淀股票、行业、财务数据、市场情绪和风险因素研究的工作区。本项目强调可验证数据、清晰推理、日期标注和风险披露。

## 目录结构

- `config/`: 数据源、分析口径和项目配置。
- `data/raw/`: 原始数据，仅保存可追溯来源的数据快照。
- `data/processed/`: 清洗后的中间数据或指标表。
- `notebooks/`: 探索性分析笔记。
- `reports/`: Markdown 研究报告。
- `scripts/`: 项目辅助脚本。
- `src/ai_stock_analysis/`: 可复用的分析与合规检查代码。
- `templates/`: 报告模板。
- `apps/frontend/`: Vite + React 前端。
- `apps/backend/`: FastAPI 后端。

## 快速开始

1. 复制环境变量样例：

   ```bash
   cp .env.example .env.local
   ```

2. 在 `.env.local` 中填写需要的数据源 API Key。不要提交真实密钥。

3. 使用模板创建报告：

   ```bash
   cp templates/stock_analysis.md reports/股票代码-研究报告.md
   ```

4. 运行报告合规检查：

   ```bash
   python3 scripts/check_report.py reports/股票代码-研究报告.md
   ```

## 最小前后端

后端：

```bash
cd apps/backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

前端：

```bash
cd apps/frontend
npm install
npm run dev
```

本地访问 `http://localhost:5173`，前端默认调用 `http://localhost:8000`。

后端的公开响应通过 `apps/backend/analysis_adapter.py` 统一生成。后续接入真实数据源时，优先把 MCP、yfinance、OpenBB 或付费 API 的原始结果转换到 adapter 输入结构，再由 adapter 输出给前端，避免在公开页面暴露买卖指令式措辞。

## 部署

- 后端部署到 Render：Root Directory 选择 `apps/backend`，Build Command 使用 `pip install -r requirements.txt`，Start Command 使用 `uvicorn main:app --host 0.0.0.0 --port $PORT`。
- 前端部署到 Vercel：Root Directory 选择 `apps/frontend`，Build Command 使用 `npm run build`，Output Directory 使用 `dist`。
- Vercel 环境变量：`VITE_API_BASE_URL=https://你的后端域名`。
- Render 环境变量：`FRONTEND_ORIGIN=https://你的前端域名`。

## 研究要求

- 涉及实时行情、最新财报、新闻、评级、政策或宏观数据时，必须标注数据日期和发布时间。
- 关键数字需标注单位、时间范围和来源。
- 结论应区分事实、估算、观点和假设。
- 输出仅供研究和信息参考，不构成投资建议。
