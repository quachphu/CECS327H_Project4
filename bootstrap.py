"""
Resources :
1. https://www.geeksforgeeks.org/system-design/peer-to-peer-p2p-architecture/
2. https://docs.docker.com/reference/samples/flask
2. https://flask.palletsprojects.com/en/stable/quickstart/ 
3. https://p2pnetsuite.github.io/P2PNet/misc/bootstrapserver.html
4. https://www.youtube.com/watch?v=Rvfs6Xx3Kww
5. Professor Lecture and assignments from CECS 327H
6. https://docs.docker.com/compose/how-tos/networking/ 
7. https://docs.docker.com/guides/python/containerize/
8. https://www.youtube.com/watch?v=mQ945KwuPjU 
"""

import time
import logging
from flask import Flask, request, jsonify
from flask_cors import CORS

app = Flask(__name__) # Resources : https://www.youtube.com/watch?v=Z1RJmh_OqeA  
CORS(app)  # I used this : https://www.youtube.com/watch?v=mQ945KwuPjU 


# Data Stores
registered_peers = {}
metrics_log = [] 
MAX_METRICS = 5000  # Cap to prevent memory bloat

logging.basicConfig(
    level=logging.INFO,
    format="[Bootstrap] %(asctime)s - %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("bootstrap")


# Helper: record a metric event
def record_metric(event, source="bootstrap", target=None, details=None):
    """Append a timestamped metric event to the log."""
    entry = {
        "timestamp": time.time(),
        "event": event,
        "source": source,
        "target": target,
        "details": details or {},
    }
    metrics_log.append(entry)
    # Trim if too large
    if len(metrics_log) > MAX_METRICS:
        metrics_log.pop(0)


# Peer Registration Endpoints
@app.route("/", methods=["GET"])
def index():
    """Health check endpoint."""
    return jsonify({
        "message": "Bootstrap node is running!",
        "registered_peers": len(registered_peers),
    })


@app.route("/register", methods=["POST"])
def register_peer():
    """Register a new peer node with the bootstrap."""
    data = request.get_json()
    if not data or "node_id" not in data or "url" not in data:
        return jsonify({"error": "Missing node_id or url"}), 400

    node_id = data["node_id"]
    url = data["url"]
    registered_peers[node_id] = {
        "url": url,
        "registered_at": time.time(),
    }
    logger.info(f"Registered peer: {node_id} at {url}  (total: {len(registered_peers)})")
    record_metric("peer_register", source=node_id, details={"url": url})

    return jsonify({"status": "registered", "node_id": node_id})


@app.route("/unregister", methods=["POST"])
def unregister_peer():
    """Remove a peer from the registry."""
    data = request.get_json()
    if not data or "node_id" not in data:
        return jsonify({"error": "Missing node_id"}), 400

    node_id = data["node_id"]
    if node_id in registered_peers:
        del registered_peers[node_id]
        logger.info(f"Unregistered peer: {node_id}  (total: {len(registered_peers)})")
        record_metric("peer_unregister", source=node_id)
    return jsonify({"status": "unregistered", "node_id": node_id})


@app.route("/peers", methods=["GET"])
def get_peers():
    """Return list of all registered peer URLs."""
    peer_list = [info["url"] for info in registered_peers.values()]
    return jsonify({"peers": peer_list})


@app.route("/peers/detailed", methods=["GET"])
def get_peers_detailed():
    """Return detailed peer info (id -> url + metadata)."""
    return jsonify({"peers": registered_peers})


# Metrics Endpoints (We chose Option 2: Visualization & Monitoring)
@app.route("/metrics", methods=["GET"])
def get_metrics():
    """Return all collected metrics for the dashboard."""
    since = request.args.get("since", 0, type=float)
    filtered = [m for m in metrics_log if m["timestamp"] > since]
    return jsonify({
        "metrics": filtered,
        "total_peers": len(registered_peers),
        "peer_ids": list(registered_peers.keys()),
    })


@app.route("/metrics/report", methods=["POST"])
def report_metric():
    """Accept metric reports from peer nodes."""
    data = request.get_json()
    if not data or "event" not in data:
        return jsonify({"error": "Missing event"}), 400

    record_metric(
        event=data["event"],
        source=data.get("source", "unknown"),
        target=data.get("target"),
        details=data.get("details", {}),
    )
    return jsonify({"status": "recorded"})


# Main
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
