import sys, os
sys.path.insert(0, os.path.dirname(__file__))
from http.server import BaseHTTPRequestHandler
from _common import _parse_vercel_request, _write_vercel_response, _make_vercel_handler, _json_response, _options_response, _read_atlas_thermal_status


def handle(request):
    if request.method == "OPTIONS":
        return _options_response()
    if request.method != "GET":
        return _json_response({"detail": "Method not allowed."}, status=405)
    return _json_response(_read_atlas_thermal_status())

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
