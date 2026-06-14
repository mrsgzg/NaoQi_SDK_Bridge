"""Introspection helpers exposed under the 'system' namespace."""

from __future__ import print_function

import inspect


class SystemService(object):
    """Lets a client discover what's available without reading the source."""

    def __init__(self, registry):
        self._registry = registry

    def ping(self):
        return {"pong": True}

    def list_methods(self):
        methods = {}
        for namespace, service in self._registry.items():
            if namespace == "system":
                continue
            names = []
            for name in dir(service):
                if name.startswith("_"):
                    continue
                attr = getattr(service, name)
                if inspect.ismethod(attr) or inspect.isfunction(attr):
                    names.append(name)
            methods[namespace] = sorted(names)
        return methods
