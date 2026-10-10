import { useEffect, useRef, useState } from "react";

// Smooth race clock. t = laps completed (a float), so maps move cars continuously while the
// dashboards update once per lap. resumeAt: lap to continue from when a new race arrives
// (used by "rain now"); autoplay: start playing as soon as a race arrives.
export function useRaceClock(laps, resetKey, resumeAt = null, autoplay = true) {
  const [t, setT] = useState(0);
  const [playing, setPlaying] = useState(false);
  const [secPerLap, setSecPerLap] = useState(2);
  const raf = useRef(0);

  useEffect(() => { setT(resumeAt ? Math.min(laps, resumeAt - 1) : 0); setPlaying(autoplay || !!resumeAt); }, [resetKey]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (!playing) return undefined;
    let last = performance.now();
    const tick = (now) => {
      const dt = Math.max(0, now - last) / 1000; // rAF time can be slightly before `last`
      last = now;
      setT((x) => {
        const n = x + dt / secPerLap;
        if (n >= laps) { setPlaying(false); return laps; }
        return n;
      });
      raf.current = requestAnimationFrame(tick);
    };
    raf.current = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf.current);
  }, [playing, secPerLap, laps]);

  const lap = Math.max(1, Math.min(laps, Math.floor(t) + 1));   // the lap being driven (1-based)
  const frac = t >= laps ? 1 : t - Math.floor(t);                // how far round that lap the leader is
  const finished = t >= laps;
  return {
    t, lap, frac, finished, playing, secPerLap, setSecPerLap,
    play: () => { if (finished) setT(0); setPlaying(true); },
    pause: () => setPlaying(false),
    seek: (l) => { setPlaying(false); setT(Math.max(0, Math.min(laps, l - 1))); },
  };
}
