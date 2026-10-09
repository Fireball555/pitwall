import { useEffect, useMemo, useState } from "react";
import { api } from "./api.js";

// Fallback when data/maps/<track>.json hasn't been made yet: a plain rounded oval.
function oval(n = 400) {
  return Array.from({ length: n }, (_, i) => {
    const a = (2 * Math.PI * i) / n;
    return [500 + 440 * Math.cos(a), 500 + 260 * Math.sin(a)];
  });
}

const cache = {};
function useCircuit(track) {
  const [points, setPoints] = useState(cache[track] ?? null);
  useEffect(() => {
    if (cache[track]) { setPoints(cache[track]); return; }
    setPoints(null);
    api.map(track).then((m) => { cache[track] = m.points; setPoints(m.points); }).catch(() => setPoints(oval()));
  }, [track]);
  return points ?? oval();
}

// A circuit with markers on it. Each marker: { id, f (0..1 round the lap from the timing line),
// colour, r, label?, ring? (hollow), top? (drawn last), title? }.
export default function Circuit({ track, markers, wet = 0, className = "" }) {
  const pts = useCircuit(track);
  const box = useMemo(() => {
    const xs = pts.map((p) => p[0]), ys = pts.map((p) => p[1]);
    const pad = 70;
    return [Math.min(...xs) - pad, Math.min(...ys) - pad, Math.max(...xs) - Math.min(...xs) + 2 * pad, Math.max(...ys) - Math.min(...ys) + 2 * pad];
  }, [pts]);
  const d = useMemo(() => `M${pts.map((p) => p.join(",")).join("L")}Z`, [pts]);
  const at = (f) => pts[Math.floor((((f % 1) + 1) % 1) * pts.length) % pts.length];
  // the timing line, drawn across the track
  const [x0, y0] = pts[0], [x1, y1] = pts[2];
  const len = Math.hypot(x1 - x0, y1 - y0) || 1;
  const nx = -(y1 - y0) / len, ny = (x1 - x0) / len;
  const sorted = [...markers].sort((a, b) => (a.top ? 1 : 0) - (b.top ? 1 : 0));
  // labels: most important first (ours, then hollow rings, then others); drop any that would overlap
  const kept = [];
  const rank = (m) => (m.top ? 0 : m.ring ? 1 : 2);
  [...markers].filter((m) => m.label).sort((a, b) => rank(a) - rank(b)).forEach((m) => {
    const [x, y] = at(m.f);
    if (kept.every((k) => Math.hypot(k.x - x, k.y - y) > 90)) kept.push({ id: m.id, x, y });
  });
  const labelled = new Set(kept.map((k) => k.id));

  return (
    <svg className={`map ${className}`} viewBox={box.join(" ")} role="img" aria-label="Track map">
      <path d={d} className="map-edge" />
      <path d={d} className="map-road" />
      {wet > 0.2 && <path d={d} className="map-wet" style={{ opacity: Math.min(0.9, wet) }} />}
      <line x1={x0 - nx * 26} y1={y0 - ny * 26} x2={x0 + nx * 26} y2={y0 + ny * 26} className="map-line" />
      {sorted.map((m) => {
        const [x, y] = at(m.f);
        return (
          <g key={m.id} className={`map-car ${m.top ? "top" : ""}`}>
            {m.ring
              ? <circle cx={x} cy={y} r={m.r} fill="none" stroke={m.colour} strokeWidth={6} strokeDasharray="10 7" />
              : <circle cx={x} cy={y} r={m.r} fill={m.colour} className={m.top ? "glow" : ""} />}
            {m.title && <title>{m.title}</title>}
            {m.label && labelled.has(m.id) && <text x={x} y={y - m.r - 14} textAnchor="middle">{m.label}</text>}
          </g>
        );
      })}
    </svg>
  );
}
