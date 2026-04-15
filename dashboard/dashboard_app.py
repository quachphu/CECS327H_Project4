"""
Dashboard Node — Option 2: Visualization & Monitoring
=======================================================
CECS 327 Project 4

Provides a web-based dashboard using Flask + Chart.js + D3.js that shows:
  - Active peers (real-time count and list)
  - Network graph (nodes and connections visualized with D3.js force layout)
  - Message traffic over time (Chart.js line chart)
  - Per-node metrics (files, KV entries, request counts)

The dashboard polls the bootstrap's /metrics endpoint and each node's
/status endpoint to build a live picture of the network.
"""

import os
import time
import logging
import threading
import requests as http_requests
from flask import Flask, render_template, jsonify
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

BOOTSTRAP_URL = os.environ.get("BOOTSTRAP_URL", "http://bootstrap:5000")
POLL_INTERVAL = int(os.environ.get("POLL_INTERVAL", 5))  # seconds

logging.basicConfig(
    level=logging.INFO,
    format="[Dashboard] %(asctime)s - %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("dashboard")

# ---------------------------------------------------------------------------
# Cached Network State (updated by background poller)
# ---------------------------------------------------------------------------
network_state = {
    "peers": {},        # node_id -> { url, status, files, kv_count, ... }
    "connections": [],  # list of { source, target } edges
    "traffic": [],      # time-series: { timestamp, event_count, ... }
    "metrics": [],      # raw metric events from bootstrap
    "last_update": 0,
}
state_lock = threading.Lock()


def poll_network():
    """
    Background thread that periodically polls bootstrap and each node
    to build a current snapshot of the network for the dashboard.
    """
    last_metric_ts = 0  # Track last fetched metric timestamp

    while True:
        try:
            # 1. Fetch peer list from bootstrap
            resp = http_requests.get(f"{BOOTSTRAP_URL}/peers/detailed", timeout=5)
            if resp.status_code == 200:
                peer_data = resp.json().get("peers", {})
            else:
                peer_data = {}

            # 2. Fetch metrics from bootstrap (only new events)
            resp = http_requests.get(
                f"{BOOTSTRAP_URL}/metrics",
                params={"since": last_metric_ts},
                timeout=5,
            )
            new_metrics = []
            if resp.status_code == 200:
                new_metrics = resp.json().get("metrics", [])
                if new_metrics:
                    last_metric_ts = new_metrics[-1]["timestamp"]

            # 3. Query each node's /status for detailed info
            peers_info = {}
            connections = []
            for node_id, info in peer_data.items():
                url = info["url"]
                node_status = {"url": url, "alive": False}
                try:
                    sr = http_requests.get(f"{url}/status", timeout=3)
                    if sr.status_code == 200:
                        status_data = sr.json()
                        node_status.update({
                            "alive": True,
                            "peers_count": status_data.get("peers_count", 0),
                            "files_count": status_data.get("files_count", 0),
                            "kv_count": status_data.get("kv_count", 0),
                            "files": status_data.get("files", []),
                            "kv_keys": status_data.get("kv_keys", []),
                            "request_count": status_data.get("request_count", {}),
                        })
                        # Build connection edges from this node's peer list
                        for peer_url in status_data.get("peers", []):
                            # Find the node_id for this peer_url
                            for pid, pinfo in peer_data.items():
                                if pinfo["url"] == peer_url:
                                    connections.append({"source": node_id, "target": pid})
                                    break
                except Exception:
                    pass  # Node is down or unreachable

                peers_info[node_id] = node_status

            # 4. Build traffic time-series entry
            now = time.time()
            event_counts = {}
            for m in new_metrics:
                evt = m.get("event", "unknown")
                event_counts[evt] = event_counts.get(evt, 0) + 1

            traffic_point = {
                "timestamp": now,
                "total_events": len(new_metrics),
                "event_breakdown": event_counts,
                "active_peers": sum(1 for p in peers_info.values() if p.get("alive")),
            }

            # 5. Update shared state
            with state_lock:
                network_state["peers"] = peers_info
                network_state["connections"] = connections
                network_state["metrics"].extend(new_metrics)
                # Keep only last 1000 metrics in memory
                if len(network_state["metrics"]) > 1000:
                    network_state["metrics"] = network_state["metrics"][-1000:]
                network_state["traffic"].append(traffic_point)
                # Keep last 100 traffic points
                if len(network_state["traffic"]) > 100:
                    network_state["traffic"] = network_state["traffic"][-100:]
                network_state["last_update"] = now

        except Exception as e:
            logger.warning(f"Poll error: {e}")

        time.sleep(POLL_INTERVAL)


# ---------------------------------------------------------------------------
# Dashboard Routes
# ---------------------------------------------------------------------------

@app.route("/")
def dashboard():
    """Serve the main dashboard HTML page."""
    return render_template("dashboard.html")


@app.route("/api/state")
def api_state():
    """Return the current network state as JSON for the dashboard frontend."""
    with state_lock:
        return jsonify(network_state)


@app.route("/api/peers")
def api_peers():
    """Return just the peer info."""
    with state_lock:
        return jsonify(network_state["peers"])


@app.route("/api/traffic")
def api_traffic():
    """Return the traffic time-series data."""
    with state_lock:
        return jsonify(network_state["traffic"])


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    logger.info("Starting dashboard poller...")

    # Launch background polling thread
    poller = threading.Thread(target=poll_network, daemon=True)
    poller.start()

    logger.info("Dashboard running at http://localhost:8080")
    app.run(host="0.0.0.0", port=8080)
