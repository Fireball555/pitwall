import { useEffect, useMemo, useRef, useState } from "react";
import { api } from "./api.js";
import CarCard from "./CarCard.jsx";
import Multiverse from "./Multiverse.jsx";
import StartLights from "./StartLights.jsx";
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
  { name: "Bahrain · safety cars", track: "bahrain", mode: "f1", weather: "usual", safety: "usual", seed: 5 },
  { name: "Bahrain · rain arrives", track: "bahrain", mode: "f1", weather: "wet", safety: "usual", seed: 8 },
  { name: "Zandvoort · dry", track: "zandvoort", mode: "f1", weather: "usual", safety: "usual", seed: 3 },
  { name: "Zandvoort · rain + chaos", track: "zandvoort", mode: "f1", weather: "wet", safety: "usual", seed: 5 },
  { name: "Singapore · safety cars", track: "singapore", mode: "f1", weather: "usual", safety: "usual", seed: 9 },
  { name: "Endurance · fuel calls", track: "bahrain", mode: "endurance", weather: "usual", safety: "usual", seed: 2 },
];

export default function LiveRace() {
  const [form, setForm] = useState({ ...DEMOS[1] });
  const [events, setEvents] = useState({});           // forced during the race: rain_at, heavy, sc_at
  const [data, setData] = useState(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState(null);
  const [runId, setRunId] = useState(0);
  const [custom, setCustom] = useState(false);
  const resume = useRef(null);

  const latest = useRef(0);   // only the newest race request may update the screen
  const run = (f, ev, resumeLap = null) => {
    const id = ++latest.current;
    setBusy(true); setErr(null);
    api.race({ track: f.track, mode: f.mode, seed: f.seed, rain: WEATHER[f.weather].rain, sc: SAFETY[f.safety].sc, ...ev })
      .then((d) => { if (id !== latest.current) return; resume.current = resumeLap; setData(d); setRunId((k) => k + 1); })
      .catch((e) => { if (id === latest.current) setErr(e.message); })
      .finally(() => { if (id === latest.current) setBusy(false); });
  };
  useEffect(() => { run(form, {}); }, []); // eslint-disable-line react-hooks/exhaustive-deps

  // any setting change starts that race straight away
  const stop = () => { clock.pause(); setMv(null); };
  const change = (k, v) => { const f = { ...form, [k]: v }; stop(); setForm(f); setEvents({}); run(f, {}); };
  const newRace = () => change("seed", newSeed());
  const pickDemo = (k) => { const { name, ...f } = DEMOS[k]; stop(); setForm(f); setEvents({}); run(f, {}); };
  const clock = useRaceClock(data?.laps ?? 1, runId, resume.current, false);
  const [lights, setLights] = useState(false);
  const [explain, setExplain] = useState(true);   // pause at each PitWall pit call and show its futures
  const [mv, setMv] = useState(null);             // { lap, decision, auto }
  const shown = useRef(new Set());

  // a new race starts with the F1 start lights; a "rain now" rerun just carries on
  useEffect(() => { if (runId && !resume.current) setLights(true); }, [runId]);
  // at each PitWall pit call: pause and look inside its head
  useEffect(() => {
    if (!data || busy || lights || !explain || !clock.playing || clock.lap < 2) return;
    const d = data.cars.rollout.decisions.find((x) => x.lap === clock.lap && x.reason && x.samples);
    const key = `${runId}:${clock.lap}`;
    if (d && !shown.current.has(key)) {
      shown.current.add(key);
      clock.pause();
      setMv({ lap: clock.lap, decision: d, auto: true });
    }
  }, [clock.lap, clock.playing, data, explain, runId, busy, lights]); // eslint-disable-line react-hooks/exhaustive-deps
  const closeMv = () => { const wasAuto = mv?.auto; setMv(null); if (wasAuto) clock.play(); };
  const openMv = () => {
    const d = data?.cars.rollout.decisions.find((x) => x.lap === clock.lap && x.samples);
    if (d) { clock.pause(); setMv({ lap: clock.lap, decision: d, auto: false }); }
  };
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
      <Scenarios form={form} pickDemo={pickDemo} custom={custom} setCustom={setCustom} busy={busy} />
      {custom && <Setup form={form} change={change} busy={busy} newRace={newRace} />}
      {err && <p className="error">{err}</p>}
      {busy && !data && <p className="help">Our strategist is imagining 100 futures for every option, every lap…</p>}
      {data && <Stage data={data} events={events} clock={clock} busy={busy} force={force} explain={explain} setExplain={setExplain} openMv={openMv} />}
      {lights && <StartLights onDone={() => { setLights(false); clock.play(); }} />}
      {mv && <Multiverse lap={mv.lap} decision={mv.decision} auto={mv.auto} onClose={closeMv} />}
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

const sameRace = (a, b) => ["track", "mode", "weather", "safety", "seed"].every((k) => a[k] === b[k]);

// The rehearsed races, one click each; "Custom race" opens every setting.
function Scenarios({ form, pickDemo, custom, setCustom, busy }) {
  return (
    <div className="scenarios" role="group" aria-label="Demo races">
      <span className="label">Races</span>
      {DEMOS.map((d, k) => (
        <button key={k} className={`pill ${sameRace(d, form) ? "on" : ""}`} aria-pressed={sameRace(d, form)} disabled={busy} onClick={() => pickDemo(k)}>{d.name}</button>
      ))}
      <button className={`pill custom ${custom ? "on" : ""}`} aria-expanded={custom} onClick={() => setCustom(!custom)}>Custom race {custom ? "▴" : "▾"}</button>
    </div>
  );
}

function Setup({ form, change, busy, newRace }) {
  return (
    <div className="setup">
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
      <button className="btn primary new-race" disabled={busy} onClick={newRace}>{busy ? "Simulating…" : "New random race"}</button>
    </div>
  );
}

function Stage({ data, events, clock, busy, force, explain, setExplain, openMv }) {
  const { lap, frac, finished } = clock;
  const i = lap - 1;
  // out = ran out of fuel by this lap; a disqualified car (two-compound rule) drops to the back at the flag
  const out = (c) => (data.cars[c].out_after != null && lap > data.cars[c].out_after) || (finished && data.cars[c].dsq);
  const rank = (c) => (out(c) ? Infinity : data.cars[c].total[i]);
  const order = useMemo(() => ORDER.filter((c) => data.cars[c]).slice().sort((a, b) => rank(a) - rank(b)), [data, i, finished]); // eslint-disable-line react-hooks/exhaustive-deps
  const lead = data.cars[order[0]].total[i];
  const posOf = (c) => order.indexOf(c) + 1;
  const gapOf = (c) => {
    if (out(c)) return data.cars[c].dsq ? "Disqualified" : "Out of fuel";
    if (posOf(c) === 1) return "Leader";
    const g = data.cars[c].total[i] - lead;
    return `+${g.toFixed(g < 0.1 ? 2 : 1)} s`;
  };
  const status = data.status[i];
  const card = (c, compact = false) => <CarCard key={c} car={c} data={data} lap={lap} pos={posOf(c)} gap={gapOf(c)} compact={compact} onExplain={c === "rollout" ? openMv : undefined} />;
  const late = lap >= data.laps - 2;
  const rainUsed = events.rain_at != null || events.dry_at != null;
  const deltaOut = out("pirelli") || out("rollout");

  const delta = data.cars.pirelli.total[i] - data.cars.rollout.total[i];
  const prev = data.status[i - 1];
  const wet = data.wetness[i] > 0.2;
  const banner = status === "SC" ? ["sc", "Safety car"] : status === "VSC" ? ["vsc", "Virtual safety car"]
    : prev && prev !== "GREEN" ? ["clear", "Track clear"] : wet ? ["rain vsc", data.wetness[i] > 0.7 ? "Heavy rain" : "Wet track"] : null;

  return (
    <>
      <div className={`stage ${busy ? "stale" : ""}`}>
        <div className="side left">{card("rollout")}</div>
        <div className="center">
          {banner && <div key={banner[0]} className={`banner ${banner[0]}`}><span>{banner[1]}</span></div>}
          <div className="center-top">
            <div className="lap-big"><span className="lap-word">Lap</span><b>{lap}</b><small>/{data.laps}</small></div>
            <p className="race-sub">{TRACK_NAMES[data.track]}<br />race #{data.seed} · {data.mode === "f1" ? "F1 rules" : "endurance: refuelling"}</p>
            <div className="delta" aria-live="off">
              <span className="label"><span className="tag" style={{ "--car": CARS.rollout.colour }}>PWL</span> vs <span className="tag" style={{ "--car": CARS.pirelli.colour }}>PIR</span></span>
              <div className={`delta-val ${delta > 0.05 && !deltaOut ? "ahead" : ""}`}>{deltaOut ? "—" : <>{delta >= 0 ? "−" : "+"}{Math.abs(delta).toFixed(1)}<small style={{ fontSize: "0.5em" }}> s</small></>}</div>
              <div className="delta-sub">{deltaOut ? `${out("rollout") ? "PitWall" : "The Pirelli plan"} is out of the race` : delta > 0.05 ? "PitWall ahead of the Pirelli plan" : delta < -0.05 ? "PitWall behind the Pirelli plan" : "level"}</div>
            </div>
          </div>
          <Weather data={data} i={i} />
          <TrackMap track={data.track} data={data} lap={lap} frac={frac} />
          {finished ? <Verdict data={data} /> : (
            <div className="force" role="group" aria-label="Change the race now">
              <span className="label">From next lap</span>
              <button className="btn" disabled={busy || late || rainUsed} title={rainUsed ? "Once per race" : undefined} onClick={() => force((l) => ({ rain_at: l, heavy: false }))}>Rain</button>
              <button className="btn" disabled={busy || late || rainUsed} title={rainUsed ? "Once per race" : undefined} onClick={() => force((l) => ({ rain_at: l, heavy: true }))}>Heavy rain</button>
              <button className="btn" disabled={busy || late || events.dry_at != null || !(data.wetness[i] > 0.05)} title="Stop the rain; the track dries over a few laps"
                onClick={() => force((l) => ({ dry_at: l }))}>Dry</button>
              <button className="btn" disabled={busy || late || events.sc_at != null} title={events.sc_at != null ? "Once per race" : undefined} onClick={() => force((l) => ({ sc_at: l }))}>Safety car</button>
            </div>
          )}
        </div>
        <div className="side">{card("pirelli", true)}{card("rules", true)}{card("oracle", true)}</div>
      </div>
      <Timeline laps={data.laps} status={data.status} wetness={data.wetness} clock={clock}
        stops={[{ laps: data.cars.rollout.pitted.map((p, k) => (p && k > 0 ? k + 1 : null)).filter(Boolean), colour: CARS.rollout.colour, label: "PitWall stop" }]}
        extra={(
          <button className={`toggle ${explain ? "on" : ""}`} aria-pressed={explain} onClick={() => setExplain(!explain)}
            title="Pause at each PitWall pit call and show the futures it imagined">
            <span className="toggle-dot" />Explain calls
          </button>
        )} />
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
  if (f.pirelli == null || f.rollout == null) {
    const who = f.rollout == null ? "PitWall" : "The Pirelli plan";
    const why = data.cars[f.rollout == null ? "rollout" : "pirelli"].dsq ? "was disqualified (one dry compound only)" : "ran out of fuel";
    return <p className="verdict2">Chequered flag · {who} {why}</p>;
  }
  const g = f.pirelli - f.rollout;
  return (
    <p className="verdict2">
      {g >= 0 ? <>Chequered flag · PitWall beat the Pirelli plan by <b>{g.toFixed(1)} s</b></> : <>Chequered flag · the Pirelli plan beat PitWall by <b>{(-g).toFixed(1)} s</b></>}
    </p>
  );
}
