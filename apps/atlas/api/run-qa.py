import sys, os
sys.path.insert(0, os.path.dirname(__file__))
from http.server import BaseHTTPRequestHandler
from _common import (
    _parse_vercel_request,
    _write_vercel_response,
    _make_vercel_handler,
    _error_response,
    _json_response,
    _issue_overlay,
    _materialize_upload,
    _load_geoqa_runner,
    _read_atlas_thermal_status,
    _atlas_validation_error_message,
)


def handle(request):
    if request.method == "OPTIONS":
        return _json_response({}, status=200)
    if request.method != "POST":
        return _json_response({"detail": "Method not allowed."}, status=405)

    try:
        filename = request.query.get("filename", "upload")
        profile = request.query.get("profile", "generic_quick")
        layer = request.query.get("layer")
        data = request.body or b""
        if not data:
            return _error_response("Upload a GeoJSON FeatureCollection, CSV, OSM/PBF, or zipped Shapefile.")

        preflight_thermal = _read_atlas_thermal_status()
        if not preflight_thermal["can_run"]:
            return _json_response({"detail": preflight_thermal["message"]}, status=429)

        validate_dataset_with_profile = _load_geoqa_runner()

        import tempfile
        from pathlib import Path

        with tempfile.TemporaryDirectory(prefix="geoqa_atlas_run_") as temp_dir:
            upload_root = Path(temp_dir)
            dataset_path, note = _materialize_upload(data, filename, upload_root, layer)
            materialized_thermal = _read_atlas_thermal_status()
            if not materialized_thermal["can_run"]:
                return _json_response({"detail": materialized_thermal["message"]}, status=429)

            report_stem = upload_root / "atlas-upload-report"
            try:
                result = validate_dataset_with_profile(
                    dataset_path,
                    profile=profile,
                    output_format="json",
                    report_path=report_stem,
                    max_runtime_seconds=75.0,
                    max_issues=200,
                    thermal_profile="balanced",
                    prefer_high_priority=True,
                )
            except ValueError as exc:
                return _error_response(str(exc))
            except Exception as exc:
                return _error_response(_atlas_validation_error_message(exc), status=500)

            issues = [issue.to_dict() for issue in result.issues]
            report_path = Path(result.report_path) if result.report_path else None
            report = (
                __import__("json").loads(report_path.read_text(encoding="utf-8"))
                if report_path and report_path.exists()
                else {
                    "issue_count": len(issues),
                    "summary": result.summary,
                    "issues": issues,
                }
            )
            return _json_response({
                "profile": result.profile_name,
                "feature_count": result.feature_count,
                "issue_count": len(issues),
                "summary": result.summary,
                "thermal": result.thermal_summary or _read_atlas_thermal_status(),
                "issues": issues,
                "issue_overlay": _issue_overlay(issues),
                "report": report,
                "messages": [note, *result.messages],
                "completed": result.completed,
                "execution_status": result.execution_status,
                "operator_next_steps": result.operator_next_steps or [],
            })
    except ValueError as exc:
        return _error_response(str(exc))
    except Exception as exc:  # pragma: no cover
        return _error_response(str(exc), status=500)

class handler(BaseHTTPRequestHandler):
    def _dispatch(self):
        try:
            request = _parse_vercel_request(self)
            result = handle(request)
            _write_vercel_response(self, result)
        except Exception as exc:
            import traceback
            body = traceback.format_exc()
            self.send_response(500)
            self.send_header("Content-Type", "text/plain")
            self.send_header("Content-Length", str(len(body.encode())))
            self.end_headers()
            self.wfile.write(body.encode())

    def do_GET(self):
        self._dispatch()

    def do_POST(self):
        self._dispatch()

    def do_OPTIONS(self):
        self._dispatch()

    def log_message(self, *args, **kwargs):
        return
