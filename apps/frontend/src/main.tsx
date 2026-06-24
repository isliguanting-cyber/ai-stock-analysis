import React, { FormEvent, useState } from "react";
import { createRoot } from "react-dom/client";
import "./styles.css";

type Analysis = {
  symbol: string;
  as_of: string;
  summary: string;
  key_points: string[];
  risks: string[];
  disclaimer: string;
  sections?: Array<{
    title: string;
    items: Array<{
      label: string;
      value: string;
    }>;
  }>;
};

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";
const REQUEST_TIMEOUT_MS = 60000;
const QUICK_SYMBOLS = ["AAPL", "MSFT", "NVDA", "TSLA", "GOOGL"];

function App() {
  const [symbol, setSymbol] = useState("AAPL");
  const [analysis, setAnalysis] = useState<Analysis | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  async function requestAnalysis(nextSymbol = symbol) {
    setError("");
    setLoading(true);

    const controller = new AbortController();
    const normalizedSymbol = nextSymbol.trim().toUpperCase();
    const timeoutId = window.setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);

    try {
      const response = await fetch(`${API_BASE_URL}/api/analyze`, {
        method: "POST",
        signal: controller.signal,
        headers: {
          "Content-Type": "application/json"
        },
        body: JSON.stringify({ symbol: normalizedSymbol })
      });

      if (!response.ok) {
        throw new Error(`请求失败：${response.status}`);
      }

      setAnalysis(await response.json());
    } catch (err) {
      if (err instanceof DOMException && err.name === "AbortError") {
        setError("请求超时，请稍后重试。完整数据源偶尔会较慢，系统已避免无限等待。");
      } else {
        setError(err instanceof Error ? err.message : "请求失败，请稍后重试。");
      }
    } finally {
      window.clearTimeout(timeoutId);
      setLoading(false);
    }
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    await requestAnalysis();
  }

  async function handleQuickSymbol(nextSymbol: string) {
    setSymbol(nextSymbol);
    await requestAnalysis(nextSymbol);
  }

  return (
    <main className="page">
      <section className="workspace">
        <header className="topbar">
          <div>
            <p className="eyebrow">AI Stock Analysis</p>
            <h1>股票研究工作台</h1>
          </div>
          <div className="statusPill">Research only</div>
        </header>

        <form className="commandBar" onSubmit={handleSubmit}>
          <div className="field">
            <label htmlFor="symbol">股票代码</label>
            <div className="searchRow">
              <input
                id="symbol"
                value={symbol}
                onChange={(event) => setSymbol(event.target.value.toUpperCase())}
                placeholder="AAPL"
                autoComplete="off"
              />
              <button type="submit" disabled={loading || !symbol.trim()}>
                {loading ? "分析中" : "生成"}
              </button>
            </div>
          </div>

          <div className="quickSymbols" aria-label="快捷股票代码">
            {QUICK_SYMBOLS.map((quickSymbol) => (
              <button
                className={symbol === quickSymbol ? "active" : ""}
                disabled={loading}
                key={quickSymbol}
                onClick={() => handleQuickSymbol(quickSymbol)}
                type="button"
              >
                {quickSymbol}
              </button>
            ))}
          </div>
        </form>

        {error ? <p className="alert">{error}</p> : null}

        {loading ? (
          <section className="panel skeletonPanel" aria-label="加载中">
            <div className="skeletonHeader">
              <span />
              <span />
            </div>
            <div className="skeletonLine wide" />
            <div className="skeletonLine" />
            <div className="skeletonGrid">
              <span />
              <span />
              <span />
              <span />
            </div>
          </section>
        ) : null}

        {analysis && !loading ? (
          <section className="panel result" aria-label="分析结果">
            <div className="resultHeader">
              <div>
                <p className="eyebrow">Result</p>
                <h2>{analysis.symbol}</h2>
              </div>
              <span>数据日期：{analysis.as_of}</span>
            </div>

            <p className="summary">{analysis.summary}</p>

            <div className="columns">
              <section>
                <h3>关键依据</h3>
                <ul>
                  {analysis.key_points.map((point) => (
                    <li key={point}>{point}</li>
                  ))}
                </ul>
              </section>

              <section>
                <h3>主要风险</h3>
                <ul>
                  {analysis.risks.map((risk) => (
                    <li key={risk}>{risk}</li>
                  ))}
                </ul>
              </section>
            </div>

            {analysis.sections?.length ? (
              <div className="detailGrid">
                {analysis.sections.map((section) => (
                  <section className="detailSection" key={section.title}>
                    <h3>{section.title}</h3>
                    <dl>
                      {section.items.map((item) => (
                        <div className="metric" key={`${section.title}-${item.label}`}>
                          <dt>{item.label}</dt>
                          <dd>{item.value}</dd>
                        </div>
                      ))}
                    </dl>
                  </section>
                ))}
              </div>
            ) : null}

            <p className="disclaimer">{analysis.disclaimer}</p>
          </section>
        ) : !loading ? (
          <section className="panel empty" aria-label="暂无分析结果">
            <div>
              <p className="eyebrow">Ready</p>
              <h2>暂无研究快照</h2>
            </div>
            <p>选择一个股票代码开始。</p>
          </section>
        ) : null}
      </section>
    </main>
  );
}

createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);
