export default function Playback({ pb, max }) {
  return (
    <div className="playback">
      {pb.playing
        ? <button className="btn" onClick={pb.pause}>Pause</button>
        : <button className="btn primary" onClick={pb.play}>{pb.lap >= max ? "Replay race" : "Play"}</button>}
      <label className="lap-slider">
        <span className="sr">Lap</span>
        <input type="range" min={1} max={max} value={pb.lap} onChange={(e) => { pb.pause(); pb.setLap(+e.target.value); }} />
      </label>
      <label className="speed">
        Speed
        <select value={pb.speed} onChange={(e) => pb.setSpeed(+e.target.value)}>
          <option value={3}>Slow</option><option value={6}>Normal</option><option value={14}>Fast</option>
        </select>
      </label>
    </div>
  );
}
