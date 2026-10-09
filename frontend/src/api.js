async function get(path) {
  const r = await fetch(path);
  if (!r.ok) {
    let msg = `${r.status}`;
    try { msg = (await r.json()).detail || msg; } catch { /* keep status */ }
    throw new Error(msg);
  }
  return r.json();
}
export const api = {
  meta: () => get("/api/meta"),
  race: (p) => get(`/api/race?${new URLSearchParams(Object.entries(p).filter(([, v]) => v !== null && v !== undefined))}`),
  map: (track) => get(`/api/map?track=${track}`),
  summary: (mode) => get(`/api/summary?mode=${mode}`),
  proof: (track, mode) => get(`/api/proof?track=${track}&mode=${mode}`),
  drivers: (track) => get(`/api/replay/drivers?track=${track}`),
  replay: (track, driver) => get(`/api/replay?track=${track}&driver=${driver}`),
};
