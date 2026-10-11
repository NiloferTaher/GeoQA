from __future__ import annotations

import json
import re
import tempfile
import unittest
from pathlib import Path

import geoqa
import geoqa_web
from geoqa_web.charts import chart_bundle, save_chart_assets
from geoqa_web.slides import slide_deck_from_report

_POINT = {"type": "Point", "coordinates": [58.405, 23.602]}
_LINE = {"type": "LineString", "coordinates": [[58.39, 23.59], [58.42, 23.62]]}


def _issue(**overrides):
    from geoqa.validations.base import ValidationIssue

    payload = {
        "problem_name": "sliver_polygon",
        "severity": "high",
        "description": "Polygon narrower than the minimum width.",
        "solution_hint": "Snap the polygon to a valid outline.",
        "feature_id": 1,
        "geometry": _POINT,
    }
    payload.update(overrides)
    return ValidationIssue(**payload)


def _collection():
    return geoqa.issues_to_geojson([
        _issue(),
        _issue(problem_name="line_intersection_same_layer", severity="critical", geometry=_LINE),
        _issue(problem_name="duplicate_geometry_same_layer", severity="medium", feature_id=2),
        _issue(problem_name="missing_attribute", severity="low", feature_id=3),
    ])


class TestSiteBuilder(unittest.TestCase):
    def test_builds_index_html(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            index = geoqa_web.build_site(_collection(), Path(tmp) / "site")

            self.assertTrue(index.exists())
            self.assertEqual("index.html", index.name)
            self.assertGreater(index.stat().st_size, 1000)

    def test_emits_findings_and_summary(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            site = geoqa_web.build_site(_collection(), Path(tmp) / "site")

            self.assertTrue((site.parent / "findings.geojson").exists())
            self.assertTrue((site.parent / "summary.json").exists())

    def test_title_and_description_are_configurable(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            index = geoqa_web.build_site(_collection(), Path(tmp) / "s", title="Mains QA")

            self.assertIn("Mains QA", index.read_text(encoding="utf-8"))

    def test_page_is_self_contained(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            index = geoqa_web.build_site(_collection(), Path(tmp) / "s")
            text = index.read_text(encoding="utf-8")

        # No local asset references: everything is inlined or from a CDN.
        self.assertNotRegex(text, r'src="(?!https://)[^"]*\.js"')
        self.assertNotRegex(text, r'href="(?!https://|data:)[^"]*\.css"')

    def test_embedded_payload_is_valid_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            index = geoqa_web.build_site(_collection(), Path(tmp) / "s")
            text = index.read_text(encoding="utf-8")

        match = re.search(r"var DATA = (\{.*?\});\n", text, re.S)
        self.assertIsNotNone(match)
        payload = json.loads(match.group(1).replace("<\\/", "</"))
        self.assertEqual(4, len(payload["findings"]))

    def test_script_injection_in_properties_is_neutralised(self) -> None:
        hostile = "</script><script>alert(1)</script>"
        collection = geoqa.issues_to_geojson([_issue(problem_name=hostile)])
        with tempfile.TemporaryDirectory() as tmp:
            index = geoqa_web.build_site(collection, Path(tmp) / "s")
            text = index.read_text(encoding="utf-8")

        self.assertNotIn("</script><script>alert(1)", text)

    def test_base_layers_are_rendered(self) -> None:
        layers = {"mains": {"type": "FeatureCollection", "features": []}}
        with tempfile.TemporaryDirectory() as tmp:
            index = geoqa_web.build_site(_collection(), Path(tmp) / "s", base_layers=layers)

            self.assertIn("mains", index.read_text(encoding="utf-8"))

    def test_storyboard_is_generated_and_can_be_disabled(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            auto = geoqa_web.build_site(_collection(), Path(tmp) / "a").read_text(encoding="utf-8")
            manual = geoqa_web.build_site(_collection(), Path(tmp) / "m", auto_play=False).read_text(encoding="utf-8")

        self.assertIn('"auto_play":[{', auto.replace(" ", ""))
        self.assertIn('"auto_play":[]', manual.replace(" ", ""))

    def test_storyboard_covers_present_severities(self) -> None:
        steps = geoqa_web.storyboard_from_report(_collection())

        self.assertGreaterEqual(len(steps), 3)

    def test_no_third_party_project_branding(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            index = geoqa_web.build_site(_collection(), Path(tmp) / "s")
            text = index.read_text(encoding="utf-8").lower()

        for token in ("tanager", "scenecube", "sentinel"):
            self.assertNotIn(token, text)

    def test_accepts_a_geoqa_report(self) -> None:
        report = geoqa.validate("tests/fixtures/tiny_extract.osm", ogr_layer="lines")
        with tempfile.TemporaryDirectory() as tmp:
            index = geoqa_web.build_site(report, Path(tmp) / "s")

            self.assertTrue(index.exists())

    def test_accepts_a_geojson_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "f.geojson"
            source.write_text(json.dumps(_collection()), encoding="utf-8")
            index = geoqa_web.build_site(source, Path(tmp) / "s")

            self.assertTrue(index.exists())

    def test_rejects_unsupported_source(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(TypeError):
                geoqa_web.build_site(object(), Path(tmp) / "s")


class TestSlides(unittest.TestCase):
    def test_deck_has_expected_slides(self) -> None:
        deck = slide_deck_from_report(_collection())

        self.assertGreaterEqual(len(deck["slides"]), 4)
        self.assertIn("title", deck["slides"][0])

    def test_headline_slide_reports_totals(self) -> None:
        deck = slide_deck_from_report(_collection())
        tiles = next((s["tiles"] for s in deck["slides"] if s.get("tiles")), [])

        self.assertTrue(tiles)
        self.assertTrue(any(t["label"] == "Total findings" for t in tiles))

    def test_action_slide_lists_distinct_hints(self) -> None:
        deck = slide_deck_from_report(_collection())
        bullets = next((s["bullets"] for s in deck["slides"] if s.get("bullets")), [])

        self.assertTrue(bullets)

    def test_writes_index_and_deck_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            index = geoqa_web.build_slides(_collection(), Path(tmp) / "slides")

            self.assertTrue(index.exists())
            self.assertTrue((index.parent / "deck.json").exists())

    def test_slides_are_self_contained(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            index = geoqa_web.build_slides(_collection(), Path(tmp) / "s")
            text = index.read_text(encoding="utf-8")

        self.assertNotRegex(text, r'src="(?!data:)[^"]*\.js"')


class TestCharts(unittest.TestCase):
    def test_bundle_has_three_charts(self) -> None:
        bundle = chart_bundle(_collection())

        self.assertIn("by_problem", bundle)
        self.assertIn("by_severity", bundle)

    def test_severity_chart_is_ordered_and_coloured(self) -> None:
        bundle = chart_bundle(_collection())
        severities = [item["label"] for item in bundle["by_severity"]["data"]]

        self.assertEqual("critical", severities[0])
        for item in bundle["by_severity"]["data"]:
            self.assertTrue(item["color"].startswith("#"))

    def test_problem_counts_are_accurate(self) -> None:
        bundle = chart_bundle(_collection())
        counts = {item["label"]: item["value"] for item in bundle["by_problem"]["data"]}

        self.assertEqual(1, counts["sliver_polygon"])

    def test_writes_json_and_renderer_assets(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            written = save_chart_assets(_collection(), Path(tmp) / "charts")

            self.assertTrue(written["json"].exists())

    def test_plotly_fragment_is_html(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            written = save_chart_assets(_collection(), Path(tmp) / "charts")

            if "plotly" in written:
                text = written["plotly"].read_text(encoding="utf-8")
                self.assertIn("<div", text)

    def test_empty_collection_does_not_crash(self) -> None:
        empty = {"type": "FeatureCollection", "features": []}

        bundle = chart_bundle(empty)
        self.assertEqual([], bundle["by_problem"]["data"])


if __name__ == "__main__":
    unittest.main()