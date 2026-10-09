// Car colours never reuse F1 tyre colours (soft red, medium yellow, hard white, inter green, wet blue).
export const CARS = {
  pirelli: { label: "Pirelli plan", tower: "Pirelli plan", short: "PIR", colour: "#a78bfa" },
  rules: { label: "Simple rules", tower: "Simple rules", short: "RUL", colour: "#fb923c" },
  rollout: { label: "PitWall (ours)", tower: "PitWall", short: "PWL", colour: "#22d3ee" },
  oracle: { label: "Hindsight (knows the future)", tower: "Hindsight", short: "HND", colour: "#94a3b8" },
};
export const ORDER = ["pirelli", "rules", "rollout", "oracle"];
export const TYRES = { SOFT: "#ef4444", MEDIUM: "#facc15", HARD: "#f1f5f9", INTER: "#22c55e", WET: "#3b82f6" };
export const TRACK_NAMES = { bahrain: "Bahrain", monza: "Monza", zandvoort: "Zandvoort", singapore: "Singapore" };

export function fmtTime(s) {
  if (s == null) return "DNF";
  const h = Math.floor(s / 3600), m = Math.floor((s % 3600) / 60), sec = (s % 60).toFixed(3).padStart(6, "0");
  return `${h}:${String(m).padStart(2, "0")}:${sec}`;
}
export const signed = (v, d = 1) => (v == null ? "–" : `${v >= 0 ? "+" : "−"}${Math.abs(v).toFixed(d)}`);
