import { useEffect, useMemo, useState } from "react";
import { MarketCard, type MarketInfo } from "./components/MarketCard";
import { TimeChart } from "./components/TimeChart";
import { DOCS_URL, REPO, loadBotData, toPoints, type BotData } from "./lib/data";
import { ACTION_LABEL, ago, pct, price, usd, when } from "./lib/format";

const MARKETS: MarketInfo[] = [
  {
    symbol: "SPY",
    title: "SPY · S&P 500 ETF",
    strategy: "Mean reversion · 15-minute bars",
    rules: "Long when the close is 2.0+ std devs below its 40-bar mean, short when 2.0+ above; exit back at the mean or at a 2-ATR stop. Parameters chosen by walk-forward tuning.",
    color: "#2166ac",
  },
  {
    symbol: "BTC/USD",
    title: "BTC/USD · Bitcoin",
    strategy: "Momentum breakout · 1-hour bars · long only",
    rules: "Long when the close breaks the previous 20-bar high on 1.5x+ average volume; exit on a break of the 20-bar low or a 2-ATR trailing stop.",
    color: "#e08214",
  },
];

const GH = `https://github.com/${REPO}`;

export default function App() {
  const [data, setData] = useState<BotData | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [onlyActions, setOnlyActions] = useState(false);

  useEffect(() => {
    const load = () => loadBotData().then(setData).catch((e: Error) => setError(e.message));
    load();
    const id = setInterval(load, 5 * 60 * 1000); // the bot runs every 15 minutes
    return () => clearInterval(id);
  }, []);

  const equityPoints = useMemo(() => (data ? toPoints(data.equity, (e) => e.runTime, (e) => e.equity) : []), [data]);

  if (error) return <main className="wrap"><p className="card error">Couldn't load the bot's logs: {error}</p></main>;
  if (!data) return <main className="wrap"><p className="muted">Loading the bot's logs…</p></main>;

  const first = data.equity[0]?.equity;
  const latest = data.equity.at(-1);
  const change = first && latest ? latest.equity / first - 1 : 0;
  const tripped = data.state?.breaker_tripped ?? false;
  const feed = [...data.signals].reverse().filter((s) => !onlyActions || s.action !== "hold").slice(0, 60);

  return (
    <main className="wrap">
      <header className="top">
        <div>
          <h1>Paper-Trading Bot</h1>
          <p className="muted">
            Two rule-based strategies trading Alpaca's <b>paper</b> account (simulated money, real prices), run every
            15 minutes by GitHub Actions. Every decision below comes straight from the bot's logs.
          </p>
        </div>
        <nav className="links">
          <a href={GH}>Code</a>
          <a href={`${GH}/actions/workflows/paper-trade.yml`}>Runs</a>
          <a href={`${GH}/commits/paper-log`}>Log history</a>
        </nav>
      </header>

      <section className="stats">
        <div className="card stat"><span className="muted small">Paper equity</span><strong>{latest ? usd(latest.equity) : "–"}</strong></div>
        <div className="card stat"><span className="muted small">Since first run</span><strong className={change >= 0 ? "up" : "down"}>{pct(change)}</strong></div>
        <div className="card stat"><span className="muted small">Last run</span><strong>{latest ? ago(latest.runTime) : "–"}</strong></div>
        <div className="card stat"><span className="muted small">Trades placed</span><strong>{data.trades.length}</strong></div>
        <div className="card stat"><span className="muted small">Circuit breaker</span><strong className={tripped ? "down" : "up"}>{tripped ? "Tripped" : "OK"}</strong></div>
      </section>

      <section className="card">
        <h2>Account equity</h2>
        <TimeChart points={equityPoints} color="#5e3c99" height={220} valueFormat={(v) => usd(v)} />
      </section>

      <section className="markets">
        {MARKETS.map((m) => <MarketCard key={m.symbol} market={m} data={data} />)}
      </section>

      <section className="card">
        <div className="row-between">
          <h2>Decision log</h2>
          <label className="small"><input type="checkbox" checked={onlyActions} onChange={(e) => setOnlyActions(e.target.checked)} /> Only buys, shorts and exits</label>
        </div>
        {feed.length === 0 ? <p className="muted">No decisions yet.</p> : (
          <div className="table-scroll">
            <table>
              <thead><tr><th>When</th><th>Market</th><th>Decision</th><th>Close</th><th>Why</th></tr></thead>
              <tbody>
                {feed.map((s, i) => (
                  <tr key={i} className={s.action !== "hold" ? "action-row" : undefined}>
                    <td>{when(s.runTime)}</td>
                    <td>{s.symbol}</td>
                    <td><span className={`tag ${s.action}`}>{ACTION_LABEL[s.action] ?? s.action}</span></td>
                    <td>{price(s.close)}</td>
                    <td className="why">{s.reason}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      <section className="card">
        <h2>Orders</h2>
        {data.trades.length === 0 ? (
          <p className="muted">No orders yet. The bot only trades when a rule fires; most checks end in "Hold".</p>
        ) : (
          <div className="table-scroll">
            <table>
              <thead><tr><th>When</th><th>Market</th><th>Order</th><th>Qty</th><th>Price</th><th>Stop</th><th>Why</th></tr></thead>
              <tbody>
                {[...data.trades].reverse().map((t, i) => (
                  <tr key={i}>
                    <td>{when(t.runTime)}</td>
                    <td>{t.symbol}</td>
                    <td><span className={`tag ${t.action}`}>{ACTION_LABEL[t.action] ?? t.action}</span></td>
                    <td>{t.qty < 1 ? t.qty.toFixed(5) : t.qty}</td>
                    <td>{price(t.refPrice)}</td>
                    <td>{t.stop != null ? price(t.stop) : "–"}</td>
                    <td className="why">{t.reason}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      <section className="card">
        <h2>Research behind the rules</h2>
        <p className="muted">
          Before trading, both strategies were backtested on historical data and tuned with walk-forward testing:
          parameters are picked on one period and judged only on the next, unseen period. Full write-up in the{" "}
          <a href={`${GH}#readme`}>README</a>.
        </p>
        <div className="figures">
          <figure><img src={`${DOCS_URL}/walkforward_btc.png`} alt="BTC walk-forward out-of-sample equity" loading="lazy" /><figcaption>BTC breakout, out of sample: tuned vs defaults vs buy and hold</figcaption></figure>
          <figure><img src={`${DOCS_URL}/backtest_btc.png`} alt="BTC backtest with trades marked" loading="lazy" /><figcaption>BTC backtest: trades on price, equity and drawdown</figcaption></figure>
        </div>
      </section>

      <footer className="muted small">
        Paper trading only: simulated money, no real orders. An engineering project, not financial advice.
        {latest && <> Data as of {when(latest.runTime)}; refreshes every 5 minutes.</>}
      </footer>
    </main>
  );
}
