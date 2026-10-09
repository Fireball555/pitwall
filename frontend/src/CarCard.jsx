import { CARS, TYRES } from "./theme.js";

const TYRE_NAME = { SOFT: "Soft", MEDIUM: "Medium", HARD: "Hard", INTER: "Intermediate", WET: "Full wet" };
const WHAT = {
  pirelli: "Follows its pre-race plan",
  rules: "Pits when tyres are worn",
  rollout: "Imagines 100 futures, every lap",
  oracle: "PitWall's thinking, but knows the future",
};
const strip = (r) => r.replace(/^Lap \d+:\s*/, "").replace(" ± 0.0", "");

// One car's dashboard: place, gap, tyre, fuel, and the last call it made.
export default function CarCard({ car, data, lap, pos, gap }) {
  const c = data.cars[car];
  const i = lap - 1;
  const compound = c.compound[i];
  const pitted = c.pitted[i];
  const stops = c.pitted.slice(1, lap).filter(Boolean).length;
  const calls = c.decisions.filter((d) => d.reason && d.lap <= lap);
  const last = calls[calls.length - 1];
  const now = c.decisions.find((d) => d.lap === lap);
  const isOurs = car === "rollout";
  const fuelMax = data.mode === "endurance" ? Math.max(...c.fuel) : 0;

  return (
    <article className={`card ${isOurs ? "ours" : ""} ${pitted && lap > 1 ? "pitting" : ""}`} style={{ "--car": CARS[car].colour }}>
      <header className="card-head">
        <div>
          <h3>{CARS[car].tower}</h3>
          <p className="card-what">{WHAT[car]}</p>
        </div>
        <div className="card-pos">P{pos}</div>
      </header>

      <div className="card-row">
        <span className="tyre-badge" style={{ borderColor: TYRES[compound] }}>{compound[0]}</span>
        <span className="card-tyre">{TYRE_NAME[compound]}<small>{c.tyre_age[i]} laps old</small></span>
        <span className="card-gap">{gap}</span>
      </div>

      <TyreHealth life={c.tyre_life[i]} loss={c.tyre_loss[i]} wetTyre={compound === "INTER" || compound === "WET"} />

      {data.mode === "endurance" && (
        <div className="fuel" aria-label={`Fuel ${Math.round(c.fuel[i])} kg`}>
          <span style={{ width: `${(100 * Math.max(0, c.fuel[i])) / fuelMax}%` }} />
          <small>{Math.round(c.fuel[i])} kg fuel</small>
        </div>
      )}

      <div className="call" key={last?.lap ?? 0}>
        {pitted && lap > 1 && <span className="pit-flag">PIT</span>}
        <span className="call-text">
          {last ? <><b>Lap {last.lap}</b> {strip(last.reason)}</> : "No calls yet"}
        </span>
        <small>{stops} stop{stops === 1 ? "" : "s"}</small>
      </div>

      {isOurs && <Thinking d={now} />}
    </article>
  );
}

// What PitWall weighed this lap: each option's average finish, relative to the best one.
function Thinking({ d }) {
  const opts = d?.options ? Object.entries(d.options).sort((a, b) => a[1] - b[1]) : [];
  if (opts.length < 2) return <p className="think-idle">Fresh tyres, green flag: nothing worth weighing this lap.</p>;
  const best = opts[0][1];
  const spread = Math.max(1, opts[opts.length - 1][1] - best);
  return (
    <div className="think">
      <p className="think-title">This lap it compared</p>
      {opts.slice(0, 4).map(([k, v], n) => (
        <div className={`think-row ${n === 0 ? "best" : ""}`} key={k}>
          <span className="think-label">{k}</span>
          <span className="think-bar"><span style={{ width: `${n === 0 ? 100 : Math.max(4, 100 - (100 * (v - best)) / spread)}%` }} /></span>
          <span className="think-val">{n === 0 ? "best" : `+${(v - best).toFixed(1)} s`}</span>
        </div>
      ))}
    </div>
  );
}

// How used-up the current set is: share of its useful life, and the time it now costs per lap.
function TyreHealth({ life, loss, wetTyre }) {
  const pct = Math.round(100 * life);
  const tone = life >= 1 ? "bad" : life >= 0.75 ? "warn" : "ok";
  return (
    <div className="health" title="Share of this tyre set's useful life used, and seconds per lap lost to wear">
      <div className="health-top">
        <span>Tyre wear</span>
        <span className={tone}>{life >= 1 ? "Past its best" : `${pct}% used`}{!wetTyre && loss > 0.05 ? ` · ${loss.toFixed(1)} s/lap slower` : ""}</span>
      </div>
      <div className={`health-bar ${tone}`}><span style={{ width: `${Math.min(100, pct)}%` }} /></div>
    </div>
  );
}
