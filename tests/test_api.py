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
