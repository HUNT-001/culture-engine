"""Confirmed entity selections persist and survive a plan revisit (mock-mode HTTP)."""


def _plan(client):
    r = client.post("/api/plans", json={"location": "New York"})
    assert r.status_code == 201, r.text
    return r.json()


def _join(client, plan, name):
    r = client.post(f"/api/plans/{plan['plan_id']}/participants",
                    json={"display_name": name}, headers={"X-Share-Token": plan["share_token"]})
    assert r.status_code == 201, r.text
    return r.json()


def test_confirmed_selection_is_persisted_and_returned_on_revisit(client):
    plan = _plan(client)
    me = _join(client, plan, "Ana")
    put = client.put(
        f"/api/plans/{plan['plan_id']}/participants/{me['participant_id']}/preferences",
        json={
            "interests": ["independent film", "jazz"],
            "resolved_interests": [
                {"text": "independent film", "entity_id": "ENT-FILM",
                 "name": "Independent Film", "entity_type": "urn:tag"},
            ],
            "dislikes": [],
        },
        headers={"X-Participant-Token": me["participant_token"]},
    )
    assert put.status_code == 200, put.text
    view = put.json()
    assert view["interests"] == ["independent film", "jazz"]
    assert view["resolved_interests"] == [
        {"text": "independent film", "entity_id": "ENT-FILM",
         "name": "Independent Film", "entity_type": "urn:tag"},
    ]

    # Revisit the plan (as if from another session) — the selection is still there.
    headers = {"X-Share-Token": plan["share_token"]}
    got = client.get(f"/api/plans/{plan['plan_id']}", headers=headers)
    assert got.status_code == 200
    parts = got.json()["participants"]
    participant = next(p for p in parts if p["participant_id"] == me["participant_id"])
    assert participant["resolved_interests"][0]["entity_id"] == "ENT-FILM"
    # "jazz" had no confirmation, so it is not fabricated into a resolved entity.
    assert all(r["text"] != "jazz" for r in participant["resolved_interests"])


def test_updating_preferences_replaces_prior_confirmation(client):
    plan = _plan(client)
    me = _join(client, plan, "Ana")
    headers = {"X-Participant-Token": me["participant_token"]}
    url = f"/api/plans/{plan['plan_id']}/participants/{me['participant_id']}/preferences"
    old = [{"text": "jazz", "entity_id": "OLD", "name": "Jazz"}]
    client.put(url, json={"interests": ["jazz"], "resolved_interests": old, "dislikes": []},
               headers=headers)
    # Re-save with a different confirmation.
    new = [{"text": "jazz", "entity_id": "NEW", "name": "Jazz Music"}]
    r = client.put(url, json={"interests": ["jazz"], "resolved_interests": new, "dislikes": []},
                   headers=headers)
    assert r.status_code == 200
    assert r.json()["resolved_interests"] == [
        {"text": "jazz", "entity_id": "NEW", "name": "Jazz Music", "entity_type": "unknown"},
    ]
