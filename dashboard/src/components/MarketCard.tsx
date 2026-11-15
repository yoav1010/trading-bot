import { useMemo } from "react";
import type { BotData } from "../lib/data";
import { toPoints, tradeBarTime } from "../lib/data";
import { ACTION_LABEL, ago, price } from "../lib/format";
import { TimeChart, type Marker } from "./TimeChart";

export interface MarketInfo {
  symbol: string;
  title: string;
  strategy: string;
  rules: string;
  color: string;
}

export function MarketCard({ market, data }: { market: MarketInfo; data: BotData }) {
  const signals = useMemo(() => data.signals.filter((s) => s.symbol === market.symbol), [data, market.symbol]);
  const trades = useMemo(() => data.trades.filter((t) => t.symbol === market.symbol), [data, market.symbol]);
  const points = useMemo(() => toPoints(signals, (s) => s.barTime, (s) => s.close), [signals]);
  const markers = useMemo<Marker[]>(
    () =>
      trades.map((t) => ({
        time: Math.floor(tradeBarTime(t, data.signals).getTime() / 1000),
        kind: t.action === "enter_long" ? "long" : t.action === "enter_short" ? "short" : "exit",
      })),
    [trades, data.signals],
  );

  const last = signals[signals.length - 1];
  const stop = data.state?.markets[market.symbol]?.stop ?? null;
  const position = last?.position ?? "flat";
  const lastAction = signals.filter((s) => s.action !== "hold").at(-1);

  return (
    <article className="card market">
      <header className="market-head">
        <div>
          <h3>{market.title}</h3>
          <p className="muted small">{market.strategy}</p>
        </div>
        <span className={`pill ${position}`}>{position === "flat" ? "No position" : position.toUpperCase()}</span>
      </header>

      <TimeChart points={points} markers={markers} color={market.color} height={220} valueFormat={price} />
      <p className="legend small muted">
        <span className="up">▲ buy</span> <span className="down">▼ short</span> <span>● exit</span> · close of each bar the bot checked
      </p>

      <dl className="facts">
        <div><dt>Last check</dt><dd>{last ? `${ago(last.runTime)} · bar ${last.barTime.toISOString().slice(11, 16)} UTC` : "Not yet"}</dd></div>
        <div><dt>Last close</dt><dd>{last ? price(last.close) : "–"}</dd></div>
        <div><dt>Stop</dt><dd>{stop != null ? price(stop) : "–"}</dd></div>
        <div><dt>Trades</dt><dd>{trades.length}</dd></div>
      </dl>

      <p className="reason">
        <span className="muted small">Latest decision: </span>
        {last ? <><b>{ACTION_LABEL[last.action] ?? last.action}</b>: {last.reason}</> : "waiting for the first closed bar"}
      </p>
      {lastAction && lastAction !== last && (
        <p className="reason muted small">
          Last action, {ago(lastAction.runTime)}: <b>{ACTION_LABEL[lastAction.action]}</b>: {lastAction.reason}
        </p>
      )}
      <p className="muted small rules">{market.rules}</p>
    </article>
  );
}
