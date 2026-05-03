from __future__ import annotations

import json
import types
import unittest
from unittest import mock

import numpy as np

from geoai import jax_layer, qgis_layer


class JaxLayerTests(unittest.TestCase):
    def test_configure_backend_falls_back_to_numpy_when_jax_missing(self) -> None:
        def fake_import(name: str):
            if name in {"jax", "jax.numpy"}:
                raise ImportError(name)
            if name == "numpy":
                return np
            raise ImportError(name)

        with mock.patch("geoai.jax_layer.importlib.import_module", side_effect=fake_import):
            backend = jax_layer.configure_backend(prefer_jax=True)

        self.assertEqual(backend, "numpy")
        self.assertFalse(jax_layer.jax_available())

    def test_configure_backend_uses_jax_when_available(self) -> None:
        fake_jax = types.SimpleNamespace()

        def fake_import(name: str):
            if name == "jax":
                return fake_jax
            if name == "jax.numpy":
                return np
            if name == "numpy":
                return np
            raise ImportError(name)

        with mock.patch("geoai.jax_layer.importlib.import_module", side_effect=fake_import):
            backend = jax_layer.configure_backend(prefer_jax=True)
            result = jax_layer.pairwise_squared_distances([[0.0, 0.0]], [[3.0, 4.0]])

        self.assertEqual(backend, "jax")
        self.assertTrue(jax_layer.jax_available())
        self.assertEqual(np.asarray(result).tolist(), [[25.0]])


class QgisLayerTests(unittest.TestCase):
    def test_qgis_helpers_handle_missing_pyqgis(self) -> None:
        with mock.patch.object(qgis_layer, "HAS_PYQGIS", False):
            self.assertFalse(qgis_layer.is_pyqgis_available())
            with self.assertRaises(RuntimeError):
                qgis_layer.layer_to_feature_dicts(object())

    def test_qgis_helpers_convert_feature_like_objects(self) -> None:
        class FakeGeometry:
            def asJson(self) -> str:
                return json.dumps({"type": "Point", "coordinates": [10.0, 20.0]})

        class FakeField:
            def __init__(self, name: str) -> None:
                self._name = name

            def name(self) -> str:
                return self._name

        class FakeFeature:
            def geometry(self) -> FakeGeometry:
                return FakeGeometry()

            def fields(self) -> list[FakeField]:
                return [FakeField("name"), FakeField("score")]

            def attributes(self) -> list[object]:
                return ["site_a", 7]

            def id(self) -> int:
                return 11

        class FakeLayer:
            def getFeatures(self) -> list[FakeFeature]:
                return [FakeFeature()]

        features = qgis_layer.layer_to_feature_dicts(FakeLayer())
        self.assertEqual(features[0]["properties"]["name"], "site_a")
        self.assertEqual(features[0]["geometry"]["coordinates"], [10.0, 20.0])


if __name__ == "__main__":
    unittest.main()
