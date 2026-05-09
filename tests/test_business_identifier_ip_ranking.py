"""
Tests for IP-aware Google Places ranking in BusinessIdentifier.
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch


PROJECT_PARENT = Path(__file__).resolve().parents[2]
if str(PROJECT_PARENT) not in sys.path:
    sys.path.insert(0, str(PROJECT_PARENT))

from chaos_tester.modules import business_identifier as bi_mod
from chaos_tester.modules.business_identifier import BusinessIdentifier


class _FakeResponse:
    def __init__(self, status_code=200, payload=None, text=""):
        self.status_code = status_code
        self._payload = payload or {}
        self.text = text

    def json(self):
        return self._payload


def _us_components(city: str, state: str):
    return [
        {"types": ["locality"], "shortText": city, "longText": city},
        {
            "types": ["administrative_area_level_1"],
            "shortText": state,
            "longText": state,
        },
    ]


def test_google_places_prefers_nearest_location_for_user_context():
    identifier = BusinessIdentifier(
        google_places_api_key="test-key",
        enable_ip_geolocation_fallback=False,
    )
    payload = {
        "places": [
            {
                "addressComponents": _us_components("New York", "NY"),
                "location": {"latitude": 40.7128, "longitude": -74.0060},
            },
            {
                "addressComponents": _us_components("Los Angeles", "CA"),
                "location": {"latitude": 34.0522, "longitude": -118.2437},
            },
        ]
    }

    with patch(
        "chaos_tester.modules.business_identifier.requests.post",
        return_value=_FakeResponse(200, payload),
    ) as mock_post:
        location = identifier._lookup_google_places(
            "Acme Inc",
            "acme.com",
            user_context={"lat": 34.05, "lng": -118.25, "country_code": "US"},
        )

    assert location == "Los Angeles, CA"
    req_payload = mock_post.call_args.kwargs["json"]
    assert req_payload["textQuery"] == "Acme Inc acme.com"
    assert "rankPreference" not in req_payload
    assert "locationBias" not in req_payload


def test_identify_cache_isolated_by_geo_bucket():
    bi_mod._identify_cache.clear()
    identifier = BusinessIdentifier(google_places_api_key="", enable_ip_geolocation_fallback=False)

    candidates = [
        {
            "name": "Acme Inc",
            "score": 9.5,
            "sources": ["title_tag"],
            "classification": "business",
        }
    ]

    with patch.object(identifier, "scrape_candidates", return_value=candidates), patch.object(
        identifier, "detect_sector", return_value="software"
    ), patch.object(
        identifier,
        "lookup_headquarters",
        side_effect=[("Los Angeles, CA", "google_places"), ("New York, NY", "google_places")],
    ) as mock_lookup:
        first = identifier.identify(
            "https://example.com",
            user_context={"lat": 34.05, "lng": -118.25},
        )
        second = identifier.identify(
            "https://example.com",
            user_context={"lat": 40.71, "lng": -74.00},
        )

    assert first["location"] == "Los Angeles, CA"
    assert second["location"] == "New York, NY"
    assert mock_lookup.call_count == 2


def test_google_places_uses_formatted_address_fallback_when_components_sparse():
    identifier = BusinessIdentifier(
        google_places_api_key="test-key",
        enable_ip_geolocation_fallback=False,
    )
    payload = {
        "places": [
            {
                "addressComponents": [],
                "formattedAddress": "123 Main St, Denver, CO 80202, USA",
                "location": {"latitude": 39.7392, "longitude": -104.9903},
            }
        ]
    }
    with patch(
        "chaos_tester.modules.business_identifier.requests.post",
        return_value=_FakeResponse(200, payload),
    ):
        location = identifier._lookup_google_places(
            "Example LLC",
            "example.com",
            user_context={"lat": 39.74, "lng": -104.99},
        )

    assert location == "Denver, CO"
