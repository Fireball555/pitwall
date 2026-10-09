"""API smoke tests: every endpoint the React app uses answers correctly. Owner: whoever changes pitwall/server.py."""
from fastapi.testclient import TestClient

from pitwall.server import app

client = TestClient(app)


def test_meta_lists_four_tracks():
    j = client.get("/api/meta").json()
    assert [t["id"] for t in j["tracks"]] == ["bahrain", "monza", "zandvoort", "singapore"]


def test_race_returns_every_lap_for_four_cars():
    j = client.get("/api/race", params={"track": "monza", "seed": 3, "n": 40}).json()
    assert set(j["cars"]) == {"pirelli", "rules", "rollout", "oracle"}
    assert all(len(c["total"]) == j["laps"] for c in j["cars"].values())


def test_endurance_race_reports_fuel():
    j = client.get("/api/race", params={"track": "bahrain", "mode": "endurance", "seed": 2, "n": 40}).json()
    assert sum(j["cars"]["rules"]["fuel_added"]) > 0


def test_bad_input_is_a_clear_error():
    r = client.get("/api/race", params={"track": "nowhere"})
    assert r.status_code == 404 and "Choose one of" in r.json()["detail"]


def test_proof_and_replay_answer():
    assert "available" in client.get("/api/proof", params={"track": "bahrain"}).json()
    drivers = client.get("/api/replay/drivers", params={"track": "bahrain"}).json()["drivers"]
    rep = client.get("/api/replay", params={"track": "bahrain", "driver": drivers[0]}).json()
    assert rep["our_finish_pos"] >= 1 and "sanity" in rep


def test_zandvoort_replay_is_refused_with_a_reason():
    r = client.get("/api/replay/drivers", params={"track": "zandvoort"})
    assert r.status_code == 400 and "red flag" in r.json()["detail"]


def test_replay_has_what_the_race_screen_draws():
    drivers = client.get("/api/replay/drivers", params={"track": "bahrain"}).json()
    rep = client.get("/api/replay", params={"track": "bahrain", "driver": drivers["drivers"][0]}).json()
    n = len(rep["laps"])
    assert len(rep["status"]) == n and len(rep["ghost"]) == n and len(rep["lap_ref"]) == n
    assert "OURS" in rep["grid"] and rep["laps"][0]["order"]


def test_summary_and_endurance_fuel_fields():
    assert "tracks" in client.get("/api/summary").json()
    r = client.get("/api/race", params={"track": "bahrain", "mode": "endurance", "seed": 3, "n": 20}).json()
    assert r["tank"] > 0 and r["fuel_burn"] > 0 and "tyre_life" in r["cars"]["rollout"]
