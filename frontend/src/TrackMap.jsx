import { useEffect, useMemo, useState } from "react";
import { api } from "./api.js";
import { CARS, ORDER } from "./theme.js";

// Fallback when data/maps/<track>.json hasn't been made yet: a plain rounded oval.
function oval(n = 400) {
  return Array.from({ length: n }, (_, i) => {
    const a = (2 * Math.PI * i) / n;
    return [500 + 440 * Math.cos(a), 500 + 260 * Math.sin(a)];
  });
}

// The circuit with the four cars on it. Each car sits behind the leader by its time gap,
// converted to a fraction of a lap, so you can see the field spread and bunch up.
export default function TrackMap({ track, data, lap, frac }) {
  const [points, setPoints] = useState(null);
  useEffect(() => {
    setPoints(null);
    api.map(track).then((m) => setPoints(m.points)).catch(() => setPoints(oval()));
  }, [track]);

  const pts = points ?? oval();
  const box = useMemo(() => {
    const xs = pts.map((p) => p[0]), ys = pts.map((p) => p[1]);
    const pad = 60;
    return [Math.min(...xs) - pad, Math.min(...ys) - pad, Math.max(...xs) - Math.min(...xs) + 2 * pad, Math.max(...ys) - Math.min(...ys) + 2 * pad];
  }, [pts]);
  const d = useMemo(() => `M${pts.map((p) => p.join(",")).join("L")}Z`, [pts]);

  const i = lap - 1;
  const running = ORDER.filter((c) => data.cars[c]?.total[i] != null);
  const leader = running.reduce((a, c) => (data.cars[c].total[i] < data.cars[a].total[i] ? c : a), running[0]);
  const lead = data.cars[leader].total[i];
  const leaderLap = Math.max(1, data.cars[leader].lap_time[i]);
  const at = (f) => pts[Math.floor((((f % 1) + 1) % 1) * pts.length) % pts.length];
  // draw ours last so it sits on top
  const drawOrder = ["oracle", "pirelli", "rules", "rollout"];
  const wet = data.wetness[i] ?? 0;
  const placed = drawOrder.filter((c) => data.cars[c]?.total[i] != null).map((c) => {
    const [x, y] = at(frac - (data.cars[c].total[i] - lead) / leaderLap);
    return { c, x, y };
  });

  return (
    <svg className="map" viewBox={box.join(" ")} role="img" aria-label={`Track map, lap ${lap}`}>
      <path d={d} className="map-edge" />
      <path d={d} className="map-road" />
      {wet > 0.2 && <path d={d} className="map-wet" style={{ opacity: Math.min(0.9, wet) }} />}
      <circle cx={pts[0][0]} cy={pts[0][1]} r={9} className="map-start"><title>Start / finish line</title></circle>
      {placed.map(({ c, x, y }) => (
        <g key={c} className={`map-car ${c === "rollout" ? "ours" : ""}`}>
          <circle cx={x} cy={y} r={c === "rollout" ? 24 : 18} fill={CARS[c].colour}><title>{CARS[c].label}</title></circle>
          {c === "rollout" && <text x={x} y={y - 36} textAnchor="middle">PitWall</text>}
        </g>
      ))}
    </svg>
  );
}
