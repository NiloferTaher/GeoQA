import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from http.server import BaseHTTPRequestHandler
from _common import _parse_vercel_request, _write_vercel_response, _make_vercel_handler, _error_response, _json_response, _load_config, _dataset_or_404, _safe_data_path


def _geojson_response(relative_path: str):
    path = _safe_data_path(relative_path)
    return {
        "statusCode": 200,
        "headers": {
            "Content-Type": "application/geo+json",
            "Access-Control-Allow-Origin": "*",
        },
        "body": path.read_text(encoding="utf-8"),
    }


def _dataset_or_404_local(dataset_id: str, config: dict):
    for dataset in config["datasets"]:
        if dataset.get("id") == dataset_id:
            return dict(dataset)
    return None


def handle(request):
    if request.method == "OPTIONS":
        return _json_response({}, status=200)
    if request.method != "GET":
        return _json_response({"detail": "Method not allowed."}, status=405)

    dataset_id = request.query.get("id") or ""
    if not dataset_id:
        parts = request.path.strip("/").split("/")
        if len(parts) >= 3:
            dataset_id = parts[-2]
    if not dataset_id or dataset_id == "[id]":
        return _error_response("Dataset ID is required.", status=400)

    # Demo GeoJSON is served as a static asset by the frontend; the API does
    # not bundle the large demo files. Return 404 so the frontend falls back.
    return _error_response(f"Dataset {dataset_id} geojson is served statically.", status=404)

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
