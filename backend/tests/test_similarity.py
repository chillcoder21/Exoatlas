"""Tests for the read-only, saved-scaler Similar Worlds endpoint."""

from __future__ import annotations

from urllib.parse import quote

import joblib
import numpy as np
import pandas as pd
import pytest

from backend.app import PROJECT_ROOT, _similarity_blockers, create_app


@pytest.fixture(scope="module")
def similarity_client():
    app = create_app(PROJECT_ROOT)
    app.config.update(TESTING=True)
    with app.test_client() as test_client:
        yield test_client


def test_neighbors_are_deterministic_sorted_and_exclude_the_selected_planet(similarity_client):
    path = f"/api/planets/{quote('11 Com b', safe='')}/similar?limit=8"
    first = similarity_client.get(path)
    second = similarity_client.get(path)

    assert first.status_code == second.status_code == 200
    body = first.get_json()
    assert body == second.get_json()
    names = [item["pl_name"] for item in body["neighbors"]]
    distances = [item["similarity_distance"] for item in body["neighbors"]]
    assert body["eligibility"]["eligible"] is True
    assert len(names) == 8
    assert body["neighbor_count"] == 8
    assert body["candidate_pool_size"] == 5272
    assert "11 Com b" not in names
    assert distances == sorted(distances)
    assert body["method"]["features"] == [
        "log10(pl_rade)", "log10(pl_orbper)", "pl_eqt", "pl_orbeccen"
    ]
    assert "not refit" in body["method"]["scaling"]


def test_neighbor_distances_use_the_saved_transforms_and_fitted_scaler(similarity_client):
    body = similarity_client.get(f"/api/planets/{quote('11 Com b', safe='')}/similar?limit=3").get_json()
    features = pd.read_csv(PROJECT_ROOT / "data/processed/clustering_features_with_temp.csv")
    scaler = joblib.load(PROJECT_ROOT / "artifacts/preprocessing/scaler_with_temp.joblib")
    transformed_columns = ["log10_pl_rade", "log10_pl_orbper", "pl_eqt", "pl_orbeccen"]
    vectors = scaler.transform(features[transformed_columns].to_numpy(dtype=float))
    positions = {name: index for index, name in enumerate(features["pl_name"])}
    target = vectors[positions["11 Com b"]]

    for neighbor in body["neighbors"]:
        expected = np.linalg.norm(target - vectors[positions[neighbor["pl_name"]]])
        assert neighbor["similarity_distance"] == pytest.approx(expected, abs=1e-12)


def test_incomplete_planet_has_no_neighbors_and_names_blocking_features(similarity_client):
    response = similarity_client.get(
        f"/api/planets/{quote('1RXS J160929.1-210524 b', safe='')}/similar"
    )

    assert response.status_code == 200
    body = response.get_json()
    assert body["eligibility"]["eligible"] is False
    assert body["neighbors"] == []
    assert {item["feature"] for item in body["eligibility"]["blockers"]} == {
        "pl_orbper", "pl_orbeccen"
    }


def test_log_inputs_must_be_positive_but_eccentricity_zero_is_valid():
    blockers = _similarity_blockers(pd.Series({
        "pl_rade": 0,
        "pl_orbper": -3,
        "pl_eqt": 300,
        "pl_orbeccen": 0,
    }))

    assert {(item["feature"], item["reason"]) for item in blockers} == {
        ("pl_rade", "must_be_positive_for_log10"),
        ("pl_orbper", "must_be_positive_for_log10"),
    }


@pytest.mark.parametrize("limit", ["0", "abc", "21"])
def test_invalid_neighbor_limits_return_clear_400(similarity_client, limit):
    response = similarity_client.get(
        f"/api/planets/{quote('11 Com b', safe='')}/similar?limit={limit}"
    )

    assert response.status_code == 400
    assert response.get_json()["error"]["code"] == "invalid_query_parameter"


def test_unknown_planet_has_a_json_404(similarity_client):
    response = similarity_client.get("/api/planets/no-such-world/similar")

    assert response.status_code == 404
    assert response.get_json()["error"]["code"] == "not_found"


def test_planet_search_matches_a_host_star_name(similarity_client):
    response = similarity_client.get("/api/planets?search=11%20Com&page_size=10")

    assert response.status_code == 200
    records = response.get_json()["records"]
    assert records
    assert all("11 Com" in row["pl_name"] or "11 Com" in row["hostname"] for row in records)
    assert any(row["pl_name"] == "11 Com b" for row in records)
