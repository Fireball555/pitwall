import { useEffect, useMemo, useRef, useState } from "react";
import { api } from "./api.js";
import CarCard from "./CarCard.jsx";
import { CARS, ORDER, TRACK_NAMES } from "./theme.js";
import Timeline from "./Timeline.jsx";
import TrackMap from "./TrackMap.jsx";
import { useRaceClock } from "./useRaceClock.js";

const FLAG = { GREEN: "Green flag", SC: "Safety car", VSC: "Virtual safety car" };
const WEATHER = { dry: { label: "Dry", rain: 0 }, usual: { label: "Usual", rain: null }, wet: { label: "Wet race", rain: 1 } };
const SAFETY = { none: { label: "None", sc: 0 }, usual: { label: "Usual", sc: 1 }, lots: { label: "Lots", sc: 3 } };
const newSeed = () => Math.floor(Math.random() * 99999);
// Rehearsed races (checked: same race number = exactly the same race on any machine).
const DEMOS = [
  { name: "Bahrain: safety cars", track: "bahrain", mode: "f1", weather: "usual", safety: "usual", seed: 5 },
  { name: "Bahrain: rain arrives", track: "bahrain", mode: "f1", weather: "wet", safety: "usual", seed: 8 },
  { name: "Zandvoort: dry race", track: "zandvoort", mode: "f1", weather: "usual", safety: "usual", seed: 3 },
  { name: "Zandvoort: rain and chaos", track: "zandvoort", mode: "f1", weather: "wet", safety: "usual", seed: 5 },
  { name: "Singapore: safety cars", track: "singapore", mode: "f1", weather: "usual", safety: "usual", seed: 9 },
  { name: "Bahrain: endurance, fuel calls", track: "bahrain", mode: "endurance", weather: "usual", safety: "usual", seed: 2 },
];

