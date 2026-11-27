import sys, os
sys.path.insert(0, os.path.dirname(__file__))
from http.server import BaseHTTPRequestHandler
from _common import _parse_vercel_request, _write_vercel_response, _make_vercel_handler, _error_response, _json_response, _load_config, _public_dataset, read_summary, _safe_data_path


def handle(request):
    if request.method == "OPTIONS":
        return _json_response({}, status=200)
    if request.method != "GET":
        return _json_response({"detail": "Method not allowed."}, status=405)

    try:
        config = _load_config()
        datasets = [_public_dataset(dataset) for dataset in config["datasets"]]
        check_names: set[str] = set()
        for dataset in config["datasets"]:
            try:
                summary = read_summary(_safe_data_path(dataset["report"]))
                check_names.update(str(name) for name in (summary.get("by_problem") or {}).keys())
            except Exception:
                pass
        stats = {
            "datasets": len(datasets),
            "checks": len(check_names),
            "issues": sum(int(dataset["issue_count"]) for dataset in datasets),
        }
        return _json_response({"datasets": datasets, "stats": stats})
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
