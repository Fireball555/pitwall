import { useEffect, useState } from "react";
import { Bar, BarChart, CartesianGrid, Cell, Legend, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { api } from "./api.js";
import { CARS, TRACK_NAMES, signed } from "./theme.js";

const tip = { contentStyle: { background: "#17304d", border: "1px solid #27476b" } };

export default function Proof() {
  const [track, setTrack] = useState("bahrain");
  const [mode, setMode] = useState("f1");
  const [d, setD] = useState(null);
  const [err, setErr] = useState(null);
  useEffect(() => { setD(null); api.proof(track, mode).then(setD).catch((e) => setErr(e.message)); }, [track, mode]);

  return (
    <div className="proof">
      <div className="toolbar">
        <h2>Is it better, or just lucky?</h2>
        <p className="help">Every race is run with all four cars in identical weather, safety cars and lap noise, so each race is a fair head-to-head.</p>
        <div className="row">
          {Object.entries(TRACK_NAMES).map(([id, n]) => (
            <button key={id} className={`chip ${track === id ? "on" : ""}`} onClick={() => setTrack(id)}>{n}</button>
          ))}
          <span className="sep" />
          <button className={`chip ${mode === "f1" ? "on" : ""}`} onClick={() => setMode("f1")}>F1</button>
          <button className={`chip ${mode === "endurance" ? "on" : ""}`} onClick={() => setMode("endurance")}>Endurance</button>
        </div>
      </div>
      {err && <p className="error">{err}</p>}
      {d && !d.available && (
        <div className="panel empty">
          <h3>No results yet for {TRACK_NAMES[track]} ({mode === "f1" ? "F1" : "endurance"})</h3>
          <p>Run the test on the laptop with the most cores, then reload this page:</p>
          <pre>python -m pitwall.eval.batch --all --n 1000</pre>
        </div>
      )}
      {d?.available && d.main && <Results d={d} />}
    </div>
  );
}

function Results({ d }) {
  const m = d.main, gp = m.gain_vs.pirelli ?? [null, null, null];
  const tags = Object.entries(m.by_tag ?? {}).map(([tag, s]) => ({
    tag, pirelli: s.gain_vs.pirelli?.[0], rules: s.gain_vs.rules?.[0], n: s.n_races,
  }));
  return (
    <>
      <div className="stats">
        <Stat value={`${signed(gp[0])} s`} label="average time gained on the Pirelli plan" sub={`95% confidence: ${signed(gp[1])} to ${signed(gp[2])} s`} />
        <Stat value={`${Math.round(100 * (m.win_rate_vs.pirelli ?? 0))}%`} label="of races won against the Pirelli plan" sub={`against simple rules: ${Math.round(100 * (m.win_rate_vs.rules ?? 0))}%`} />
        <Stat value={m.oracle_share != null ? `${Math.round(100 * m.oracle_share)}%` : "–"} label="of the best possible gain captured" sub="the Oracle knows the future; this is how close we get" />
        <Stat value={m.n_races.toLocaleString()} label="races in this test" sub={d.accuracy ? `simulator error ${d.accuracy.mae_s} s per lap` : "simulator accuracy: not measured yet"} />
      </div>
      <div className="two">
        <div className="panel">
          <h3>Race by race: seconds gained on the Pirelli plan</h3>
          <p className="help">Each bar counts races. Right of zero, PitWall finished ahead.</p>
          <ResponsiveContainer width="100%" height={280}>
            <BarChart data={d.histogram} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
              <CartesianGrid stroke="#27476b" strokeDasharray="2 4" vertical={false} />
              <XAxis dataKey="from" stroke="#93a9c2" tickFormatter={(v) => v.toFixed(0)} />
              <YAxis stroke="#93a9c2" width={36} allowDecimals={false} />
              <Tooltip {...tip} labelFormatter={(v, p) => p?.[0] ? `${signed(p[0].payload.from)} to ${signed(p[0].payload.to)} s` : ""} formatter={(v) => [v, "races"]} />
              <Bar dataKey="count" isAnimationActive={false}>
                {d.histogram.map((h, i) => <Cell key={i} fill={h.to <= 0 ? "#64748b" : CARS.rollout.colour} />)}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
        <div className="panel">
          <h3>Average gain by type of race</h3>
          <p className="help">Dry: nothing happened. Chaotic: two or more safety cars. Wet: it rained.</p>
          <ResponsiveContainer width="100%" height={280}>
            <BarChart data={tags} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
              <CartesianGrid stroke="#27476b" strokeDasharray="2 4" vertical={false} />
              <XAxis dataKey="tag" stroke="#93a9c2" />
              <YAxis stroke="#93a9c2" width={36} />
              <Tooltip {...tip} formatter={(v, n) => [`${signed(v)} s`, `vs ${CARS[n].label}`]} />
              <Legend formatter={(n) => `vs ${CARS[n].label}`} />
              <Bar dataKey="pirelli" fill={CARS.pirelli.colour} isAnimationActive={false} />
              <Bar dataKey="rules" fill={CARS.rules.colour} isAnimationActive={false} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>
      <div className="two">
        <div className="panel">
          <h3>Fairness test: does it still win when its numbers are wrong?</h3>
          {d.mismatch ? (
            <p className="big-text">
              In {d.mismatch.n_races} races the real tyre wear, pit loss and fuel effect were secretly changed, while every car kept
              planning with the normal numbers. PitWall still gained <strong>{signed(d.mismatch.gain_vs.pirelli?.[0])} s</strong> on
              average and won <strong>{Math.round(100 * (d.mismatch.win_rate_vs.pirelli ?? 0))}%</strong> of races.
            </p>
          ) : <p className="help">Not run for this track and mode. Command: <code>python -m pitwall.eval.batch --track {d.track} --test mismatch</code></p>}
          <h3>Where it doesn't help</h3>
          <p className="big-text">PitWall lost to the Pirelli plan in <strong>{d.losses}</strong> of {d.races} races{d.worst != null ? ` (worst by ${(-d.worst).toFixed(1)} s)` : ""}. These are mostly calm, dry races where the pre-race plan was already close to ideal.</p>
        </div>
        <div className="panel">
          <h3>More rain, bigger advantage</h3>
          {d.rain_sweep.length ? (
            <ResponsiveContainer width="100%" height={250}>
              <LineChart data={d.rain_sweep} margin={{ top: 8, right: 16, left: 0, bottom: 0 }}>
                <CartesianGrid stroke="#27476b" strokeDasharray="2 4" />
                <XAxis dataKey="rain_prob" stroke="#93a9c2" tickFormatter={(v) => `${Math.round(v * 100)}%`} />
                <YAxis stroke="#93a9c2" width={36} />
                <Tooltip {...tip} labelFormatter={(v) => `Chance of rain ${Math.round(v * 100)}%`} formatter={(v) => [`${signed(v)} s`, "gain on Pirelli plan"]} />
                <Line dataKey="gain_vs_pirelli" stroke={CARS.rollout.colour} strokeWidth={3} isAnimationActive={false} />
              </LineChart>
            </ResponsiveContainer>
          ) : <p className="help">Not run yet.</p>}
        </div>
      </div>
    </>
  );
}

function Stat({ value, label, sub }) {
  return <div className="stat"><div className="stat-value">{value}</div><div className="stat-label">{label}</div><div className="stat-sub">{sub}</div></div>;
}
