# Stock Analysis MCP Audit

Date: 2026-06-21

Candidate:

- Repository: https://github.com/nickzren/stock-analysis-mcp
- Local audit path: `/private/tmp/stock-analysis-mcp-audit`
- Commit checked: `c4c51b3` from 2026-06-08
- License: MIT

## Summary

`nickzren/stock-analysis-mcp` is a reasonable first candidate for extending this project with stock-analysis tools through MCP. It is more appropriate than trading-agent or broker-integration repositories because it focuses on market data, fundamentals, technicals, comparison, risk summaries, and portfolio exposure rather than placing orders.

The project should still be treated as a research/data assistant, not as an investment-advice engine.

## What Was Checked

- Dependency surface in `pyproject.toml`
- MCP entrypoint in `src/stock_analysis/server.py`
- yfinance data client and cache behavior
- Text sanitization and input validation helpers
- High-risk keyword scan for shell execution, dynamic code execution, broker SDKs, secrets, token access, destructive file operations, and order/trade APIs
- Python syntax compilation with a temporary pycache directory

## Dependencies

Direct dependencies are limited to:

- `fastmcp`
- `yfinance`
- `pandas`
- `numpy`
- `pytz`

No direct broker SDK, exchange SDK, wallet library, or payment API was found in the direct dependency list.

## Observed Safety Properties

- MCP server exposes tool functions; it does not appear to execute shell commands.
- Data access is concentrated through `yfinance`.
- Price resource cache is in-memory and process-local.
- No `.env`, secret file, shell script, Dockerfile, or deployment automation file was found at shallow project depth.
- Inputs such as periods and intervals use allowlists in validators.
- Text fields from external data are sanitized for control characters and length.
- The candidate repository's own `AGENTS.md` requires data-quality fields and keeps the output informational rather than financial advice.

## Main Risks

The primary risk is product/compliance wording, not obvious malicious behavior.

The tool uses action-oriented labels such as `buy`, `sell`, `hold`, `avoid`, position sizing, and account-size based calculations. These labels are too close to personalized investment advice for this project's public product surface.

If used, our app should translate those outputs into research language such as:

- `buy` -> `positive setup signal`
- `sell` -> `risk reduction signal`
- `hold` -> `neutral/monitor signal`
- `avoid` -> `high-risk/watchlist-only signal`
- position sizing -> omit from public output unless explicitly framed as educational risk illustration

## Recommended Initial Integration Policy

For the first integration pass, allow:

- `search_symbol`
- `get_stock_summary`
- `get_price_history`
- `get_technicals`
- `get_fundamentals`
- `get_events`
- `get_news`
- `compare`
- `check_data_quality`

Use with caution:

- `analyze`
- `detect_changes`

Avoid exposing in the public UI initially:

- `analyze_my_position`
- `analyze_portfolio`
- account-size, cost-basis, share-count, or risk-per-trade inputs

## Suggested Codex MCP Command

Installed locally on 2026-06-21 with:

```bash
codex mcp add stock-analysis -- uvx --from git+https://github.com/nickzren/stock-analysis-mcp stock-analysis
```

`uv` / `uvx` was installed to `~/.local/bin` because Homebrew was locked during the setup attempt.

Verification performed:

- `codex mcp list` shows `stock-analysis` as enabled.
- `uvx --from git+https://github.com/nickzren/stock-analysis-mcp stock-analysis --help` fetched dependencies, built the package, and started the FastMCP server successfully.
- The test process exited cleanly.
- After restarting Codex, the MCP tools were available in the `stock_analysis` namespace.
- Read-only checks passed for AAPL using `get_stock_summary`, `get_technicals`, and `get_fundamentals`.
- Returned payloads included `source="yfinance"` and `as_of` provenance timestamps.

## Required Product Guardrails

Any app feature using this MCP should:

- Show data source and data timestamp.
- Include a clear "research only, not investment advice" disclaimer.
- Avoid personalized buy/sell instructions.
- Preserve uncertainty and data-quality warnings.
- Avoid exposing account-size based sizing by default.
- Treat news sentiment as weak evidence unless independently sourced.

## Audit Result

Recommendation: conditionally acceptable for local MCP experimentation.

Do not connect it directly to the production backend until we add an adapter layer that normalizes the output into this project's compliance format.
