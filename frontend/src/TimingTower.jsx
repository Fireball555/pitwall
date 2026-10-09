import { CARS, TYRES } from "./theme.js";

// The race order at the current lap, like a broadcast timing tower.
export default function TimingTower({ data, lap }) {
  const i = lap - 1;
  const rows = Object.entries(data.cars)
    .map(([car, c]) => ({ car, total: c.total[i], compound: c.compound[i], age: c.tyre_age[i], fuel: c.fuel[i],
      stops: c.pitted.slice(0, lap).filter(Boolean).length }))
    .sort((a, b) => a.total - b.total);
  const lead = rows[0]?.total ?? 0;
  const status = data.status[i];
  return (
    <div className="tower" aria-live="polite">
      <div className="tower-head">
        <span className="lapnum">Lap {lap}<small>/{data.laps}</small></span>
        <span className={`flag ${status.toLowerCase()}`}>{status === "GREEN" ? (data.wetness[i] > 0.2 ? "Rain" : "Green") : status === "SC" ? "Safety car" : "Virtual SC"}</span>
      </div>
      <ol>
        {rows.map((r, k) => (
          <li key={r.car} className={r.car === "rollout" ? "ours" : ""}>
            <span className="pos">{k + 1}</span>
            <span className="swatch" style={{ background: CARS[r.car].colour }} />
            <span className="name" title={CARS[r.car].label}>{CARS[r.car].tower}</span>
            <span className="tyre" style={{ borderColor: TYRES[r.compound] }} title={r.compound}>{r.compound[0]}</span>
            <span className="age">{r.age}L</span>
            {data.mode === "endurance" && <span className="age">{Math.round(r.fuel)}kg</span>}
            <span className="gap">{k === 0 ? "Leader" : `+${(r.total - lead).toFixed(1)}`}</span>
          </li>
        ))}
      </ol>
    </div>
  );
}
