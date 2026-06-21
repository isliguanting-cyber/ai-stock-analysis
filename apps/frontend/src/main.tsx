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
};

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";

function App() {
  const [symbol, setSymbol] = useState("AAPL");
  const [analysis, setAnalysis] = useState<Analysis | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    setLoading(true);

    try {
      const response = await fetch(`${API_BASE_URL}/api/analyze`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json"
        },
        body: JSON.stringify({ symbol })
      });

      if (!response.ok) {
        throw new Error(`请求失败：${response.status}`);
      }

      setAnalysis(await response.json());
    } catch (err) {
      setError(err instanceof Error ? err.message : "请求失败，请稍后重试。");
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="page">
      <section className="workspace">
        <div className="header">
          <p className="eyebrow">AI Stock Analysis</p>
          <h1>股票分析工作台</h1>
          <p className="subtitle">输入股票代码，生成带数据日期、关键依据和风险提示的研究快照。</p>
        </div>

        <form className="search" onSubmit={handleSubmit}>
          <label htmlFor="symbol">股票代码</label>
          <div className="searchRow">
            <input
              id="symbol"
              value={symbol}
              onChange={(event) => setSymbol(event.target.value)}
              placeholder="例如 AAPL"
              autoComplete="off"
            />
            <button type="submit" disabled={loading || !symbol.trim()}>
              {loading ? "生成中..." : "生成分析"}
            </button>
          </div>
        </form>

        {error ? <p className="error">{error}</p> : null}

        {analysis ? (
          <section className="result" aria-label="分析结果">
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

            <p className="disclaimer">{analysis.disclaimer}</p>
          </section>
        ) : (
          <section className="empty">
            输入股票代码后生成研究快照。
          </section>
        )}
      </section>
    </main>
  );
}

createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);
