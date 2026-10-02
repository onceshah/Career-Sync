"""
Lightweight localhost OAuth callback server.

Responsible only for receiving the OAuth callback and
returning the authorization code and state.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Optional
from urllib.parse import parse_qs, urlparse


@dataclass(slots=True)
class OAuthCallbackResult:
    code: str
    state: str


class OAuthCallbackServer:
    """
    Waits for a single OAuth callback from Google.
    """

    def __init__(
        self,
        host: str = "localhost",
        port: int = 8000,
    ):

        self.host = host
        self.port = port

        self._result: Optional[OAuthCallbackResult] = None
        self._event = threading.Event()

    def wait_for_callback(
        self,
        timeout: int = 300,
    ) -> OAuthCallbackResult:

        server = self

        class CallbackHandler(BaseHTTPRequestHandler):

            def do_GET(self):

                parsed = urlparse(self.path)

                if parsed.path != "/auth/callback":
                    self.send_error(404)
                    return

                params = parse_qs(parsed.query)

                code = params.get("code", [None])[0]
                state = params.get("state", [None])[0]

                if not code or not state:

                    self.send_response(400)
                    self.end_headers()

                    self.wfile.write(
                        b"Missing OAuth parameters."
                    )

                    return

                server._result = OAuthCallbackResult(
                    code=code,
                    state=state,
                )

                self.send_response(200)
                self.send_header(
                    "Content-Type",
                    "text/html",
                )
                self.end_headers()

                self.wfile.write(
                    b"""
                    <html>
                        <body>
                            <h2>Authentication Successful</h2>
                            <p>You may now close this window.</p>
                        </body>
                    </html>
                    """
                )

                server._event.set()

            def log_message(self, *_):
                return

        httpd = HTTPServer(
            (self.host, self.port),
            CallbackHandler,
        )

        thread = threading.Thread(
            target=httpd.handle_request,
            daemon=True,
        )

        thread.start()

        if not self._event.wait(timeout):

            httpd.server_close()

            raise TimeoutError(
                "Timed out waiting for OAuth callback."
            )

        httpd.server_close()

        return self._result