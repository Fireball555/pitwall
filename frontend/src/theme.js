// "Purple Sector": on F1 timing screens purple means fastest overall, so PitWall runs purple and
// nothing else does. Car colours never reuse tyre colours (soft red, medium yellow, hard white,
// inter green, wet blue); cars are also told apart by shape on the map (circle, diamond, triangle,
// hollow diamond), so colour is never the only cue.
export const CARS = {
  pirelli: { label: "Pirelli plan", tower: "Pirelli plan", short: "PIR", colour: "#35c9d0", shape: "diamond" },
  rules: { label: "Simple rules", tower: "Simple rules", short: "RUL", colour: "#ff8cc6", shape: "triangle" },
  rollout: { label: "PitWall (ours)", tower: "PitWall", short: "PWL", colour: "#cf7dff", shape: "circle" },
  oracle: { label: "Hindsight (knows the future)", tower: "Hindsight", short: "HND", colour: "#8c8f99", shape: "ghost" },
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
