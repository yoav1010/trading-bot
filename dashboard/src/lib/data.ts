import { parseCsv } from "./csv";

export const REPO = "yoav1010/trading-bot";
const RAW = `https://raw.githubusercontent.com/${REPO}`;
// `npm run dev` + `?sample` reads a local sample generated from the backtest (dashboard/sample/,
// git-ignored) to check the UI before the bot has traded. Production always reads the real logs.
const useSample =
  import.meta.env.DEV && typeof window !== "undefined" && new URLSearchParams(window.location.search).has("sample");
export const LOG_URL = useSample ? `${import.meta.env.BASE_URL}sample` : `${RAW}/paper-log`;
export const DOCS_URL = `${RAW}/main/docs`;

export interface SignalRow {
  runTime: Date;
  barTime: Date;
  symbol: string;
  position: string;
  action: string;
  reason: string;
  close: number;
  equity: number;
}

export interface TradeRow {
  runTime: Date;
  symbol: string;
  action: string; // enter_long | enter_short | exit
  qty: number;
  refPrice: number;
  stop: number | null;
  reason: string;
  orderId: string;
}

export interface EquityRow {
  runTime: Date;
  equity: number;
}

export interface BotState {
  peak_equity: number;
  breaker_tripped: boolean;
  markets: Record<string, { last_bar: string | null; stop: number | null }>;
}

export interface BotData {
  signals: SignalRow[];
  trades: TradeRow[];
  equity: EquityRow[];
  state: BotState | null;
}

const num = (s: string) => (s === "" ? NaN : Number(s));

export function toSignals(text: string): SignalRow[] {
  return parseCsv(text).map((r) => ({
    runTime: new Date(r.run_time),
    barTime: new Date(r.bar_time),
    symbol: r.symbol,
    position: r.position,
    action: r.action,
    reason: r.reason,
    close: num(r.close),
    equity: num(r.equity),
  }));
}

export function toTrades(text: string): TradeRow[] {
  return parseCsv(text).map((r) => ({
    runTime: new Date(r.run_time),
    symbol: r.symbol,
    action: r.action,
    qty: num(r.qty),
    refPrice: num(r.ref_price),
    stop: r.stop === "" || r.stop === "None" ? null : num(r.stop),
    reason: r.reason,
    orderId: r.order_id,
  }));
}

export function toEquity(text: string): EquityRow[] {
  return parseCsv(text).map((r) => ({ runTime: new Date(r.run_time), equity: num(r.equity) }));
}

/** A log that doesn't exist yet (e.g. no trades so far) is an empty list, not an error. */
async function fetchText(url: string): Promise<string> {
  const res = await fetch(url, { cache: "no-store" });
  if (res.status === 404) return "";
  if (!res.ok) throw new Error(`${url}: HTTP ${res.status}`);
  return res.text();
}

export async function loadBotData(): Promise<BotData> {
  const [signals, trades, equity, state] = await Promise.all([
    fetchText(`${LOG_URL}/logs/signals.csv`),
    fetchText(`${LOG_URL}/logs/trades.csv`),
    fetchText(`${LOG_URL}/logs/equity.csv`),
    fetchText(`${LOG_URL}/state/bot_state.json`),
  ]);
  return {
    signals: toSignals(signals),
    trades: toTrades(trades),
    equity: toEquity(equity),
    state: state ? (JSON.parse(state) as BotState) : null,
  };
}

/** Chart points: one per unique time, ascending (what lightweight-charts requires). */
export function toPoints<T>(rows: T[], time: (r: T) => Date, value: (r: T) => number) {
  const byTime = new Map<number, number>();
  for (const r of rows) {
    const t = Math.floor(time(r).getTime() / 1000);
    const v = value(r);
    if (Number.isFinite(t) && Number.isFinite(v)) byTime.set(t, v); // later rows win
  }
  return [...byTime.entries()].sort((a, b) => a[0] - b[0]).map(([t, v]) => ({ time: t, value: v }));
}

/** The bar a trade was decided on: the signal logged in the same run for the same symbol. */
export function tradeBarTime(trade: TradeRow, signals: SignalRow[]): Date {
  const match = signals.find(
    (s) => s.symbol === trade.symbol && s.runTime.getTime() === trade.runTime.getTime(),
  );
  return match ? match.barTime : trade.runTime;
}
