import { useEffect, useState } from "react";

// F1 start sequence: five red lights come on one by one, then all go out together and the race
// starts. Click anywhere to skip.
export default function StartLights({ onDone }) {
  const [on, setOn] = useState(0);        // lights lit (0..5)
  const [out, setOut] = useState(false);  // all lights out: go!
  useEffect(() => {
    const timers = [1, 2, 3, 4, 5].map((k) => setTimeout(() => setOn(k), 380 * k));
    const hold = 380 * 5 + 450 + Math.random() * 450;  // like the real thing, the wait varies
    timers.push(setTimeout(() => setOut(true), hold));
    timers.push(setTimeout(onDone, hold + 650));
    return () => timers.forEach(clearTimeout);
  }, []); // eslint-disable-line react-hooks/exhaustive-deps
  return (
    <div className="lights-wrap" onClick={onDone} role="status" aria-live="assertive">
      <div className="lights" aria-hidden="true">
        {[1, 2, 3, 4, 5].map((k) => (
          <div key={k} className="light-col">
            <span className={!out && on >= k ? "lit" : ""} />
            <span className={!out && on >= k ? "lit" : ""} />
          </div>
        ))}
      </div>
      <p className={`lights-text ${out ? "go" : ""}`}>{out ? "Lights out and away we go" : "Click to skip"}</p>
    </div>
  );
}
