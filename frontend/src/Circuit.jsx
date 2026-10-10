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

function Shape({ shape, x, y, r, colour }) {
  if (shape === "diamond") return <path className="body" d={`M${x},${y - r * 1.25}L${x + r * 1.25},${y}L${x},${y + r * 1.25}L${x - r * 1.25},${y}Z`} fill={colour} />;
  if (shape === "triangle") return <path className="body" d={`M${x},${y - r * 1.35}L${x + r * 1.25},${y + r * 0.9}L${x - r * 1.25},${y + r * 0.9}Z`} fill={colour} />;
  if (shape === "ghost") return <path className="ghost" d={`M${x},${y - r * 1.25}L${x + r * 1.25},${y}L${x},${y + r * 1.25}L${x - r * 1.25},${y}Z`} stroke={colour} />;
  if (shape === "ring") return <circle className="ghost" cx={x} cy={y} r={r} stroke={colour} />;
  return <circle className={shape === "dot" ? "map-small" : "body"} cx={x} cy={y} r={r} fill={colour} />;
}

// A circuit with markers on it. Each marker: { id, f (0..1 round the lap from the timing line),
// colour, r, shape (circle | diamond | triangle | ghost | ring | dot), tag? (text plate above it),
// ours? (drawn last, with a bone ring), title? }.
export default function Circuit({ track, markers, wet = 0, sc = false, className = "" }) {
  const pts = useCircuit(track);
  const box = useMemo(() => {
    const xs = pts.map((p) => p[0]), ys = pts.map((p) => p[1]);
    const pad = 90;
    return [Math.min(...xs) - pad, Math.min(...ys) - pad, Math.max(...xs) - Math.min(...xs) + 2 * pad, Math.max(...ys) - Math.min(...ys) + 2 * pad];
  }, [pts]);
  const d = useMemo(() => `M${pts.map((p) => p.join(",")).join("L")}Z`, [pts]);
  const at = (f) => pts[Math.floor((((f % 1) + 1) % 1) * pts.length) % pts.length];
  const [x0, y0] = pts[0], [x1, y1] = pts[2];
  const len = Math.hypot(x1 - x0, y1 - y0) || 1;
  const nx = -(y1 - y0) / len, ny = (x1 - x0) / len;
  const sorted = [...markers].sort((a, b) => (a.ours ? 1 : 0) - (b.ours ? 1 : 0));
  // tags: ours first, then the rest; skip any that would overlap one already placed
  const kept = [];
  [...markers].filter((m) => m.tag).sort((a, b) => (b.ours ? 1 : 0) - (a.ours ? 1 : 0)).forEach((m) => {
    const [x, y] = at(m.f);
    if (kept.every((k) => Math.abs(k.x - x) > 95 || Math.abs(k.y - y) > 55)) kept.push({ id: m.id, x, y });
  });
  const tagged = new Set(kept.map((k) => k.id));

  return (
    <svg className={`map ${className}`} viewBox={box.join(" ")} role="img" aria-label="Track map">
      <path d={d} className="map-edge" />
      <path d={d} className="map-road" />
      {sc && <path d={d} className="map-sc" />}
      {wet > 0.2 && <path d={d} className="map-wet" style={{ opacity: Math.min(1, 0.3 + wet) }} />}
      <line x1={x0 - nx * 30} y1={y0 - ny * 30} x2={x0 + nx * 30} y2={y0 + ny * 30} className="map-line" />
      {sorted.map((m) => {
        const [x, y] = at(m.f);
        return (
          <g key={m.id} className={`map-car ${m.ours ? "ours" : ""}`}>
            {m.ours && <circle className="ring" cx={x} cy={y} r={m.r + 7} />}
            <Shape shape={m.shape} x={x} y={y} r={m.r} colour={m.colour} />
            {m.title && <title>{m.title}</title>}
          </g>
        );
      })}
      {sorted.filter((m) => tagged.has(m.id)).map((m) => {
        const [x, y] = at(m.f);
        const w = m.tag.length * 17 + 16;
        const ty = y - m.r - 44;
        return (
          <g key={`t-${m.id}`} className="map-tag">
            <rect x={x - w / 2} y={ty} width={w} height={36} fill={m.colour} />
            <text x={x} y={ty + 28} textAnchor="middle">{m.tag}</text>
          </g>
        );
      })}
    </svg>
  );
}
