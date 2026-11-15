import { useEffect, useRef } from "react";
import { ColorType, createChart, type SeriesMarker, type UTCTimestamp } from "lightweight-charts";

export interface Point {
  time: number; // unix seconds
  value: number;
}

export interface Marker {
  time: number;
  kind: "long" | "short" | "exit";
}

const MIN_POINTS = 3;

const MARKER_STYLE = {
  long: { color: "#1a9850", shape: "arrowUp", position: "belowBar" },
  short: { color: "#d73027", shape: "arrowDown", position: "aboveBar" },
  exit: { color: "#7b7b7b", shape: "circle", position: "aboveBar" },
} as const;

function cssVar(name: string, fallback: string) {
  const v = getComputedStyle(document.documentElement).getPropertyValue(name).trim();
  return v || fallback;
}

/** Line chart over time with optional trade markers (TradingView lightweight-charts). */
export function TimeChart({ points, markers = [], color, height = 260, valueFormat }: {
  points: Point[];
  markers?: Marker[];
  color: string;
  height?: number;
  valueFormat?: (v: number) => string;
}) {
  const ref = useRef<HTMLDivElement>(null);

  const enough = points.length >= MIN_POINTS;

  useEffect(() => {
    if (!ref.current || !enough) return;
    const text = cssVar("--muted", "#888");
    const grid = cssVar("--grid", "rgba(128,128,128,0.15)");
    const chart = createChart(ref.current, {
      autoSize: true,
      layout: { background: { type: ColorType.Solid, color: "transparent" }, textColor: text, fontFamily: "inherit" },
      grid: { vertLines: { color: grid }, horzLines: { color: grid } },
      rightPriceScale: { borderVisible: false },
      timeScale: { borderVisible: false, timeVisible: true, secondsVisible: false },
      localization: valueFormat ? { priceFormatter: valueFormat } : undefined,
      handleScroll: false,
      handleScale: false,
    });
    const series = chart.addLineSeries({ color, lineWidth: 2, priceLineVisible: false });
    series.setData(points.map((p) => ({ time: p.time as UTCTimestamp, value: p.value })));
    const sorted = [...markers].sort((a, b) => a.time - b.time);
    // Shapes only: text labels overlap when trades cluster. The card shows a legend instead.
    series.setMarkers(sorted.map((m): SeriesMarker<UTCTimestamp> => ({
      time: m.time as UTCTimestamp,
      ...MARKER_STYLE[m.kind],
    })));
    chart.timeScale().fitContent();
    return () => chart.remove();
  }, [points, markers, color, valueFormat, enough]);

  if (!enough) {
    return (
      <div className="chart empty" style={{ height }}>
        {points.length === 0
          ? "No data yet. The bot logs a point every time it checks this market."
          : `${points.length} of ${MIN_POINTS} points so far. The chart appears once there's a little history.`}
      </div>
    );
  }
  return <div className="chart" ref={ref} style={{ height }} />;
}
