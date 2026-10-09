import { useEffect, useRef, useState } from "react";

// Lap-by-lap playback: returns [lap, setLap, playing, setPlaying, speed, setSpeed].
export function usePlayback(maxLap, resetKey) {
  const [lap, setLap] = useState(maxLap);
  const [playing, setPlaying] = useState(false);
  const [speed, setSpeed] = useState(6); // laps per second
  const timer = useRef(null);

  useEffect(() => { setLap(maxLap); setPlaying(false); }, [resetKey, maxLap]);

  useEffect(() => {
    clearInterval(timer.current);
    if (!playing) return;
    timer.current = setInterval(() => {
      setLap((l) => {
        if (l >= maxLap) { setPlaying(false); return maxLap; }
        return l + 1;
      });
    }, 1000 / speed);
    return () => clearInterval(timer.current);
  }, [playing, speed, maxLap]);

  const play = () => { if (lap >= maxLap) setLap(1); setPlaying(true); };
  return { lap, setLap, playing, play, pause: () => setPlaying(false), speed, setSpeed };
}
