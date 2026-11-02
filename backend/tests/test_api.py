"""Integration tests for the read-only prepared-data Flask API."""

from __future__ import annotations

import json
from urllib.parse import quote

import pandas as pd
import pytest

from backend.app import PROJECT_ROOT, create_app


@pytest.fixture(scope="module")
def client():
    app = create_app(PROJECT_ROOT)
    app.config.update(TESTING=True)
    with app.test_client() as test_client:
        yield test_client


@pytest.fixture(scope="module")
def application_data():
    return pd.read_csv(PROJECT_ROOT / "data/processed/planets_application.csv", low_memory=False)


def test_health_reports_ready_data_and_counts(client):
    response = client.get("/api/health")
    assert response.status_code == 200
    body = response.get_json()
    assert body["status"] == "ok"
    assert body["data_ready"] is True
    assert body["dataset"] == {
        "total_planets": 6451,
        "assigned_planets": 5273,
        "unassigned_planets": 1178,
    }


def test_overview_counts(client):
    response = client.get("/api/overview")
    assert response.status_code == 200
    dataset = response.get_json()["dataset"]
    assert dataset["total_confirmed_planets"] == 6451
    assert dataset["with_primary_cluster_assignment"] == 5273
    assert dataset["without_cluster_assignment"] == 1178
    assert dataset["number_of_clusters"] == 4
    assert dataset["discovery_method_counts"]["Transit"] == 4785
    assert "source_sha256" in dataset


def test_planet_pagination_is_deterministic(client, application_data):
    response = client.get("/api/planets?page=2&page_size=2")
    assert response.status_code == 200
    body = response.get_json()
    assert body["pagination"] == {
        "page": 2,
        "page_size": 2,
        "total_records": 6451,
        "total_pages": 3226,
    }
    assert [record["pl_name"] for record in body["records"]] == application_data["pl_name"].iloc[2:4].tolist()


def test_planet_search_by_name(client):
    response = client.get("/api/planets?search=trappist-1&page_size=10")
    assert response.status_code == 200
    names = [record["pl_name"] for record in response.get_json()["records"]]
    assert names
    assert all("trappist-1" in name.casefold() for name in names)


def test_planet_filter_by_cluster(client):
    response = client.get("/api/planets?cluster_id=2&page_size=5")
    assert response.status_code == 200
    body = response.get_json()
    assert body["pagination"]["total_records"] == 2223
    assert all(record["cluster_id"] == 2 for record in body["records"])


def test_planet_filter_by_discovery_method(client):
    response = client.get("/api/planets?discovery_method=transit&page_size=4")
    assert response.status_code == 200
    body = response.get_json()
    assert body["pagination"]["total_records"] == 4785
    assert all(record["discoverymethod"] == "Transit" for record in body["records"])


@pytest.mark.parametrize(
    ("status", "expected_count"),
    [("assigned", 5273), ("unassigned", 1178)],
)
def test_planet_filter_by_assignment_status(client, status, expected_count):
    response = client.get(f"/api/planets?assignment_status={status}&page_size=1")
    assert response.status_code == 200
    body = response.get_json()
    assert body["pagination"]["total_records"] == expected_count
    assert all(record["assignment_status"] == status for record in body["records"])
    if status == "unassigned":
        assert body["records"][0]["cluster_id"] is None


def test_individual_planet_lookup_supports_encoded_stable_identifier(client):
    encoded_name = quote("11 Com b", safe="")
    response = client.get(f"/api/planets/{encoded_name}")
    assert response.status_code == 200
    body = response.get_json()
    assert body["record"]["pl_name"] == "11 Com b"
    assert body["record"]["hostname"] == "11 Com"
    assert body["record"]["pl_rade"] == pytest.approx(12.2)


def test_unknown_planet_returns_404(client):
    response = client.get("/api/planets/definitely-not-a-real-planet")
    assert response.status_code == 404
    assert response.get_json()["error"]["code"] == "not_found"


def test_unknown_endpoint_uses_json_error_envelope(client):
    response = client.get("/api/unknown")
    assert response.status_code == 404
    assert response.get_json()["error"]["code"] == "not_found"


def test_cluster_profiles_and_sizes(client):
    response = client.get("/api/clusters")
    assert response.status_code == 200
    body = response.get_json()
    assert body["cohort_size"] == 5273
    assert [cluster["cluster_id"] for cluster in body["clusters"]] == [0, 1, 2, 3]
    assert [cluster["planet_count"] for cluster in body["clusters"]] == [871, 1361, 2223, 818]
    assert body["clusters"][0]["physical_features"]["pl_rade"]["unit"] == "Earth radii"
    assert "descriptive sample statistics" in body["clusters"][0]["descriptive_summary"]


