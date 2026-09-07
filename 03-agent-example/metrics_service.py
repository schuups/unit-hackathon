"""A mock node-telemetry service -- stands in for the monitoring API that
another team runs (Prometheus, Redfish, whatever your site uses).

It is a separate process on purpose: the agent reaches it over HTTP, exactly
as it would reach the real thing, and you can curl it yourself to prove it is
not part of the agent.

    python3 metrics_service.py            # then: curl localhost:8088/metrics/nid02

    GET /nodes            every node, its partition and its state
    GET /metrics/<node>   live telemetry for one node
    GET /alerts           whatever is firing right now
"""
import json
import math
import random
import time
from http.server import BaseHTTPRequestHandler, HTTPServer

PORT = 8088

# node: (partition, state, base temperature C, base power W, base GPU util %)
NODES = {
    "nid01": ("normal",  "idle",     41, 190,  2),
    "nid02": ("gpu",     "alloc",    91, 605, 97),   # running hot for three days
    "nid03": ("gpu",     "alloc",    63, 480, 91),
    "nid04": ("gpu",     "alloc",    61, 470, 88),
    "nid05": ("gpu",     "alloc",    59, 455, 84),
    "nid06": ("normal",  "alloc",    52, 320, 12),
    "nid07": ("normal",  "alloc",    54, 335, 15),
    "nid08": ("prepost", "drained",  33, 110,  0),   # out for a DIMM replacement
}
THROTTLE_C = 85          # above this the GPUs clock down; see docs/


def sample(node):
    """Telemetry for one node. Drifts on every call, so it reads as live."""
    partition, state, temp, power, util = NODES[node]
    phase = sum(map(ord, node))                       # each node drifts differently
    wobble = math.sin(time.time() / 30 + phase)
    jitter = random.uniform(-0.8, 0.8)
    temp_c = round(temp + 2.5 * wobble + jitter, 1)
    return {
        "node": node,
        "partition": partition,
        "state": state,
        "temp_c": temp_c,
        "power_w": round(power + 25 * wobble + 4 * jitter),
        "gpu_util_pct": max(0, min(100, round(util + 3 * wobble))),
        "fan_rpm": round(3200 + 45 * (temp_c - 40)),
        "throttling": temp_c > THROTTLE_C,
        "sampled_at": time.strftime("%Y-%m-%d %H:%M:%S"),
    }


def alerts():
    out = []
    for node in NODES:
        m = sample(node)
        if m["throttling"]:
            out.append({"node": node, "severity": "warning", "alert": "thermal_throttling",
                        "detail": f"{m['temp_c']} C is above the {THROTTLE_C} C throttle point",
                        "since": "2026-09-04 02:10:00"})
        if m["state"] == "drained":
            out.append({"node": node, "severity": "info", "alert": "node_drained",
                        "detail": "scheduled hardware maintenance", "since": "2026-09-05 06:00:00"})
    return out


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/nodes":
            body = [{"node": n, "partition": p, "state": s} for n, (p, s, *_) in NODES.items()]
        elif self.path == "/alerts":
            body = alerts()
        elif self.path.startswith("/metrics/") and self.path[9:] in NODES:
            body = sample(self.path[9:])
        else:
            return self.reply(404, {"error": f"no such endpoint or node: {self.path}",
                                    "known_nodes": list(NODES)})
        self.reply(200, body)

    def reply(self, code, body):
        blob = json.dumps(body, indent=2).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(blob)))
        self.end_headers()
        self.wfile.write(blob)

    def log_message(self, fmt, *args):        # one tidy line per request, on stderr
        print(f"  metrics-api  {self.address_string()}  {fmt % args}", flush=True)


if __name__ == "__main__":
    print(f"node telemetry on http://127.0.0.1:{PORT}  (/nodes  /metrics/<node>  /alerts)", flush=True)
    HTTPServer(("127.0.0.1", PORT), Handler).serve_forever()
