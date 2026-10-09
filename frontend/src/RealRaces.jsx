import { useEffect, useMemo, useState } from "react";
import { CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { api } from "./api.js";
import Playback from "./Playback.jsx";
import { CARS, TRACK_NAMES, TYRES } from "./theme.js";
import { usePlayback } from "./usePlayback.js";

// Compare with the same car on its real pit stops inside our simulator, so model error cancels out.
function gainText(rep) {
  const ref = rep.sanity?.real_strategy_pos ?? rep.real_finish_pos;
  const d = ref - rep.our_finish_pos;
  if (d === 0) return `same place as his real pit stops (P${ref}) in our simulator`;
  return `${Math.abs(d)} place${Math.abs(d) === 1 ? "" : "s"} ${d > 0 ? "gained" : "lost"} vs his real pit stops (P${ref}) in our simulator`;
}

export default function RealRaces() {
  const [track, setTrack] = useState("bahrain");
  const [drivers, setDrivers] = useState(null);
  const [driver, setDriver] = useState(null);
  const [rep, setRep] = useState(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState(null);

  useEffect(() => {
    setDrivers(null); setRep(null);
    api.drivers(track).then((d) => { setDrivers(d); setDriver(d.drivers[0]); }).catch((e) => setErr(e.message));
  }, [track]);
  useEffect(() => {
    if (!driver) return;
    setBusy(true); setErr(null);
    api.replay(track, driver).then(setRep).catch((e) => setErr(e.message)).finally(() => setBusy(false));
  }, [track, driver]);

  const laps = rep?.laps.length ?? 1;
  const pb = usePlayback(laps, rep ? `${rep.track}${rep.driver}` : "");

  return (
    <div className="real">
      <div className="toolbar">
        <h2>What if PitWall had been on the pit wall?</h2>
        <p className="help">Zandvoort 2023 is left out: its 40-minute red flag isn't something our simulator models. The other 19 cars drive their real lap times. Our car takes one real driver's place and pace, and makes its own pit calls. Safety cars and rain happen when they really did.</p>
        <div className="row">
          {Object.entries(TRACK_NAMES).filter(([id]) => id !== "zandvoort").map(([id, n]) => (
            <button key={id} className={`chip ${track === id ? "on" : ""}`} onClick={() => setTrack(id)}>{n} 2023</button>
          ))}
          <span className="sep" />
          <label className="inline">Replace
            <select value={driver ?? ""} onChange={(e) => setDriver(e.target.value)}>
              {drivers?.drivers.map((d) => <option key={d}>{d}</option>)}
            </select>
          </label>
        </div>
      </div>
      {drivers && !drivers.is_real && (
        <div className="notice">This is a synthetic race made by our own engine. The real 2023 data hasn't been downloaded yet: <code>python -m pitwall.data.build --track {track}</code></div>
      )}
      {err && <p className="error">{err}</p>}
      {busy && <p className="help">Replaying the race…</p>}
      {rep && !busy && (
        <>
          <div className="stats">
            <div className="stat"><div className="stat-value">P{rep.real_finish_pos}</div><div className="stat-label">where {rep.driver} really finished</div><div className="stat-sub">started P{rep.real_grid}</div></div>
            <div className="stat ours"><div className="stat-value">P{rep.our_finish_pos}</div><div className="stat-label">with PitWall making the calls</div><div className="stat-sub">{gainText(rep)}</div></div>
            <div className="stat"><div className="stat-value">P{rep.sanity?.real_strategy_pos ?? "–"}</div><div className="stat-label">sanity check: his real pit stops in our simulator</div><div className="stat-sub">this is the fair comparison for PitWall's result; close to P{rep.real_finish_pos} means the replay is trustworthy</div></div>
          </div>
          <div className="panel">
            <h3>Positions lap by lap</h3>
            <p className="help">Thick cyan: PitWall in {rep.driver}'s car. Dashed: what {rep.driver} really did. Grey: everyone else.</p>
            <PositionChart rep={rep} lap={pb.lap} />
            <Playback pb={pb} max={laps} />
          </div>
          <div className="two">
            <Stops title="PitWall's pit calls" rows={rep.ours.filter((r) => r.pitted || r.lap === 1).map((r) => ({ lap: r.lap, tyre: r.compound, why: r.reason }))} />
            <Stops title={`What ${rep.driver} really did`} rows={rep.real_driver.filter((r) => r.pitted || r.lap === 1).map((r) => ({ lap: r.lap, tyre: r.compound }))} />
          </div>
          <p className="help">Limits: the recorded cars can't react to ours, and the traffic rule (stuck within one second unless clearly faster) is a simplification.</p>
        </>
      )}
    </div>
  );
}

function PositionChart({ rep, lap }) {
  const { rows, names } = useMemo(() => {
    const names = [...new Set(rep.laps.flatMap((l) => l.order))].filter((n) => n !== "OURS");
    const real = Object.fromEntries(rep.real_driver.map((r) => [r.lap, r.position]));
    const rows = rep.laps.map((l) => {
      const r = { lap: l.lap, OURS: l.order.indexOf("OURS") + 1, REAL: real[l.lap] ?? null };
      names.forEach((n) => { const i = l.order.indexOf(n); r[n] = i >= 0 ? i + 1 : null; });
      return r;
    });
    return { rows, names };
  }, [rep]);
  const shown = rows.map((r) => (r.lap <= lap ? r : { lap: r.lap }));
  return (
    <ResponsiveContainer width="100%" height={460}>
      <LineChart data={shown} margin={{ top: 8, right: 16, left: 0, bottom: 0 }}>
        <CartesianGrid stroke="#27476b" strokeDasharray="2 4" />
        <XAxis dataKey="lap" type="number" domain={[1, rows.length]} stroke="#93a9c2" />
        <YAxis reversed domain={[1, 20]} ticks={[1, 5, 10, 15, 20]} stroke="#93a9c2" width={32} />
        <Tooltip contentStyle={{ background: "#17304d", border: "1px solid #27476b" }} labelFormatter={(l) => `Lap ${l}`}
          formatter={(v, n) => [`P${v}`, n === "OURS" ? "PitWall" : n === "REAL" ? `${rep.driver} (real)` : n]}
          itemSorter={(i) => (i.dataKey === "OURS" ? -1 : i.dataKey === "REAL" ? 0 : 1)} />
        {names.map((n) => <Line key={n} dataKey={n} stroke="#5b7290" strokeWidth={1} dot={false} isAnimationActive={false} />)}
        <Line dataKey="REAL" stroke={CARS.rollout.colour} strokeDasharray="6 4" strokeWidth={2} dot={false} isAnimationActive={false} />
        <Line dataKey="OURS" stroke={CARS.rollout.colour} strokeWidth={4} dot={false} isAnimationActive={false} />
      </LineChart>
    </ResponsiveContainer>
  );
}

function Stops({ title, rows }) {
  return (
    <div className="panel">
      <h3>{title}</h3>
      <table className="stops">
        <thead><tr><th>Lap</th><th>Tyre</th>{rows.some((r) => r.why) && <th>Why</th>}</tr></thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.lap}><td>{r.lap}</td><td><span className="tyre-dot" style={{ background: TYRES[r.tyre] }} />{r.tyre.toLowerCase()}</td>{r.why !== undefined && <td>{r.why}</td>}</tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