def test_cluster_member_pagination(client):
    response = client.get("/api/clusters/1?page=3&page_size=7")
    assert response.status_code == 200
    body = response.get_json()
    assert body["profile"]["cluster_id"] == 1
    assert body["members"]["pagination"]["total_records"] == 1361
    assert body["members"]["pagination"]["page"] == 3
    assert len(body["members"]["records"]) == 7
    assert all(row["cluster_id"] == 1 for row in body["members"]["records"])


def test_discovery_summary_is_descriptive_and_internally_consistent(client):
    response = client.get("/api/discovery/summary")
    assert response.status_code == 200
    body = response.get_json()
    assert body["overall_counts"]["Transit"] == 4785
    assert len(body["primary_cluster_composition"]) == 4
    for cluster in body["primary_cluster_composition"]:
        assert sum(item["planet_count"] for item in cluster["discovery_methods"]) == cluster["planet_count"]
        assert sum(item["percent_within_cluster"] for item in cluster["discovery_methods"]) == pytest.approx(100.0)
    assert "not causal" in body["interpretation_caveat"]


def test_model_metadata_has_primary_and_comparison_configurations_without_local_paths(client):
    response = client.get("/api/model")
    assert response.status_code == 200
    body = response.get_json()
    model = body["model"]
    assert model["model_id"] == "exoatlas-kmeans-with-temperature-k4"
    assert model["k"] == 4
    assert model["cohort_size"] == 5273
    assert model["ordered_features"] == [
        "log10_pl_rade",
        "log10_pl_orbper",
        "pl_eqt",
        "pl_orbeccen",
    ]
    assert model["standardized_input_columns"] == [
        "scaled_log10_pl_rade",
        "scaled_log10_pl_orbper",
        "scaled_pl_eqt",
        "scaled_pl_orbeccen",
    ]
    assert model["kmeans_configuration"]["n_init"] == 20
    assert len(body["comparison_configurations"]) == 4
    assert "not an established astronomical classification" in model["interpretation"]

    def has_path_key(value):
        if isinstance(value, dict):
            return any(key.casefold().endswith("path") or key in {"model_artifact", "assignment_file"} or has_path_key(item)
                       for key, item in value.items())
        if isinstance(value, list):
            return any(has_path_key(item) for item in value)
        return False

    assert not has_path_key(body)


def test_validation_summary_uses_saved_validation_findings(client):
    response = client.get("/api/validation/summary")
    assert response.status_code == 200
    body = response.get_json()
    assert body["silhouette"]["mean"] == pytest.approx(0.3412641721072896)
    assert body["stability"]["ari_mean"] == pytest.approx(0.9867440419256184)
    assert body["negative_silhouette"]["count"] == 119
    assert body["feature_configuration_sensitivity"]["adjusted_rand_index"] == pytest.approx(0.4562698687107592)
    assert body["discovery_method_association"]["common_expected_count_heuristic_met"] is False
    assert "does not show" in body["discovery_method_association"]["caveat"]


@pytest.mark.parametrize(
    "query",
    [
        "page=0",
        "page=abc",
        "page_size=101",
        "cluster_id=8",
        "cluster_id=1.5",
        "discovery_method=unknown-method",
        "assignment_status=pending",
    ],
)
def test_invalid_query_parameters_return_clear_400(client, query):
    response = client.get(f"/api/planets?{query}")
    assert response.status_code == 400
    body = response.get_json()
    assert body["error"]["code"] == "invalid_query_parameter"
    assert body["error"]["message"]


def test_application_dataset_has_all_unique_source_records_and_preserves_measurements(application_data):
    master = pd.read_csv(PROJECT_ROOT / "data/processed/planets_master.csv", low_memory=False)
    assert len(application_data) == 6451
    assert application_data["pl_name"].notna().all()
    assert application_data["pl_name"].is_unique
    assert application_data["pl_name"].tolist() == master["pl_name"].tolist()
    source_columns = [column for column in master.columns if column in application_data.columns]
    pd.testing.assert_frame_equal(
        application_data[source_columns],
        master[source_columns],
        check_dtype=False,
        check_exact=True,
    )
    assert application_data["cluster_id"].notna().sum() == 5273
    assert application_data["cluster_id"].isna().sum() == 1178
    assert application_data["assignment_status"].value_counts().to_dict() == {
        "assigned": 5273,
        "unassigned": 1178,
    }


