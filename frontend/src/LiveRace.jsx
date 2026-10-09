import { useEffect, useMemo, useState } from "react";
import { CartesianGrid, Line, LineChart, ReferenceArea, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { api } from "./api.js";
import Playback from "./Playback.jsx";
import TimingTower from "./TimingTower.jsx";
import { CARS, ORDER, TRACK_NAMES, TYRES, fmtTime, signed } from "./theme.js";
import { usePlayback } from "./usePlayback.js";

export default function LiveRace() {
  const [form, setForm] = useState({ track: "bahrain", mode: "f1", seed: 7, rainOn: false, rain: 0.5, sc: 1, n: 100 });
  const [data, setData] = useState(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState(null);
  const [picked, setPicked] = useState(null);

  const run = (f = form) => {
    setBusy(true); setErr(null);
    api.race({ track: f.track, mode: f.mode, seed: f.seed, rain: f.rainOn ? f.rain : null, sc: f.sc, n: f.n })
      .then((d) => { setData(d); setPicked(null); })
      .catch((e) => setErr(e.message))
      .finally(() => setBusy(false));
  };
  useEffect(() => { run(); }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const set = (k) => (e) => setForm({ ...form, [k]: e.target.type === "checkbox" ? e.target.checked : e.target.type === "range" || e.target.type === "number" ? +e.target.value : e.target.value });
  const randomRace = () => { const f = { ...form, seed: Math.floor(Math.random() * 99999) }; setForm(f); run(f); };

  const pb = usePlayback(data?.laps ?? 1, data ? `${data.track}${data.mode}${data.seed}` : "");

  return (
    <div className="live">
      <aside className="panel controls">
        <h2>Race setup</h2>
        <label>Track
          <select value={form.track} onChange={set("track")}>
            {Object.entries(TRACK_NAMES).map(([id, n]) => <option key={id} value={id}>{n}</option>)}
          </select>
        </label>
        <fieldset className="seg">
          <legend>Rules</legend>
          <button className={form.mode === "f1" ? "on" : ""} onClick={() => setForm({ ...form, mode: "f1" })}>F1</button>
          <button className={form.mode === "endurance" ? "on" : ""} onClick={() => setForm({ ...form, mode: "endurance" })}>Endurance</button>
        </fieldset>
        <p className="help">{form.mode === "f1" ? "2023 F1 rules: no refuelling, two dry compounds required." : "Small fuel tank: every stop also decides how much fuel to take."}</p>
        <label>Race number (same number, same race)
          <input type="number" min={0} max={99999} value={form.seed} onChange={set("seed")} />
        </label>
        <label className="check"><input type="checkbox" checked={form.rainOn} onChange={set("rainOn")} /> Set the chance of rain myself</label>
        {form.rainOn && <label>Chance of rain: {Math.round(form.rain * 100)}%
          <input type="range" min={0} max={1} step={0.05} value={form.rain} onChange={set("rain")} /></label>}
        <label>Safety cars: {form.sc}× the track's normal rate
          <input type="range" min={0} max={4} step={0.5} value={form.sc} onChange={set("sc")} /></label>
        <div className="row">
          <button className="btn primary" disabled={busy} onClick={() => run()}>{busy ? "Racing…" : "Run race"}</button>
          <button className="btn" disabled={busy} onClick={randomRace}>Random race</button>
        </div>
        {busy && <p className="help">Our strategist is imagining {form.n} futures for every option, every lap.</p>}
        {err && <p className="error">{err}</p>}
      </aside>

      {data && (
        <section className="race">
          <Result data={data} />
          <div className="race-grid">
            <div className="panel">
              <h3>Seconds gained on the Pirelli-plan car</h3>
              <p className="help">Up means faster. Shaded laps: amber = safety car, blue = rain. Dots are pit stops.</p>
              <GainChart data={data} lap={pb.lap} />
              <Playback pb={pb} max={data.laps} />
            </div>
            <TimingTower data={data} lap={pb.lap} />
          </div>
          <TyreStrip data={data} lap={pb.lap} />
          <Decisions data={data} lap={pb.lap} picked={picked} setPicked={setPicked} />
        </section>
      )}
    </div>
  );
}

function Result({ data }) {
  const f = data.finish;
  const gain = f.rollout != null && f.pirelli != null ? f.pirelli - f.rollout : null;
  return (
    <div className="result">
      <div>
        <h2>{TRACK_NAMES[data.track]}, race {data.seed}</h2>
        <p className="help">{data.laps} laps · {data.mode === "f1" ? "F1 rules" : "Endurance rules"} · {data.tag} race</p>
      </div>
      <div className="verdict">
        {gain == null ? "One car did not finish" : gain >= 0
          ? <>PitWall beat the Pirelli plan by <strong>{gain.toFixed(1)} s</strong></>
          : <>The Pirelli plan beat PitWall by <strong>{(-gain).toFixed(1)} s</strong> this time</>}
      </div>
      <table className="finish">
        <tbody>
          {ORDER.slice().sort((a, b) => (f[a] ?? 1e12) - (f[b] ?? 1e12)).map((c) => (
            <tr key={c}><td><span className="swatch" style={{ background: CARS[c].colour }} />{CARS[c].label}</td><td>{fmtTime(f[c])}</td></tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function GainChart({ data, lap }) {
  const rows = useMemo(() => Array.from({ length: data.laps }, (_, i) => {
    const r = { lap: i + 1 };
    for (const c of ORDER) r[c] = data.cars[c]?.total[i] != null && data.cars.pirelli.total[i] != null ? data.cars.pirelli.total[i] - data.cars[c].total[i] : null;
    return r;
  }), [data]);
  const shown = rows.map((r) => (r.lap <= lap ? r : { lap: r.lap }));
  const bands = useMemo(() => {
    const out = [];
    data.status.forEach((s, i) => { if (s !== "GREEN") out.push({ x: i + 1, kind: s }); });
    data.wetness.forEach((w, i) => { if (w > 0.2) out.push({ x: i + 1, kind: "RAIN" }); });
    return out;
  }, [data]);
  const Dot = (car) => (p) => (p.payload.lap <= lap && data.cars[car].pitted[p.payload.lap - 1]
    ? <circle key={`${car}${p.index}`} cx={p.cx} cy={p.cy} r={5} fill={CARS[car].colour} stroke="#0e2036" strokeWidth={2} />
    : null);
  return (
    <ResponsiveContainer width="100%" height={330}>
      <LineChart data={shown} margin={{ top: 8, right: 16, bottom: 4, left: 0 }}>
        <CartesianGrid stroke="#27476b" strokeDasharray="2 4" />
        {bands.map((b, k) => (
          <ReferenceArea key={k} x1={b.x - 0.5} x2={b.x + 0.5} ifOverflow="hidden"
            fill={b.kind === "RAIN" ? "#3b82f6" : b.kind === "SC" ? "#f59e0b" : "#fcd34d"} fillOpacity={b.kind === "RAIN" ? 0.18 : 0.22} />
        ))}
        <XAxis dataKey="lap" type="number" domain={[1, data.laps]} stroke="#93a9c2" tickCount={8} />
        <YAxis stroke="#93a9c2" width={44} />
        <ReferenceLine y={0} stroke="#93a9c2" />
        <Tooltip contentStyle={{ background: "#17304d", border: "1px solid #27476b" }} labelFormatter={(l) => `Lap ${l}`}
          formatter={(v, name) => [`${signed(v)} s`, CARS[name]?.label ?? name]} />
        {ORDER.map((c) => (
          <Line key={c} dataKey={c} isAnimationActive={false} connectNulls={false} stroke={CARS[c].colour}
            strokeWidth={c === "rollout" ? 4 : 2} strokeDasharray={c === "oracle" ? "6 4" : undefined} dot={Dot(c)} />
        ))}
      </LineChart>
    </ResponsiveContainer>
  );
}

function TyreStrip({ data, lap }) {
  return (
    <div className="panel">
      <h3>Tyre strategy</h3>
      <div className="strip">
        {ORDER.map((c) => {
          const comp = data.cars[c].compound, pit = data.cars[c].pitted;
          const stints = [];
          comp.forEach((t, i) => {
            if (i === 0 || pit[i] || t !== comp[i - 1]) stints.push({ t, start: i, len: 1 });
            else stints[stints.length - 1].len += 1;
          });
          return (
            <div className="strip-row" key={c}>
              <span className="strip-name"><span className="swatch" style={{ background: CARS[c].colour }} />{CARS[c].label}</span>
              <div className="strip-track">
                {stints.map((s, k) => (
                  <span key={k} className="stint" title={`${s.t}, laps ${s.start + 1}–${s.start + s.len}`}
                    style={{ left: `${(100 * s.start) / data.laps}%`, width: `${(100 * s.len) / data.laps}%`, background: TYRES[s.t] }}>
                    {s.len > 4 ? s.t[0] : ""}
                  </span>
                ))}
                <span className="cursor" style={{ left: `${(100 * lap) / data.laps}%` }} />
              </div>
            </div>
          );
        })}
      </div>
      <p className="legend">{Object.entries(TYRES).map(([t, col]) => <span key={t}><i style={{ background: col }} />{t.toLowerCase()}</span>)}</p>
    </div>
  );
}

function Decisions({ data, lap, picked, setPicked }) {
  const ds = data.cars.rollout.decisions;
  const current = picked ?? [...ds].reverse().find((d) => d.lap <= lap) ?? ds[0];
  const opts = current ? Object.entries(current.options) : [];
  const best = opts.length ? Math.min(...opts.map(([, v]) => v)) : 0;
  const worst = opts.length ? Math.max(...opts.map(([, v]) => v)) : 1;
  return (
    <div className="decisions">
      <div className="panel">
        <h3>Why PitWall made each call</h3>
        <ul className="feed">
          {ds.map((d) => (
            <li key={d.lap} className={`${d.lap > lap ? "future" : ""} ${current === d ? "sel" : ""}`}>
              <button onClick={() => setPicked(d)}>{d.reason}</button>
            </li>
          ))}
        </ul>
      </div>
      <div className="panel">
        <h3>Options compared{current ? ` (${current.reason.split(":")[0]})` : ""}</h3>
        <p className="help">Average finish across the imagined futures, relative to the best option.</p>
        <div className="bars">
          {opts.sort((a, b) => a[1] - b[1]).map(([k, v]) => (
            <div className="bar-row" key={k}>
              <span className="bar-label">{k}</span>
              <span className="bar" style={{ width: `${Math.max(2, (100 * (v - best)) / Math.max(1, worst - best))}%`, background: v === best ? "#22d3ee" : "#3d5f86" }} />
              <span className="bar-val">{v === best ? "best" : `+${(v - best).toFixed(1)} s`}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
