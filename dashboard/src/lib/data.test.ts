import { describe, expect, it } from "vitest";
import { parseCsv } from "./csv";
import { toPoints, toSignals, toTrades, tradeBarTime } from "./data";

describe("parseCsv", () => {
  it("handles quoted commas, doubled quotes and CRLF", () => {
    const rows = parseCsv('a,b\r\n1,"z = 0.53, inside +/-1.5"\r\n2,"say ""hi"""\r\n');
    expect(rows).toEqual([
      { a: "1", b: "z = 0.53, inside +/-1.5" },
      { a: "2", b: 'say "hi"' },
    ]);
  });

  it("returns nothing for empty input", () => {
    expect(parseCsv("")).toEqual([]);
    expect(parseCsv("a,b\n")).toEqual([]);
  });
});

const SIGNALS =
  "run_time,bar_time,symbol,position,action,reason,close,equity\n" +
  '2026-11-16T15:02:00+00:00,2026-11-16T14:45:00+00:00,SPY,flat,enter_long,"Close 590.10 is 2.10 std devs below, mean",590.1,100000\n' +
  "2026-11-16T15:17:00+00:00,2026-11-16T15:00:00+00:00,SPY,long,hold,Waiting,591,100010\n";

describe("log transforms", () => {
  it("parses signals with numbers and dates", () => {
    const s = toSignals(SIGNALS);
    expect(s).toHaveLength(2);
    expect(s[0].close).toBe(590.1);
    expect(s[0].reason).toContain("below, mean");
    expect(s[0].barTime.toISOString()).toBe("2026-11-16T14:45:00.000Z");
  });

  it("treats a missing stop as null", () => {
    const t = toTrades("run_time,symbol,action,qty,ref_price,stop,reason,order_id\n2026-11-16T15:02:00+00:00,SPY,exit,10,590,,Stop hit,abc\n");
    expect(t[0].stop).toBeNull();
  });

  it("maps a trade to the bar it was decided on", () => {
    const trade = toTrades(
      "run_time,symbol,action,qty,ref_price,stop,reason,order_id\n2026-11-16T15:02:00+00:00,SPY,enter_long,10,590.1,585,x,abc\n",
    )[0];
    expect(tradeBarTime(trade, toSignals(SIGNALS)).toISOString()).toBe("2026-11-16T14:45:00.000Z");
  });

  it("builds ascending, de-duplicated chart points", () => {
    const pts = toPoints(
      [
        { t: new Date("2026-01-01T00:02:00Z"), v: 3 },
        { t: new Date("2026-01-01T00:01:00Z"), v: 1 },
        { t: new Date("2026-01-01T00:01:00Z"), v: 2 },
      ],
      (r) => r.t,
      (r) => r.v,
    );
    expect(pts.map((p) => p.value)).toEqual([2, 3]);
  });
});