def test_generated_registry_and_application_data_report_are_machine_readable():
    registry = json.loads((PROJECT_ROOT / "artifacts/clustering/model_registry.json").read_text(encoding="utf-8"))
    report = json.loads((PROJECT_ROOT / "data/metadata/application_data_report.json").read_text(encoding="utf-8"))
    assert registry["primary_model"]["cohort_size"] == 5273
    assert [item["k"] for item in registry["comparison_configurations"][:3]] == [2, 3, 5]
    assert report["dataset"]["assignment_status_counts"] == {"assigned": 5273, "unassigned": 1178}


def test_outlier_overview_uses_precomputed_scientific_report(client):
    response = client.get("/api/outliers/overview")
    assert response.status_code == 200
    body = response.get_json()
    assert body["summary"] == {
        "assigned_records": 5273,
        "catalogue_records": 6451,
        "negative_silhouette_records": 119,
        "unassigned_records": 1178,
    }
    assert body["distributions"]["silhouette"]["negative_count"] == 119
    assert sum(body["distributions"]["centroid_distance_percentile"]["histogram"].values()) == 5273
    assert body["method"]["model_fitting"] is False
    assert len(body["cluster_profiles"]) == 4


def test_outlier_observations_rank_by_within_cluster_percentile(client):
    response = client.get("/api/outliers/observations?percentile_min=90&page_size=20")
    assert response.status_code == 200
    body = response.get_json()
    records = body["records"]
    assert len(records) == 20
    assert body["pagination"]["total_records"] == 530
    percentiles = [record["cluster_distance_percentile"] for record in records]
    assert percentiles == sorted(percentiles, reverse=True)
    assert all(record["assignment_status"] == "assigned" for record in records)
    assert "not a universal anomaly threshold" in body["ranking_note"]


def test_outlier_observations_support_cluster_host_search_and_silhouette_sort(client):
    initial = client.get("/api/outliers/observations?percentile_min=90&page_size=1").get_json()["records"][0]
    host = initial["hostname"]
    filtered = client.get(
        f"/api/outliers/observations?percentile_min=0&cluster_id={initial['cluster_id']}"
        f"&search={quote(host)}&page_size=20"
    )
    assert filtered.status_code == 200
    assert all(row["hostname"] == host for row in filtered.get_json()["records"])
    assert all(row["cluster_id"] == initial["cluster_id"] for row in filtered.get_json()["records"])

    boundary = client.get("/api/outliers/observations?percentile_min=0&sort_by=silhouette&page_size=20")
    values = [row["silhouette_score"] for row in boundary.get_json()["records"]]
    assert values == sorted(values)
    assert values[0] < 0


def test_outlier_planet_detail_exposes_measurement_comparisons_and_frozen_context(client):
    observation = client.get("/api/outliers/observations?page_size=1").get_json()["records"][0]
    response = client.get(f"/api/outliers/planets/{quote(observation['pl_name'])}")
    assert response.status_code == 200
    body = response.get_json()
    assert body["record"]["pl_name"] == observation["pl_name"]
    assert body["diagnostics_available"] is True
    assert body["record"]["centroid_distance"] == pytest.approx(observation["centroid_distance"])
    assert len(body["feature_comparisons"]) == 4
    assert all(item["reference"] is not None for item in body["feature_comparisons"])
    assert body["feature_comparisons"][0]["unit"] == "Earth radii"


def test_unassigned_outlier_detail_has_no_fabricated_model_diagnostics(client, application_data):
    name = application_data.loc[application_data["assignment_status"] == "unassigned", "pl_name"].iloc[0]
    response = client.get(f"/api/outliers/planets/{quote(name)}")
    assert response.status_code == 200
    body = response.get_json()
    assert body["diagnostics_available"] is False
    assert body["record"]["centroid_distance"] is None
    assert body["record"]["silhouette_score"] is None
    assert body["cluster_profile"] is None
    assert all(item["relation"] is None and item["reference"] is None for item in body["feature_comparisons"])
    assert "outside the frozen four-feature" in body["unavailable_reason"]


@pytest.mark.parametrize(
    "query",
    ["percentile_min=-1", "percentile_min=101", "percentile_min=nan", "sort_by=distance", "page_size=101", "cluster_id=9"],
)
def test_outlier_observations_reject_invalid_filters(client, query):
    response = client.get(f"/api/outliers/observations?{query}")
    assert response.status_code == 400
    assert response.get_json()["error"]["code"] == "invalid_query_parameter"


def test_outlier_detail_unknown_identifier_returns_404(client):
    response = client.get("/api/outliers/planets/no%20such%20planet")
    assert response.status_code == 404

