import Circuit from "./Circuit.jsx";
import { CARS, ORDER } from "./theme.js";

// Gap behind the leader in laps, at the end of lap index k.
function gapLaps(data, c, k) {
  if (k < 0) return 0;
  const lead = Math.min(...ORDER.map((o) => data.cars[o]?.total[k] ?? Infinity));
  const leaderLap = Math.max(1, ...ORDER.filter((o) => data.cars[o]?.total[k] === lead).map((o) => data.cars[o].lap_time[k]));
  return (data.cars[c].total[k] - lead) / leaderLap;
}

// The four cars on the circuit. Gaps slide smoothly from one lap's value to the next,
// so a pit stop shows as the car dropping back along the track.
export default function TrackMap({ track, data, lap, frac }) {
  const i = lap - 1;
  const markers = ["oracle", "pirelli", "rules", "rollout"].filter((c) => data.cars[c]?.total[i] != null).map((c) => {
    const g = gapLaps(data, c, i - 1) + (gapLaps(data, c, i) - gapLaps(data, c, i - 1)) * frac;
    return {
      id: c, f: frac - g, colour: CARS[c].colour, r: c === "rollout" ? 24 : 18,
      top: c === "rollout", label: c === "rollout" ? "PitWall" : undefined, title: CARS[c].label,
    };
  });
  return <Circuit track={track} markers={markers} wet={data.wetness[i] ?? 0} />;
}
