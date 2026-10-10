import { useEffect, useState } from "react";
import { api } from "./api.js";
import LiveRace from "./LiveRace.jsx";
import Proof from "./Proof.jsx";
import RealRaces from "./RealRaces.jsx";

const TABS = [
  { id: "live", label: "Live race", hint: "Watch one race lap by lap" },
  { id: "proof", label: "Proof", hint: "Thousands of races, head to head" },
  { id: "real", label: "Real races", hint: "Our strategist in a real 2023 race" },
];

export default function App() {
  const [tab, setTab] = useState("live");
  const [meta, setMeta] = useState(null);
  const [err, setErr] = useState(null);
  useEffect(() => { api.meta().then(setMeta).catch((e) => setErr(e.message)); }, []);
  const placeholders = meta?.tracks.filter((t) => !t.fitted).length ?? 0;

  return (
    <div className="app">
      <header className="topbar">
        <div className="brand">
          <span className="brand-mark" aria-hidden="true" />
          <div>
            <h1>PitWall</h1>
            <p className="tagline">The F1 strategist that races the future before every call</p>
          </div>
        </div>
        <nav className="tabs" aria-label="Screens">
          {TABS.map((t) => (
            <button key={t.id} className={`tab ${tab === t.id ? "on" : ""}`} onClick={() => setTab(t.id)} title={t.hint}>
              {t.label}
            </button>
          ))}
        </nav>
      </header>
      {err && <div className="notice bad">Can't reach the PitWall server ({err}). Start it with <code>python -m pitwall.server</code>.</div>}
      {placeholders > 0 && (
        <div className="notice">
          {placeholders} of 4 tracks still use placeholder numbers. Run <code>python -m pitwall.data.build --all</code> to fit them from real 2022–2023 data.
        </div>
      )}
      <main>
        {tab === "live" && <LiveRace />}
        {tab === "proof" && <Proof />}
        {tab === "real" && <RealRaces />}
      </main>
      <footer className="foot">Team Chumma Oru Commit · CommitCon · The Impossible Pit Stop</footer>
    </div>
  );
}
