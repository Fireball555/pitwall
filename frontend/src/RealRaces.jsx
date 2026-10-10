import { useEffect, useMemo, useRef, useState } from "react";
import { CartesianGrid, Line, LineChart, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { api } from "./api.js";
import { strip, Thinking } from "./CarCard.jsx";
import Circuit from "./Circuit.jsx";
import Multiverse from "./Multiverse.jsx";
import StartLights from "./StartLights.jsx";
import { CARS, TRACK_NAMES, TYRES } from "./theme.js";
import Timeline from "./Timeline.jsx";
import { useRaceClock } from "./useRaceClock.js";

const RACES = Object.fromEntries(Object.entries(TRACK_NAMES).filter(([id]) => id !== "zandvoort"));
const OURS = CARS.rollout.colour;
const GHOST = "#eaf1f8";
const FLAG = { GREEN: "Green flag", SC: "Safety car", VSC: "Virtual safety car" };

export default function RealRaces() {
  const [track, setTrack] = useState("bahrain");
  const [drivers, setDrivers] = useState(null);
  const [driver, setDriver] = useState(null);
  const [rep, setRep] = useState(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState(null);

  // Only the newest request may update the screen: clicking quickly between races and drivers
  // must never show one driver's replay under another driver's name.
  const latest = useRef(0);
  const pickTrack = (t) => { if (t !== track) { setDriver(null); setDrivers(null); setRep(null); setTrack(t); } };
  useEffect(() => {
    setErr(null);
    let live = true;
    api.drivers(track).then((d) => { if (live) { setDrivers(d); setDriver(d.drivers[0]); } }).catch((e) => live && setErr(e.message));
    return () => { live = false; };
  }, [track]);
  useEffect(() => {
    if (!driver || !drivers?.drivers.includes(driver) || drivers.track !== track) return;
    const id = ++latest.current;
    setBusy(true); setErr(null);
    api.replay(track, driver)
      .then((r) => { if (id === latest.current) setRep(r); })
      .catch((e) => { if (id === latest.current) setErr(e.message); })
      .finally(() => { if (id === latest.current) setBusy(false); });
  }, [track, driver, drivers]);

  const clock = useRaceClock(rep?.laps.length ?? 1, rep ? `${rep.track}${rep.driver}` : "", null, false);

  return (
    <div className="real2">
      <div className="real-head">
        <div>
          <h2>What if PitWall had been on the pit wall?</h2>
          <p className="help">A real 2023 race. The other 19 cars drive their real lap times; PitWall takes one driver's car and pace and makes its own pit calls. Safety cars and rain happen when they really did.</p>
        </div>
        <div className="real-pick">
          <div className="field">
            <span className="field-label">Race</span>
            <div className="seg2" role="group" aria-label="Race">
              {Object.entries(RACES).map(([id, n]) => (
                <button key={id} className={track === id ? "on" : ""} aria-pressed={track === id} onClick={() => pickTrack(id)}>{n} 2023</button>
              ))}
            </div>
          </div>
          <div className="field">
            <span className="field-label">PitWall replaces</span>
            <div className="seg2" role="group" aria-label="Driver">
              {drivers?.drivers.map((d) => (
                <button key={d} className={driver === d ? "on" : ""} aria-pressed={driver === d} onClick={() => setDriver(d)}>
                  {d}{drivers.grid?.[d] ? <small> P{drivers.grid[d]}</small> : null}
                </button>
              ))}
            </div>
          </div>
        </div>
      </div>
      {drivers && !drivers.is_real && <div className="notice">Synthetic race: the real 2023 data hasn't been downloaded yet (<code>python -m pitwall.data.build --track {track}</code>).</div>}
      {err && <p className="error">{err}</p>}
      {busy && <p className="help">Replaying the race with PitWall in the car…</p>}
      {rep && !busy && <Replay rep={rep} clock={clock} />}
    </div>
  );
}

function Replay({ rep, clock }) {
  const { lap, frac } = clock;
  const done = clock.finished;
  const [lights, setLights] = useState(false);
  const [mv, setMv] = useState(null);
  const shown = useRef(new Set());
  useEffect(() => { shown.current = new Set(); }, [rep]);
  // pause at each of PitWall's pit calls and show the futures it imagined
  useEffect(() => {
    if (!clock.playing || lap < 2) return;
    const d = rep.ours[lap - 1];
    if (d?.reason && d.samples && !shown.current.has(lap)) {
      shown.current.add(lap);
      clock.pause();
      setMv({ lap, decision: d, auto: true });
    }
  }, [lap, clock.playing, rep]); // eslint-disable-line react-hooks/exhaustive-deps
  const n = rep.laps.length;
  const i = lap - 1;
  const atGrid = clock.t === 0 && !clock.playing;
  const real = rep.real_driver;
  const ref = rep.sanity?.real_strategy_pos;
  const gained = ref != null && rep.our_finish_pos != null ? ref - rep.our_finish_pos : null;
  const ourPos = atGrid ? rep.grid.OURS : rep.laps[i].order.indexOf("OURS") + 1;
  const realPos = atGrid ? rep.real_grid : rep.real_driver[i]?.position;
  const posDelta = ourPos && realPos ? realPos - ourPos : 0;
  const st = rep.status[i], prevSt = rep.status[i - 1];
  const banner = st === "SC" ? ["sc", "Safety car"] : st === "VSC" ? ["vsc", "Virtual safety car"]
    : prevSt && prevSt !== "GREEN" ? ["clear", "Track clear"] : rep.wetness[i] > 0.2 ? ["rain vsc", "Wet track"] : null;

  return (
    <>
      <div className="verdicts">
        <Tile big={done ? `P${rep.real_finish_pos ?? "–"}` : "P?"} hidden={!done} reveal={done} delay={0}
          label={`${rep.driver} for real`} sub={`started P${rep.real_grid}`} />
        <Tile big={done ? `P${ref ?? "–"}` : "P?"} hidden={!done} reveal={done} delay={400}
          label="his real stops, our simulator" sub="the fair comparison: same model for both" />
        <Tile ours big={done ? `P${rep.our_finish_pos ?? "–"}` : "P?"} hidden={!done} reveal={done} delay={800}
          label="PitWall's own pit calls"
          sub={done ? <span className={`stamp ${gained > 0 ? "" : "neutral"}`} style={{ animationDelay: "1.4s" }}>
            {gained > 0 ? `+${gained} place${gained === 1 ? "" : "s"} vs his stops` : gained === 0 ? "same place as his stops" : `${-gained} place${gained === -1 ? "" : "s"} lost`}</span>
            : <button className="linkish" onClick={() => clock.seek(n + 1)}>Skip to the flag</button>} />
      </div>

      <div className="real-stage">
        <div className="center">
          {done && <div className="chequer" key={rep.driver} />}
          {!atGrid && banner && <div key={banner[0]} className={`banner ${banner[0]}`}><span>{banner[1]}</span></div>}
          <div className="center-top">
            <div className="lap-big">{atGrid ? <><span className="lap-word">On the</span><b>Grid</b></> : <><span className="lap-word">Lap</span><b>{lap}</b><small>/{n}</small></>}</div>
            <p className="race-sub">{TRACK_NAMES[rep.track]} Grand Prix 2023<br />PitWall in {rep.driver}'s car</p>
            <div className="delta">
              <span className="label"><span className="tag" style={{ "--car": OURS }}>PWL</span> vs <span className="tag" style={{ "--car": GHOST }}>{rep.driver}</span></span>
              <div className={`delta-val ${posDelta > 0 ? "ahead" : ""}`}>{atGrid ? "—" : posDelta > 0 ? `+${posDelta}` : posDelta}</div>
              <div className="delta-sub">{atGrid ? "places vs the real race" : posDelta > 0 ? "places ahead of the real race" : posDelta < 0 ? "places behind the real race" : "same place as the real race"}</div>
            </div>
          </div>
          <RaceMap rep={rep} i={i} frac={atGrid ? 0 : frac} atGrid={atGrid} />
          <p className="map-legend">
            <span><i className="dot" style={{ background: OURS }} />PitWall in {rep.driver}'s car</span>
            <span><i className="dot ring" />{rep.driver} for real</span>
            <span><i className="dot" style={{ background: "#6b6e78" }} />the other 19 cars (the two around PitWall are labelled)</span>
          </p>
        </div>
        <Tower rep={rep} i={i} atGrid={atGrid} />
      </div>

      <div className="real-bottom">
        <Calls rep={rep} lap={lap} />
        <div className="panel">
          <h3>Tyre plans</h3>
          <p className="help">Each block is one set of tyres. The white line is now.</p>
          <Stints label="PitWall" colour={OURS} comps={rep.ours.map((o) => o.compound)} pits={rep.ours.map((o, k) => k > 0 && o.pitted)} lap={lap} n={n} />
          <Stints label={`${rep.driver} for real`} colour={GHOST} comps={real.map((r) => r.compound)} pits={real.map((r, k) => k > 0 && r.pitted)} lap={lap} n={n} />
          <p className="legend">{Object.entries(TYRES).map(([t, col]) => <span key={t}><i style={{ background: col }} />{t.toLowerCase()}</span>)}</p>
        </div>
        <Positions rep={rep} lap={lap} />
      </div>

      {lights && <StartLights onDone={() => { setLights(false); clock.play(); }} />}
      {mv && <Multiverse lap={mv.lap} decision={mv.decision} auto={mv.auto} onClose={() => { setMv(null); clock.play(); }} />}
      <Timeline laps={n} status={rep.status} wetness={rep.wetness} clock={clock} startLabel="Lights out" onStart={() => setLights(true)}
        stops={[
          { laps: rep.ours.filter((o, k) => k > 0 && o.pitted).map((o) => o.lap), colour: OURS, label: "PitWall stop" },
          { laps: real.filter((r, k) => k > 0 && r.pitted).map((r) => r.lap), colour: GHOST, label: `${rep.driver} real stop` },
        ]} />
    </>
  );
}

function Tile({ big, label, sub, ours, hidden, reveal, delay }) {
  return (
    <div className={`vtile ${ours ? "ours" : ""} ${hidden ? "hidden" : ""} ${reveal ? "reveal" : ""}`} style={reveal ? { animationDelay: `${delay}ms` } : undefined}>
      <div className="vtile-big">{big}</div>
      <div><div className="vtile-label">{label}</div><div className="vtile-sub">{sub}</div></div>
    </div>
  );
}

// Gap behind the leader (in laps) for every car at the end of lap index k; grid spacing before lap 1.
function gapsAt(rep, k) {
  if (k < 0) {
    const out = {};
    Object.entries(rep.grid).forEach(([d, g]) => { if (d !== rep.driver) out[d] = (g - 1) * 0.0022; });
    return out;
  }
  const L = rep.laps[k];
  const lead = L.elapsed[L.order[0]];
  const lapS = rep.lap_ref[k] || 90;
  const out = {};
  L.order.forEach((d) => { out[d] = (L.elapsed[d] - lead) / lapS; });
  if (rep.ghost[k] != null) out.__ghost = (rep.ghost[k] - lead) / lapS;
  return out;
}

function RaceMap({ rep, i, frac, atGrid }) {
  const prev = useMemo(() => gapsAt(rep, i - 1), [rep, i]);
  const cur = useMemo(() => gapsAt(rep, atGrid ? -1 : i), [rep, i, atGrid]);
  const order = atGrid ? null : rep.laps[i].order;
  const me = order ? order.indexOf("OURS") : -1;
  const nearby = order ? new Set([order[me - 1], order[me + 1]]) : new Set();
  const markers = [];
  Object.keys(cur).forEach((d) => {
    if (prev[d] == null && !atGrid) return;
    const g = atGrid ? cur[d] : prev[d] + (cur[d] - prev[d]) * frac;
    const f = (atGrid ? -0.003 : frac) - g;
    if (d === "__ghost") markers.push({ id: d, f, colour: GHOST, r: 21, shape: "ring", tag: `${rep.driver} real`, title: `${rep.driver}, what really happened` });
    else if (d === "OURS") markers.push({ id: d, f, colour: OURS, r: 22, shape: "circle", ours: true, tag: "PWL", title: `PitWall in ${rep.driver}'s car` });
    else markers.push({ id: d, f, colour: nearby.has(d) ? "#c9c6bd" : "#6b6e78", r: 13, shape: "dot", tag: nearby.has(d) ? d : undefined, title: d });
  });
  return <Circuit track={rep.track} markers={markers} wet={atGrid ? 0 : rep.wetness[i]} sc={!atGrid && rep.status[i] !== "GREEN"} className="map-real" />;
}

// The running order, F1 timing-tower style, with the real driver's actual place as a ghost row.
function Tower({ rep, i, atGrid }) {
  const L = rep.laps[i], P = rep.laps[i - 1];
  let rows;
  if (atGrid) {
    rows = Object.entries(rep.grid).filter(([d]) => d !== rep.driver).sort((a, b) => a[1] - b[1]).map(([d]) => ({ d }));
  } else {
    const lead = L.elapsed[L.order[0]], lapS = rep.lap_ref[i] || 90;
    rows = L.order.map((d, k) => {
      const gap = L.elapsed[d] - lead;
      const down = Math.floor(gap / lapS);
      const before = P ? P.order.indexOf(d) : k;
      return { d, gap: k === 0 ? "Leader" : down >= 1 ? `+${down} lap${down > 1 ? "s" : ""}` : `+${gap.toFixed(1)}`, move: before - k };
    });
    const realPos = rep.real_driver[i]?.position;
    if (realPos) rows.splice(Math.min(rows.length, realPos - 1), 0, { d: "__ghost" });
  }
  const tyre = (d) => (d === "OURS" ? rep.ours[i]?.compound : d === "__ghost" ? rep.real_driver[i]?.compound : rep.tyres[d]?.[i]);
  const pitting = (d) => !atGrid && i > 0 && (d === "OURS" ? rep.ours[i]?.pitted : d === "__ghost" ? rep.real_driver[i]?.pitted : rep.pits[d]?.includes(i + 1));
  let pos = 0;
  return (
    <div className="tower2" aria-live="off">
      <div className="tower2-head"><span className="label">{atGrid ? "Starting grid" : "Running order"}</span><span className="label">{atGrid ? "" : "gap"}</span></div>
      <ol>
        {rows.map((r) => {
          const ghost = r.d === "__ghost";
          if (!ghost) pos += 1;
          const c = tyre(r.d);
          return (
            <li key={r.d} className={`${r.d === "OURS" ? "ours" : ""} ${ghost ? "ghost" : ""}`}>
              <span className="tpos">{ghost ? rep.real_driver[i].position : pos}</span>
              <span className={`tmove ${r.move > 0 ? "up" : r.move < 0 ? "down" : ""}`}>{r.move > 0 ? `▲${r.move}` : r.move < 0 ? `▼${-r.move}` : ""}</span>
              <span className="tname">{r.d === "OURS" ? <>PitWall <small>{rep.driver}'s car</small></> : ghost ? <>{rep.driver} <small>for real</small></> : r.d}</span>
              <span className="tpit">{pitting(r.d) ? "PIT" : ""}</span>
              {c ? <span className="ttyre" style={{ borderColor: TYRES[c] }} title={c}>{c[0]}</span> : <span />}
              <span className="tgap">{ghost ? "" : r.gap ?? ""}</span>
            </li>
          );
        })}
      </ol>
    </div>
  );
}

function Calls({ rep, lap }) {
  const calls = rep.ours.filter((o) => o.reason && o.lap > 1);
  const now = rep.ours[lap - 1];
  return (
    <div className="panel calls">
      <h3>PitWall's calls</h3>
      <ul className="callfeed">
        {calls.length === 0 && <li className="future">No stops yet</li>}
        {calls.map((o) => (
          <li key={o.lap} className={o.lap <= lap ? (calls.filter((c) => c.lap <= lap).slice(-1)[0] === o ? "now" : "") : "future"}>
            <b>Lap {o.lap}</b> {strip(o.reason)}
          </li>
        ))}
      </ul>
      {now?.options && Object.keys(now.options).length > 1 && <Thinking d={now} max={3} />}
    </div>
  );
}

function Stints({ label, colour, comps, pits, lap, n }) {
  const stints = [];
  comps.forEach((t, k) => {
    if (k === 0 || pits[k] || t !== comps[k - 1]) stints.push({ t, start: k, len: 1 });
    else stints[stints.length - 1].len += 1;
  });
  return (
    <div className="stint-row">
      <span className="stint-name"><i style={{ background: colour }} />{label}</span>
      <div className="stint-track">
        {stints.map((s, k) => (
          <span key={k} className="stint" title={`${s.t}, laps ${s.start + 1}–${s.start + s.len}`}
            style={{ left: `${(100 * s.start) / n}%`, width: `${(100 * s.len) / n}%`, background: TYRES[s.t] ?? "#475569" }}>
            {s.len > 5 ? s.t?.[0] : ""}
          </span>
        ))}
        <span className="cursor" style={{ left: `${(100 * lap) / n}%` }} />
      </div>
    </div>
  );
}

function Positions({ rep, lap }) {
  const rows = useMemo(() => rep.laps.map((L, k) => ({
    lap: k + 1, ours: L.order.indexOf("OURS") + 1, real: rep.real_driver[k]?.position ?? null,
  })), [rep]);
  return (
    <div className="panel">
      <h3>Position, lap by lap</h3>
      <p className="help">Up is better. Cyan: PitWall. Dashed: {rep.driver} for real.</p>
      <ResponsiveContainer width="100%" height={190}>
        <LineChart data={rows} margin={{ top: 6, right: 10, bottom: 0, left: -18 }}>
          <CartesianGrid stroke="#213654" strokeDasharray="2 4" />
          <XAxis dataKey="lap" type="number" domain={[1, rows.length]} stroke="#8aa0bb" tickCount={6} />
          <YAxis reversed domain={[1, 20]} stroke="#8aa0bb" ticks={[1, 5, 10, 15, 20]} />
          <Tooltip contentStyle={{ background: "#13233a", border: "1px solid #213654" }} labelFormatter={(l) => `Lap ${l}`}
            formatter={(v, k) => [`P${v}`, k === "ours" ? "PitWall" : `${rep.driver} for real`]} />
          <ReferenceLine x={lap} stroke="#eaf1f8" strokeOpacity={0.5} />
          <Line dataKey="real" stroke={GHOST} strokeDasharray="5 4" strokeWidth={2} dot={false} isAnimationActive={false} />
          <Line dataKey="ours" stroke={OURS} strokeWidth={3} dot={false} isAnimationActive={false} />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
