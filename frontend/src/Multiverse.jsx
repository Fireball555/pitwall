import { useEffect, useMemo, useState } from "react";
import { optionLabel } from "./CarCard.jsx";

const AUTO_CLOSE_MS = 10000;

// "Inside PitWall's head": for one decision, each option against staying out, future by future.
// Every option is raced on the SAME imagined futures, so the difference per future is a fair,
// paired comparison: dots left of the line are futures where that choice finished ahead.
export default function Multiverse({ lap, decision, onClose, auto = true }) {
  const [phase, setPhase] = useState(0); // 0 dots appearing, 1 verdict shown
  useEffect(() => {
    const t1 = setTimeout(() => setPhase(1), 1500);
    const t2 = auto ? setTimeout(onClose, AUTO_CLOSE_MS) : null;
    const key = (e) => { if (e.key === "Escape" || e.key === " " || e.key === "Enter") { e.preventDefault(); onClose(); } };
    window.addEventListener("keydown", key);
    return () => { clearTimeout(t1); if (t2) clearTimeout(t2); window.removeEventListener("keydown", key); };
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const { ref, rows } = useMemo(() => {
    const s = decision.samples ?? {};
    const all = Object.entries(decision.options).filter(([k]) => s[k]?.length).map(([k, mean]) => ({ k, mean, xs: s[k] }));
    const reference = all.find((r) => r.k === "stay out") ?? [...all].sort((x, y) => x.mean - y.mean)[0];
    const others = all.filter((r) => r !== reference).sort((x, y) => x.mean - y.mean).slice(0, 4)
      .map((r) => ({ ...r, d: r.xs.map((x, j) => x - reference.xs[j]) }));   // same future, two choices
    return { ref: reference, rows: others };
  }, [decision]);
  if (!ref || rows.length < 1) return null;

  const all = rows.flatMap((r) => r.d).sort((x, y) => x - y);
  const lo = Math.min(-3, all[Math.floor(all.length * 0.03)] ?? -3);
  const hi = Math.max(3, all[Math.floor(all.length * 0.97)] ?? 3);
  const pct = (v) => `${(100 * (Math.min(hi, Math.max(lo, v)) - lo)) / (hi - lo)}%`;
  const span = hi - lo;
  const step = span > 80 ? 20 : span > 40 ? 10 : span > 16 ? 5 : span > 8 ? 2 : 1;
  const ticks = [];
  for (let v = Math.ceil(lo / step) * step; v <= hi; v += step) ticks.push(v);
  const best = rows[0];
  const bestIsPit = best.mean < ref.mean;
  const n = best.d.length;
  const wins = best.d.filter((x) => x < 0).length;
  const refName = ref.k === "stay out" ? "staying out" : optionLabel(ref.k).toLowerCase();

  return (
    <div className="mv-backdrop" onClick={onClose}>
      <section className="mv" onClick={(e) => e.stopPropagation()} aria-label="PitWall's imagined futures">
        {bestIsPit && auto && <div className="mv-flash" />}
        <header className="mv-head">
          <div>
            <p className="mv-kicker">Lap {lap} · inside PitWall's head</p>
            {bestIsPit && auto && <p className="mv-box">Box, box</p>}
            <h2>{n} imagined futures, every choice tested on each</h2>
            <p className="mv-sub">Each dot is one imagined future, raced to the chequered flag with its own safety cars, rain and lap times. It shows how much faster (left) or slower (right) that choice finished than {refName}, in that same future.</p>
          </div>
          <button className="btn" onClick={onClose}>Continue race</button>
        </header>
        <div className="mv-plot">
          <div className="mv-axis" aria-hidden="true">
            {ticks.map((v) => <span key={v} style={{ left: pct(v) }}>{v === 0 ? refName : `${v > 0 ? "+" : "−"}${Math.abs(v)} s`}</span>)}
          </div>
          {rows.map((r, ri) => (
            <div key={r.k} className={`mv-row ${phase && ri === 0 && bestIsPit ? "chosen" : ""}`}>
              <span className="mv-label">{optionLabel(r.k)}</span>
              <div className="mv-strip">
                {ticks.map((v) => <i key={v} className={`mv-grid ${v === 0 ? "zero" : ""}`} style={{ left: pct(v) }} />)}
                {r.d.map((x, j) => (
                  <b key={j} className={`mv-dot ${x < 0 ? "win" : "loss"}`} style={{ left: pct(x), top: `${12 + ((j * 37) % 76)}%`, animationDelay: `${ri * 180 + j * 10}ms` }} />
                ))}
                <em className="mv-mean" style={{ left: pct(r.mean - ref.mean), animationDelay: `${ri * 180 + 650}ms` }} />
              </div>
              <span className="mv-val">{r.mean - ref.mean < 0 ? "−" : "+"}{Math.abs(r.mean - ref.mean).toFixed(1)} s</span>
            </div>
          ))}
        </div>
        <p className={`mv-verdict ${phase ? "show" : ""}`}>
          {bestIsPit
            ? <><b>{optionLabel(best.k)}</b> beats {refName} in <b>{wins} of {n}</b> futures, {(ref.mean - best.mean).toFixed(1)} s faster on average. PitWall pits.</>
            : <><b>{ref.k === "stay out" ? "Staying out" : optionLabel(ref.k)}</b> is best: every other choice is slower on average (next best: {optionLabel(best.k).toLowerCase()}, {(best.mean - ref.mean).toFixed(1)} s slower).</>}
        </p>
        {auto && <div className="mv-timer"><span style={{ animationDuration: `${AUTO_CLOSE_MS}ms` }} /></div>}
      </section>
    </div>
  );
}
