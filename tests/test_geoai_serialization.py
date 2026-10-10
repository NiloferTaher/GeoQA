from __future__ import annotations

import types
import unittest
from unittest import mock

from geoai import serialization


class SerializationTests(unittest.TestCase):
    def test_json_round_trip(self) -> None:
        obj = {"name": "GeoAI", "values": [1, 2, 3], "nested": {"ok": True}}
        data = serialization.serialize(obj, format="json")
        restored = serialization.deserialize(data, format="json")
        self.assertEqual(restored, obj)

    def test_toon_round_trip_with_backend(self) -> None:
        fake_backend = types.SimpleNamespace(
            dumps=lambda obj: "TOON:" + serialization.serialize(obj, format="json"),
            loads=lambda data: serialization.deserialize(data.removeprefix("TOON:"), format="json"),
        )
        with mock.patch.object(serialization, "_TOON_BACKEND", fake_backend):
            obj = {"prompt": "compact", "tokens": 42}
            data = serialization.serialize(obj, format="toon")
            restored = serialization.deserialize(data, format="toon")
        self.assertEqual(data.startswith("TOON:"), True)
        self.assertEqual(restored, obj)

    def test_toon_falls_back_to_json_when_backend_missing(self) -> None:
        obj = {"geometry": {"type": "Point", "coordinates": [1, 2]}}
        with mock.patch.object(serialization, "_TOON_BACKEND", None):
            data = serialization.serialize(obj, format="toon")
            restored = serialization.deserialize(data, format="toon")
        self.assertEqual(restored, obj)
        self.assertTrue(data.startswith("{"))


if __name__ == "__main__":
    unittest.main()
