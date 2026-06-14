"""Newline-delimited JSON message framing for the NAO bridge.

This module is imported by both the Python 2.7 server (server.py, running
in the `naoqi` conda env) and the Python 3 client (client.py). It only uses
features that behave identically on both interpreters: json, and bytes/str
handling via explicit encode/decode.
"""

import json


class ConnectionClosed(Exception):
    """Raised when the peer closes the connection."""


class MessageStream(object):
    """Wraps a connected TCP socket and exchanges one JSON object per line.

    Each message is a JSON document encoded as UTF-8 followed by a single
    '\\n'. json.dumps() with the default ensure_ascii=True never emits a
    literal newline, so '\\n' is a safe message separator.
    """

    def __init__(self, sock):
        self._sock = sock
        self._buf = b""

    def send_obj(self, obj):
        data = json.dumps(obj)
        if not isinstance(data, bytes):
            data = data.encode("utf-8")
        self._sock.sendall(data + b"\n")

    def recv_obj(self):
        while b"\n" not in self._buf:
            chunk = self._sock.recv(65536)
            if not chunk:
                raise ConnectionClosed("connection closed by peer")
            self._buf += chunk
        line, self._buf = self._buf.split(b"\n", 1)
        return json.loads(line.decode("utf-8"))

    def close(self):
        try:
            self._sock.close()
        except Exception:
            pass
