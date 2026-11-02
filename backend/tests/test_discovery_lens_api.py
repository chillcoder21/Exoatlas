"""API tests for the precomputed Discovery Lens tables."""

from __future__ import annotations

import pytest

from backend.app import PROJECT_ROOT, create_app


@pytest.fixture(scope="module")
def client():
    app = create_app(PROJECT_ROOT)
    app.config.update(TESTING=True)
    with app.test_client() as test_client:
        yield test_client


def test_discovery_overview_reports_catalogue_and_host_counts(client):
    response = client.get("/api/discovery/overview")
    assert response.status_code == 200
    body = response.get_json()
    assert body["total_planet_records"] == 6_451
    assert body["number_of_discovery_methods"] == 11
    assert body["number_of_discovery_years"] == 34
    assert body["number_of_facilities"] == 73
    assert body["number_of_unique_host_systems"] == 4_847
    assert body["snapshot_date"] == "2026-10-30"
    assert body["source"]["download_timestamp"] == "Fri Oct 30 13:47:46 2026"
    assert len(body["methods"]) == 11
    assert next(row for row in body["methods"] if row["discovery_method"] == "Disk Kinematics")["planet_count"] == 1
    assert "not occurrence rates" in " ".join(body["limitations"])


def test_discovery_timeline_has_zero_1993_partial_2026_and_exact_method_filter(client):
    response = client.get("/api/discovery/timeline")
    assert response.status_code == 200
    body = response.get_json()
    assert [row["year"] for row in body["years"]] == list(range(1992, 2027))
    assert sum(row["total_planet_records"] for row in body["years"]) == 6_451
    assert next(row for row in body["years"] if row["year"] == 1993)["total_planet_records"] == 0
    assert next(row for row in body["years"] if row["year"] == 2026)["is_partial_year"] is True

    filtered = client.get("/api/discovery/timeline?method=Transit")
    assert filtered.status_code == 200
    filtered_body = filtered.get_json()
    assert filtered_body["selected_methods"] == ["Transit"]
    assert sum(row["selected_method_planet_records"] for row in filtered_body["years"]) == 4_785
    assert all([item["discovery_method"] for item in year["methods"]] == ["Transit"] for year in filtered_body["years"])


def test_discovery_distributions_include_counts_raw_values_and_signed_uncertainties(client):
    response = client.get(
        "/api/discovery/distributions?property=pl_rade&method=Transit&method=Disk%20Kinematics"
    )
    assert response.status_code == 200
    body = response.get_json()
    assert body["property"] == "pl_rade"
    assert body["unit"] == "Earth radii"
    assert body["axis_scale"] == "log"
    transit = next(item for item in body["distributions"] if item["discovery_method"] == "Transit")
    disk = next(item for item in body["distributions"] if item["discovery_method"] == "Disk Kinematics")
    assert transit["total_planet_records"] == 4_785
    assert transit["measured_count"] + transit["missing_count"] == 4_785
    assert transit["uncertainty_count"] <= transit["measured_count"]
    assert len(transit["observations"]) == transit["measured_count"]
    assert disk["measured_count"] == 1
    assert disk["sample_size_warning"]["is_small"] is True
    assert len(disk["observations"]) == 1
    assert "hostname" in disk["observations"][0]
    assert "not independent" in body["host_independence_note"]
    assert transit["error_1_field"] == "pl_radeerr1"
    assert transit["error_2_field"] == "pl_radeerr2"
    assert "original err1 and err2" in body["uncertainty_note"]

    eccentricity = client.get("/api/discovery/distributions?property=pl_orbeccen").get_json()
    assert sum(item["zero_measurement_count"] for item in eccentricity["distributions"]) == 3_156


@pytest.mark.parametrize(
    "query",
    [
        "/api/discovery/distributions",
        "/api/discovery/distributions?property=pl_mass",
        "/api/discovery/distributions?property=pl_rade&method=transit",
        "/api/discovery/timeline?method=Unknown%20Method",
        "/api/discovery/facilities?methods=Transit,Unknown",
    ],
)
def test_discovery_endpoints_reject_invalid_properties_and_methods(client, query):
    response = client.get(query)
    assert response.status_code == 400
    body = response.get_json()
    assert body["error"]["code"] == "invalid_query_parameter"
    assert body["error"]["message"]


def test_facilities_counts_use_the_selected_scope_denominator(client):
    response = client.get("/api/discovery/facilities")
    assert response.status_code == 200
    body = response.get_json()
    assert body["facility_count"] == 73
    assert body["denominator_planet_records"] == 6_451
    assert sum(item["planet_count"] for item in body["facilities"]) == 6_451
    assert "independent surveys" in body["interpretation_note"]

    filtered = client.get("/api/discovery/facilities?method=Transit")
    assert filtered.status_code == 200
    filtered_body = filtered.get_json()
    assert filtered_body["scope"] == ["Transit"]
    assert filtered_body["denominator_planet_records"] == 4_785
    assert sum(item["planet_count"] for item in filtered_body["facilities"]) == 4_785


def test_legacy_discovery_summary_contract_remains_available(client):
    response = client.get("/api/discovery/summary")
    assert response.status_code == 200
    body = response.get_json()
    assert body["overall_counts"]["Transit"] == 4_785
    assert len(body["primary_cluster_composition"]) == 4
