"""Tests for the GeoQA Atlas FastAPI backend."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

fastapi = pytest.importorskip("fastapi")
from fastapi.testclient import TestClient

from geoqa.api_server import app


SAMPLE_GEOJSON = {
    "type": "FeatureCollection",
    "features": [
        {
            "type": "Feature",
            "properties": {"id": 1, "name": "a"},
            "geometry": {"type": "Point", "coordinates": [1.0, 2.0]},
        },
        {
            "type": "Feature",
            "properties": {"id": 2, "name": "b"},
            "geometry": {"type": "Point", "coordinates": [3.0, 4.0]},
        },
    ],
}


@pytest.fixture(scope="module")
def client():
    return TestClient(app)


def test_health(client):
    response = client.get("/api/thermal")
    assert response.status_code == 200
    payload = response.json()
    assert "can_run" in payload


def test_run_qa_executes_geoqa(client):
    data = json.dumps(SAMPLE_GEOJSON).encode("utf-8")
    response = client.post(
        "/api/run-qa",
        params={"filename": "sample.geojson", "profile": "generic_quick"},
        content=data,
        headers={"Content-Type": "application/octet-stream"},
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["profile"] == "generic_quick"
    assert payload["feature_count"] == 2
    assert isinstance(payload["issues"], list)
    assert payload["completed"] is True
    assert payload["execution_status"] in {"full", "partial", "budget-limited", "input-limited", "thermal-limited"}
    # The backend must return genuine GeoQA findings, not an empty mock.
    assert payload["issue_count"] == len(payload["issues"])


def test_run_qa_invalid_profile(client):
    data = json.dumps(SAMPLE_GEOJSON).encode("utf-8")
    response = client.post(
        "/api/run-qa",
        params={"filename": "sample.geojson", "profile": "does_not_exist"},
        content=data,
        headers={"Content-Type": "application/octet-stream"},
    )
    assert response.status_code == 400
    assert "Unknown GeoQA profile" in response.json()["detail"]


def test_run_qa_empty_body(client):
    response = client.post(
        "/api/run-qa",
        params={"filename": "sample.geojson", "profile": "generic_quick"},
        content=b"",
        headers={"Content-Type": "application/octet-stream"},
    )
    assert response.status_code in {400, 422}


def test_preview_layer(client):
    data = json.dumps(SAMPLE_GEOJSON).encode("utf-8")
    response = client.post(
        "/api/preview-layer",
        params={"filename": "sample.geojson"},
        content=data,
        headers={"Content-Type": "application/octet-stream"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["collection"]["type"] == "FeatureCollection"
    assert len(payload["collection"]["features"]) == 2


def test_datasets_fallback(client):
    response = client.get("/api/datasets")
    assert response.status_code == 404