export default function LiveRace() {
  const [form, setForm] = useState({ track: "bahrain", mode: "f1", weather: "usual", safety: "usual", seed: 7 });
  const [events, setEvents] = useState({});           // forced during the race: rain_at, heavy, sc_at
  const [data, setData] = useState(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState(null);
  const [runId, setRunId] = useState(0);
  const resume = useRef(null);

  const run = (f, ev, resumeLap = null) => {
    setBusy(true); setErr(null);
    api.race({ track: f.track, mode: f.mode, seed: f.seed, rain: WEATHER[f.weather].rain, sc: SAFETY[f.safety].sc, ...ev })
      .then((d) => { resume.current = resumeLap; setData(d); setRunId((k) => k + 1); })
      .catch((e) => setErr(e.message)).finally(() => setBusy(false));
  };
  useEffect(() => { run(form, {}); }, []); // eslint-disable-line react-hooks/exhaustive-deps

  // any setting change starts that race straight away
  const change = (k, v) => { const f = { ...form, [k]: v }; setForm(f); setEvents({}); run(f, {}); };
  const newRace = () => change("seed", newSeed());
  const pickDemo = (k) => { const { name, ...f } = DEMOS[k]; setForm(f); setEvents({}); run(f, {}); };
  const clock = useRaceClock(data?.laps ?? 1, runId, resume.current);
  // "rain now" / "safety car now": rerun the same race with the event from the next lap, carry on watching
  const force = (ev) => {
    const lap = clock.lap;
    clock.pause();
    const e = { ...events, ...ev(lap) };
    setEvents(e);
    run(form, e, lap);
  };

  return (
    <div className="live2">
      <Setup form={form} change={change} busy={busy} newRace={newRace} pickDemo={pickDemo} />
      {err && <p className="error">{err}</p>}
      {busy && !data && <p className="help">Our strategist is imagining 100 futures for every option, every lap…</p>}
      {data && <Stage data={data} clock={clock} busy={busy} force={force} />}
    </div>
  );
}

function Seg({ label, value, options, onChange }) {
  return (
    <div className="field">
      <span className="field-label">{label}</span>
      <div className="seg2" role="group" aria-label={label}>
        {Object.entries(options).map(([k, o]) => (
          <button key={k} className={value === k ? "on" : ""} aria-pressed={value === k} onClick={() => onChange(k)}>{o.label ?? o}</button>
        ))}
      </div>
    </div>
  );
}

// Type a race number, then Enter (or click away) to run it.
function RaceNo({ seed, onSet }) {
  const [v, setV] = useState(String(seed));
  useEffect(() => setV(String(seed)), [seed]);
  const commit = () => { const n = parseInt(v, 10); if (Number.isFinite(n) && n !== seed) onSet(Math.max(0, n)); else setV(String(seed)); };
  return (
    <div className="field race-no">
      <span className="field-label">Race #</span>
      <input type="number" min={0} max={99999} value={v} aria-label="Race number"
        onChange={(e) => setV(e.target.value)} onBlur={commit} onKeyDown={(e) => e.key === "Enter" && commit()} />
    </div>
  );
}

function Setup({ form, change, busy, newRace, pickDemo }) {
  const demo = DEMOS.findIndex((d) => ["track", "mode", "weather", "safety", "seed"].every((k) => d[k] === form[k]));
  return (
    <div className="setup">
      <div className="field">
        <span className="field-label">Demo race</span>
        <select value={demo} onChange={(e) => pickDemo(+e.target.value)} aria-label="Demo race">
          <option value={-1} disabled>Choose…</option>
          {DEMOS.map((d, k) => <option key={k} value={k}>{d.name}</option>)}
        </select>
      </div>
      <div className="field">
        <span className="field-label">Track</span>
        <select value={form.track} onChange={(e) => change("track", e.target.value)} aria-label="Track">
          {Object.entries(TRACK_NAMES).map(([id, n]) => <option key={id} value={id}>{n}</option>)}
        </select>
      </div>
      <Seg label="Rules" value={form.mode} options={{ f1: "F1", endurance: "Endurance" }} onChange={(v) => change("mode", v)} />
      <Seg label="Weather" value={form.weather} options={WEATHER} onChange={(v) => change("weather", v)} />
      <Seg label="Safety cars" value={form.safety} options={SAFETY} onChange={(v) => change("safety", v)} />
      <RaceNo seed={form.seed} onSet={(v) => change("seed", v)} />
      <button className="btn primary new-race" disabled={busy} onClick={newRace}>{busy ? "Simulating…" : "New race"}</button>
    </div>
  );
}

function Stage({ data, clock, busy, force }) {
  const { lap, frac, finished } = clock;
  const i = lap - 1;
  const order = useMemo(() => ORDER.filter((c) => data.cars[c]).slice().sort((a, b) => data.cars[a].total[i] - data.cars[b].total[i]), [data, i]);
  const lead = data.cars[order[0]].total[i];
  const posOf = (c) => order.indexOf(c) + 1;
  const gapOf = (c) => {
    if (posOf(c) === 1) return "Leader";
    const g = data.cars[c].total[i] - lead;
    return `+${g.toFixed(g < 0.1 ? 2 : 1)} s`;
  };
  const status = data.status[i];
  const card = (c) => <CarCard key={c} car={c} data={data} lap={lap} pos={posOf(c)} gap={gapOf(c)} />;
  const late = lap >= data.laps - 2;

  return (
    <>
      <div className={`stage ${busy ? "stale" : ""}`}>
        <div className="side left">{card("rollout")}{card("pirelli")}</div>
        <div className="center">
          <div className="lap-head">
            <div className="lap-big">Lap <b>{lap}</b><small>/{data.laps}</small></div>
            <span className={`flag2 ${status.toLowerCase()}`}>{FLAG[status]}</span>
          </div>
          <p className="race-sub">{TRACK_NAMES[data.track]} · race #{data.seed} · {data.mode === "f1" ? "F1 rules" : "Endurance rules: small tank, refuelling"}</p>
          <Weather data={data} i={i} />
          <TrackMap track={data.track} data={data} lap={lap} frac={frac} />
          {finished ? <Verdict data={data} /> : (
            <div className="force" role="group" aria-label="Change the race now">
              <span>From the next lap:</span>
              <button className="btn" disabled={busy || late} onClick={() => force((l) => ({ rain_at: l, heavy: false, dry_at: undefined }))}>Rain</button>
              <button className="btn" disabled={busy || late} onClick={() => force((l) => ({ rain_at: l, heavy: true, dry_at: undefined }))}>Heavy rain</button>
              <button className="btn" disabled={busy || late || !(data.wetness[i] > 0.05)} title="Stop the rain; the track dries over a few laps"
                onClick={() => force((l) => ({ dry_at: l }))}>Dry</button>
              <button className="btn" disabled={busy || late} onClick={() => force((l) => ({ sc_at: l }))}>Safety car</button>
            </div>
          )}
        </div>
        <div className="side">{card("rules")}{card("oracle")}</div>
      </div>
      <Timeline laps={data.laps} status={data.status} wetness={data.wetness} clock={clock}
        stops={[{ laps: data.cars.rollout.pitted.map((p, k) => (p && k > 0 ? k + 1 : null)).filter(Boolean), colour: CARS.rollout.colour, label: "PitWall stop" }]} />
    </>
  );
}

// Current conditions plus the weather radar the teams see (chance of rain over the next 10 laps).
function Weather({ data, i }) {
  const w = data.wetness[i] ?? 0;
  const label = w > 0.7 ? "Heavy rain" : w > 0.2 ? "Light rain" : w > 0.05 ? "Damp" : "Dry";
  const fc = (data.forecast[i] ?? []).slice(1);   // laps after this one
  return (
    <div className="weather">
      <div className="wx-now">
        <span className={`wx-icon ${w > 0.2 ? "wet" : ""}`} aria-hidden="true" />
        <div>
          <b>{label}</b>
          <div className="wx-meter" title={`Track wetness ${Math.round(w * 100)}%`}><span style={{ width: `${Math.round(w * 100)}%` }} /></div>
        </div>
      </div>
      {fc.length > 0 && <div className="wx-radar">
        <span className="wx-radar-label">Radar: chance of rain, next {fc.length} lap{fc.length === 1 ? "" : "s"}</span>
        <div className="wx-bars">
          {fc.map((p, k) => <span key={k} style={{ height: `${Math.max(6, p * 100)}%`, opacity: 0.35 + 0.65 * p }} title={`Lap ${i + 2 + k}: ${Math.round(p * 100)}%`} />)}
        </div>
      </div>}
    </div>
  );
}

function Verdict({ data }) {
  const f = data.finish;
  const g = f.pirelli - f.rollout;
  return (
    <p className="verdict2">
      {g >= 0 ? <>PitWall beat the Pirelli plan by <b>{g.toFixed(1)} s</b></> : <>The Pirelli plan beat PitWall by <b>{(-g).toFixed(1)} s</b> this time</>}
    </p>
  );
}
