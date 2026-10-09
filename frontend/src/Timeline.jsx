// Play/pause, a lap scrubber that shows safety cars and rain as bands and pit stops as ticks,
// and the playback speed. stops: [{ laps: [lap numbers], colour, label }].
export default function Timeline({ laps, status, wetness, stops = [], clock, startLabel = "Play" }) {
  const n = laps;
  const marks = [];
  status.forEach((s, k) => { if (s !== "GREEN") marks.push({ k, cls: s.toLowerCase() }); });
  wetness.forEach((w, k) => { if (w > 0.2) marks.push({ k, cls: "rain" }); });
  return (
    <div className="timeline">
      {clock.playing
        ? <button className="btn" onClick={clock.pause}>Pause</button>
        : <button className="btn primary" onClick={clock.play}>{clock.finished ? "Watch again" : clock.t === 0 ? startLabel : "Play"}</button>}
      <div className="scrub">
        <div className="scrub-bands" aria-hidden="true">
          {marks.map((m, k) => <span key={k} className={m.cls} style={{ left: `${(100 * m.k) / n}%`, width: `${100 / n}%` }} />)}
          {stops.flatMap((s, j) => s.laps.map((l) => (
            <i key={`${j}-${l}`} className={j ? "low" : ""} style={{ left: `${(100 * (l - 0.5)) / n}%`, background: s.colour }} title={`${s.label}: lap ${l}`} />
          )))}
        </div>
        <input type="range" min={1} max={n} step={1} value={clock.lap} aria-label="Lap" onChange={(e) => clock.seek(+e.target.value)} />
      </div>
      <div className="seg2" role="group" aria-label="Speed">
        {[1, 2, 5].map((s) => (
          <button key={s} className={clock.secPerLap === s ? "on" : ""} aria-pressed={clock.secPerLap === s} onClick={() => clock.setSecPerLap(s)}>{s} s/lap</button>
        ))}
      </div>
    </div>
  );
}
