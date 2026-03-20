#!/usr/bin/env python3
"""Read `railway status --json` on stdin; print backend service name then frontend (one per line).

Matches Railway service instances whose latest deployment meta has rootDirectory
\"backend\" or \"frontend\". Falls back to Backend / Frontend if not found.
"""
from __future__ import annotations

import json
import sys


def main() -> None:
    data = json.load(sys.stdin)
    by_root: dict[str, str] = {}

    for env_edge in data.get("environments", {}).get("edges", []):
        node = env_edge.get("node") or {}
        for si_edge in node.get("serviceInstances", {}).get("edges", []):
            sn = si_edge.get("node") or {}
            name = sn.get("serviceName")
            dep = sn.get("latestDeployment") or {}
            meta = dep.get("meta") or {}
            root = meta.get("rootDirectory")
            if name and root and root not in by_root:
                by_root[str(root)] = str(name)

    backend = by_root.get("backend", "Backend")
    frontend = by_root.get("frontend", "Frontend")
    sys.stdout.write(f"{backend}\n{frontend}\n")


if __name__ == "__main__":
    main()
