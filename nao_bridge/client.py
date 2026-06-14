"""Python 3 client for the nao_bridge server.

The bridge server runs inside the `naoqi` (Python 2.7) conda environment and
exposes NAOqi functionality (motion, speech, ...) over a local TCP socket as
JSON-RPC. This client lets a Python 3 process - e.g. an LLM/VLM agent - call
those functions with plain Python method calls and no NAOqi dependency:

    from nao_bridge.client import NaoBridgeClient

    nao = NaoBridgeClient(host="127.0.0.1", port=5050)
    nao.motion.go_to_posture(posture_name="StandInit")
    nao.speech.say(text="Hello from Python 3!")
    angles = nao.motion.get_joint_angles(joints=["HeadYaw", "HeadPitch"])
"""

import itertools
import socket

from .protocol import MessageStream


class NaoBridgeError(RuntimeError):
    """Raised when the bridge server reports an error for an RPC call."""


class _RemoteNamespace(object):
    """Turns `client.<namespace>.<method>(**kwargs)` into an RPC call."""

    def __init__(self, client, name):
        self._client = client
        self._name = name

    def __getattr__(self, method_name):
        if method_name.startswith("_"):
            raise AttributeError(method_name)

        full_name = "{0}.{1}".format(self._name, method_name)

        def call(**params):
            return self._client.call(full_name, **params)

        call.__name__ = str(method_name)
        return call


class NaoBridgeClient(object):
    """Connects to a running nao_bridge server.

    Each call opens a short-lived TCP connection, sends one JSON-RPC request
    and waits for the matching response, then closes the socket. This keeps
    the client simple and avoids stale-connection issues for the relatively
    low-frequency commands a robot control / LLM agent loop typically sends.
    """

    def __init__(self, host="127.0.0.1", port=5050, timeout=10.0):
        self.host = host
        self.port = port
        self.timeout = timeout
        self._ids = itertools.count(1)

        # Known namespaces, exposed as attributes for nice dot-call syntax.
        self.motion = _RemoteNamespace(self, "motion")
        self.speech = _RemoteNamespace(self, "speech")
        self.system = _RemoteNamespace(self, "system")

    def call(self, method, **params):
        """Call `<namespace>.<method>` on the bridge server.

        `method` should be e.g. "motion.go_to_posture". Equivalent to
        `self.motion.go_to_posture(**params)` but useful for methods that
        aren't in a known namespace, or for generic/LLM-driven dispatch.
        """
        sock = socket.create_connection((self.host, self.port), timeout=self.timeout)
        try:
            stream = MessageStream(sock)
            request_id = next(self._ids)
            stream.send_obj({"id": request_id, "method": method, "params": params})
            response = stream.recv_obj()
        finally:
            sock.close()

        if not response.get("ok", False):
            raise NaoBridgeError("{0}: {1}".format(method, response.get("error", "unknown error")))
        return response.get("result")
