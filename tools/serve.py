#!/usr/bin/env python3
"""Local, read-only single-payload server. Expose through Tailscale Serve, not the internet.
Not a production multi-tenant server. Does not serve directories or execute commands.
"""
from __future__ import annotations
import argparse
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit


def make_handler(file: Path):
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            if urlsplit(self.path).path != '/usage.json':
                self.send_error(404); return
            try:
                with file.open('rb') as handle:
                    content = handle.read(1_048_577)
                if len(content) > 1_048_576:
                    raise ValueError('Response too large')
                if not isinstance(json.loads(content), dict):
                    raise ValueError('Payload must be a JSON object')
            except (OSError, ValueError):
                self.send_error(503, 'No valid JSON payload available'); return
            self.send_response(200)
            self.send_header('Content-Type', 'application/json; charset=utf-8')
            self.send_header('Content-Length', str(len(content)))
            self.send_header('Cache-Control', 'no-store, max-age=0')
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.end_headers(); self.wfile.write(content)

        def log_message(self, format, *args):
            pass  # Avoid retaining URLs, query strings or reader addresses in logs.
    return Handler


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--file', type=Path, required=True)
    parser.add_argument('--port', type=int, default=8765)
    args = parser.parse_args()
    if not 1 <= args.port <= 65535:
        parser.error('Port must be 1..65535')
    server = ThreadingHTTPServer(('127.0.0.1', args.port), make_handler(args.file.resolve()))
    print(f'Only /usage.json is served, at http://127.0.0.1:{args.port}/usage.json')
    print('Keep running. Stop with Ctrl+C. This does not start a collector or wake the PC.')
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
