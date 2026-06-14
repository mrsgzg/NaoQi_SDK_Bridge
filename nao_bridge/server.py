#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""nao_bridge server: exposes NAOqi (Python 2.7) over a local JSON-RPC socket.

Run this *inside* the `naoqi` conda environment (Python 2.7), with the NAOqi
Python SDK on PYTHONPATH (see ../run_server.sh). A Python 3 process - e.g. an
LLM/VLM agent running in the `python312` env - can then control NAO via
nao_bridge.client.NaoBridgeClient without needing the NAOqi SDK itself.

Protocol: one JSON object per line (see protocol.py). Requests look like:

    {"id": 1, "method": "motion.go_to_posture", "params": {"posture_name": "StandInit"}}

Responses look like:

    {"id": 1, "ok": true, "result": {"ok": true}}
    {"id": 1, "ok": false, "error": "..."}
"""

from __future__ import print_function

import argparse
import inspect
import threading

try:
    import SocketServer as socketserver  # Python 2
except ImportError:
    import socketserver  # Python 3 (server.py itself only targets py2.7, but keep this harmless)

from protocol import ConnectionClosed, MessageStream
from services.motion import MockMotionService, MotionService
from services.speech import MockSpeechService, SpeechService
from services.system_service import SystemService


# NAOqi ALProxy objects are not guaranteed to be safe under concurrent calls
# from multiple threads; serialize all dispatched calls with a single lock.
_DISPATCH_LOCK = threading.Lock()

# Proxies that must be available for the bridge to be useful at all.
_REQUIRED_PROXIES = ["ALMotion", "ALRobotPosture", "ALTextToSpeech"]

# Proxies that enable extra functionality but aren't strictly required.
_OPTIONAL_PROXIES = ["ALAnimatedSpeech", "ALSpeechRecognition", "ALMemory"]

try:
    _TEXT_TYPE = unicode  # noqa: F821 (py2 only)
except NameError:
    _TEXT_TYPE = None


def _to_native_strings(obj):
    """Recursively convert `unicode` -> `str` (UTF-8 bytes).

    json.loads() always returns `unicode` for strings (and dict keys) under
    Python 2.7, but the NAOqi Boost.Python bindings only accept `str` for
    ALValue String arguments - a `unicode` value is silently converted to
    ALValue Void instead, e.g. ALRobotPosture.goToPosture(u"StandInit", 0.5)
    fails with "conversion failure from Void to String". No-op on Python 3.
    """
    if _TEXT_TYPE is None:
        return obj
    if isinstance(obj, dict):
        return dict((_to_native_strings(k), _to_native_strings(v)) for k, v in obj.items())
    if isinstance(obj, list):
        return [_to_native_strings(v) for v in obj]
    if isinstance(obj, _TEXT_TYPE):
        return obj.encode("utf-8")
    return obj


def build_registry(args):
    if args.mock:
        registry = {
            "motion": MockMotionService(),
            "speech": MockSpeechService(),
        }
    else:
        from naoqi import ALProxy

        proxies = {}
        for name in _REQUIRED_PROXIES:
            proxies[name] = ALProxy(name, args.nao_ip, args.nao_port)

        for name in _OPTIONAL_PROXIES:
            try:
                proxies[name] = ALProxy(name, args.nao_ip, args.nao_port)
            except Exception as exc:
                print("[WARN] {0} unavailable: {1}".format(name, exc))
                proxies[name] = None

        registry = {
            "motion": MotionService(proxies),
            "speech": SpeechService(proxies),
        }

    registry["system"] = SystemService(registry)
    return registry


class RpcHandler(socketserver.BaseRequestHandler):
    def handle(self):
        stream = MessageStream(self.request)
        while True:
            try:
                request = stream.recv_obj()
            except ConnectionClosed:
                return
            except ValueError as exc:
                stream.send_obj({"id": None, "ok": False, "error": "bad request: {0}".format(exc)})
                continue

            response = self.server.dispatch(request)
            stream.send_obj(response)


class BridgeServer(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True

    def __init__(self, addr, registry):
        socketserver.ThreadingTCPServer.__init__(self, addr, RpcHandler)
        self.registry = registry

    def dispatch(self, request):
        request_id = request.get("id")
        method = request.get("method", "")
        params = request.get("params") or {}

        if "." not in method:
            return {"id": request_id, "ok": False, "error": "method must be '<namespace>.<name>', got: {0}".format(method)}

        namespace, _, name = method.partition(".")
        service = self.registry.get(namespace)
        if service is None:
            return {"id": request_id, "ok": False, "error": "unknown namespace: {0}".format(namespace)}

        if name.startswith("_"):
            return {"id": request_id, "ok": False, "error": "unknown method: {0}".format(method)}

        func = getattr(service, name, None)
        if func is None or not inspect.ismethod(func):
            return {"id": request_id, "ok": False, "error": "unknown method: {0}".format(method)}

        try:
            with _DISPATCH_LOCK:
                result = func(**_to_native_strings(params))
        except TypeError as exc:
            return {"id": request_id, "ok": False, "error": "bad arguments for {0}: {1}".format(method, exc)}
        except Exception as exc:
            return {"id": request_id, "ok": False, "error": "{0}: {1}".format(type(exc).__name__, exc)}

        return {"id": request_id, "ok": True, "result": result}


def parse_args():
    parser = argparse.ArgumentParser(description="NAO bridge server (NAOqi <-> JSON-RPC)")
    parser.add_argument("--nao-ip", default="192.168.1.100", help="NAO robot IP (ignored with --mock)")
    parser.add_argument("--nao-port", type=int, default=9559, help="NAOqi port (ignored with --mock)")
    parser.add_argument("--host", default="127.0.0.1", help="Address to bind the bridge server on")
    parser.add_argument("--port", type=int, default=5050, help="Port to bind the bridge server on")
    parser.add_argument("--mock", action="store_true", help="Run with mock services, no robot needed")
    return parser.parse_args()


def main():
    args = parse_args()
    registry = build_registry(args)
    server = BridgeServer((args.host, args.port), registry)

    print("[INFO] nao_bridge server listening on {0}:{1} (mock={2})".format(args.host, args.port, args.mock))
    if not args.mock:
        print("[INFO] connected to NAOqi at {0}:{1}".format(args.nao_ip, args.nao_port))

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[INFO] shutting down")
    finally:
        server.shutdown()
        server.server_close()


if __name__ == "__main__":
    main()
