import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from http.server import BaseHTTPRequestHandler
from _common import _parse_vercel_request, _write_vercel_response, _error_response, _json_response, _load_config, _public_dataset


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

    dataset_id = request.path.rstrip("/").rsplit("/", 1)[-1]
    if not dataset_id or dataset_id == "[id]":
        return _error_response("Dataset ID is required.", status=400)

    config = _load_config()
    dataset = _dataset_or_404_local(dataset_id, config)
    if dataset is None:
        return _error_response(f"Dataset {dataset_id} not found.", status=404)

    return _json_response(_public_dataset(dataset, include_summary=False))


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