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
"""

import os
import sys
import uuid
import time
import json
import hashlib
import logging
import threading
import requests as http_requests 
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from werkzeug.utils import secure_filename

# Configuration (via environment variables for Docker flexibility)
NODE_ID = os.environ.get("NODE_ID", str(uuid.uuid4())[:8])
NODE_PORT = int(os.environ.get("NODE_PORT", 5000))
BOOTSTRAP_URL = os.environ.get("BOOTSTRAP_URL", "http://bootstrap:5000")
NODE_HOST = os.environ.get("NODE_HOST", f"node-{NODE_ID}")
NODE_URL = f"http://{NODE_HOST}:{NODE_PORT}"
DISCOVERY_INTERVAL = int(os.environ.get("DISCOVERY_INTERVAL", 10))  # seconds
STORAGE_DIR = os.environ.get("STORAGE_DIR", "./storage")

# Application Setup
app = Flask(__name__)
CORS(app)

# Create local storage directory for file uploads (Phase 1)
os.makedirs(STORAGE_DIR, exist_ok=True)

# Peer storage: set of peer URLs 
peers = set()

# Message log for tracking communication
message_log = []

# Key-Value store: in-memory dictionary (Phase 2)
kv_store = {}

# Metrics counter for monitoring (Option 2)
request_count = {"upload": 0, "download": 0, "kv_put": 0, "kv_get": 0, "forwarded": 0}

logging.basicConfig(
    level=logging.INFO,
    format=f"[Node {NODE_ID}] %(asctime)s - %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(f"node-{NODE_ID}")


# Phase 3 helpers
def sha1_hash(key):
    return int(hashlib.sha1(key.encode()).hexdigest(), 16)


def get_sorted_node_list():
    all_urls = list(peers) + [NODE_URL]
    node_hashes = []
    for url in all_urls:
        h = sha1_hash(url)
        node_hashes.append((h, url))
    node_hashes.sort(key=lambda x: x[0])
    return node_hashes


def hash_key_to_node(key):
    key_hash = sha1_hash(key)
    ring = get_sorted_node_list()

    # Find the first node with hash >= key_hash 
    for node_hash, node_url in ring:
        if node_hash >= key_hash:
            return node_url

    # Wrap around: if no node hash >= key_hash, the first node is responsible
    return ring[0][1] if ring else NODE_URL


# Metrics Helper 
def report_metric(event, target=None, details=None):
    try:
        http_requests.post(
            f"{BOOTSTRAP_URL}/metrics/report",
            json={
                "event": event,
                "source": NODE_ID,
                "target": target,
                "details": details or {},
            },
            timeout=2,
        )
    except Exception:
        pass  


# Phase 1: File Upload & Download
@app.route("/upload", methods=["POST"])
def upload_file():
    if "file" not in request.files:
        return jsonify({"error": "No file part in request"}), 400

    file = request.files["file"]
    if file.filename == "":
        return jsonify({"error": "No file selected"}), 400

    filename = secure_filename(file.filename)

    # Phase 3: Check DHT routing 
    responsible = hash_key_to_node(f"file:{filename}")
    if responsible != NODE_URL:
        # Forward the upload to the responsible node
        logger.info(f"Forwarding file '{filename}' to responsible node: {responsible}")
        request_count["forwarded"] += 1
        report_metric("file_forward", target=responsible, details={"filename": filename})
        try:
            file.seek(0)
            resp = http_requests.post(
                f"{responsible}/upload",
                files={"file": (filename, file.read())},
                timeout=10,
            )
            return jsonify(resp.json()), resp.status_code
        except Exception as e:
            return jsonify({"error": f"Forwarding failed: {str(e)}"}), 502

    # This node is responsible save the file locally
    filepath = os.path.join(STORAGE_DIR, filename)
    file.save(filepath)
    request_count["upload"] += 1
    logger.info(f"Stored file: {filename} (size: {os.path.getsize(filepath)} bytes)")
    report_metric("file_upload", details={"filename": filename, "size": os.path.getsize(filepath)})

    return jsonify({
        "status": "uploaded",
        "filename": filename,
        "stored_on": NODE_ID,
    })


@app.route("/download/<filename>", methods=["GET"])
def download_file(filename):
    filepath = os.path.join(STORAGE_DIR, secure_filename(filename))
    # Check if we have the file locally
    if os.path.exists(filepath):
        request_count["download"] += 1
        report_metric("file_download", details={"filename": filename})
        return send_from_directory(STORAGE_DIR, secure_filename(filename))

    # Phase 3: Check DHT 
    responsible = hash_key_to_node(f"file:{filename}")
    if responsible != NODE_URL:
        logger.info(f"Redirecting download '{filename}' to: {responsible}")
        request_count["forwarded"] += 1
        report_metric("file_redirect", target=responsible, details={"filename": filename})
        try:
            resp = http_requests.get(f"{responsible}/download/{filename}", timeout=10)
            if resp.status_code == 200:
                return resp.content, 200, {"Content-Type": resp.headers.get("Content-Type", "application/octet-stream")}
            return jsonify({"error": "File not found on responsible node"}), 404
        except Exception as e:
            return jsonify({"error": f"Forwarding failed: {str(e)}"}), 502

    return jsonify({"error": "File not found"}), 404


@app.route("/files", methods=["GET"])
def list_files():
    """List all files stored on this node."""
    files = os.listdir(STORAGE_DIR)
    return jsonify({"node_id": NODE_ID, "files": files, "count": len(files)})


# Phase 2: Key-Value Store
@app.route("/kv", methods=["POST"])
def kv_put():
    data = request.get_json()
    if not data or "key" not in data or "value" not in data:
        return jsonify({"error": "Missing 'key' or 'value' in request body"}), 400

    key = data["key"]
    value = data["value"]

    # Phase 3: Check DHT routing 
    responsible = hash_key_to_node(key)
    if responsible != NODE_URL:
        # Forward the request to the responsible node
        logger.info(f"Forwarding KV PUT '{key}' to responsible node: {responsible}")
        request_count["forwarded"] += 1
        report_metric("kv_forward_put", target=responsible, details={"key": key})
        try:
            resp = http_requests.post(f"{responsible}/kv", json=data, timeout=5)
            return jsonify(resp.json()), resp.status_code
        except Exception as e:
            return jsonify({"error": f"Forwarding failed: {str(e)}"}), 502

    kv_store[key] = value
    request_count["kv_put"] += 1
    logger.info(f"Stored KV: {key} = {value}")
    report_metric("kv_put", details={"key": key})

    return jsonify({
        "status": "stored",
        "key": key,
        "value": value,
        "stored_on": NODE_ID,
    })


@app.route("/kv/<key>", methods=["GET"])
def kv_get(key):
    # Check if we have it locally first
    if key in kv_store:
        request_count["kv_get"] += 1
        report_metric("kv_get", details={"key": key, "found": True})
        return jsonify({
            "key": key,
            "value": kv_store[key],
            "stored_on": NODE_ID,
        })

    # Phase 3: Route to the responsible node
    responsible = hash_key_to_node(key)
    if responsible != NODE_URL:
        logger.info(f"Forwarding KV GET '{key}' to responsible node: {responsible}")
        request_count["forwarded"] += 1
        report_metric("kv_forward_get", target=responsible, details={"key": key})
        try:
            resp = http_requests.get(f"{responsible}/kv/{key}", timeout=5)
            return jsonify(resp.json()), resp.status_code
        except Exception as e:
            return jsonify({"error": f"Forwarding failed: {str(e)}"}), 502

    return jsonify({"error": f"Key '{key}' not found"}), 404


@app.route("/kv", methods=["GET"])
def kv_list():
    # List all key-value pairs stored on this node.
    return jsonify({
        "node_id": NODE_ID,
        "store": kv_store,
        "count": len(kv_store),
    })


# Peer Discovery & Management
@app.route("/", methods=["GET"])
def index():
    return jsonify({
        "message": f"Node {NODE_ID} is running!",
        "node_id": NODE_ID,
        "url": NODE_URL,
        "peers_count": len(peers),
        "files_count": len(os.listdir(STORAGE_DIR)),
        "kv_count": len(kv_store),
        "request_count": request_count,
    })


@app.route("/register", methods=["POST"])
def register_peer():
    data = request.get_json()
    if not data or "url" not in data:
        return jsonify({"error": "Missing 'url'"}), 400

    peer_url = data["url"]
    if peer_url != NODE_URL:
        peers.add(peer_url)
        logger.info(f"Registered peer: {peer_url}  (total peers: {len(peers)})")
    return jsonify({"status": "registered"})


@app.route("/peers", methods=["GET"])
def get_peers():
    return jsonify({"peers": list(peers)})


@app.route("/message", methods=["POST"])
def receive_message():
    data = request.get_json()
    if not data or "from" not in data or "body" not in data:
        return jsonify({"error": "Missing 'from' or 'body'"}), 400

    message_log.append({
        "from": data["from"],
        "body": data["body"],
        "timestamp": time.time(),
    })
    logger.info(f"Message from {data['from']}: {data['body']}")
    report_metric("message_received", target=NODE_ID, details={"from": data["from"]})
    return jsonify({"status": "received"})


@app.route("/messages", methods=["GET"])
def get_messages():
    """Return the message log for this node."""
    return jsonify({"messages": message_log})


# Node Status for Dashboard 
@app.route("/status", methods=["GET"])
def node_status():
    return jsonify({
        "node_id": NODE_ID,
        "url": NODE_URL,
        "peers": list(peers),
        "peers_count": len(peers),
        "files": os.listdir(STORAGE_DIR),
        "files_count": len(os.listdir(STORAGE_DIR)),
        "kv_keys": list(kv_store.keys()),
        "kv_count": len(kv_store),
        "request_count": request_count,
        "uptime": time.time(),
    })



def register_with_bootstrap():
    try:
        http_requests.post(
            f"{BOOTSTRAP_URL}/register",
            json={"node_id": NODE_ID, "url": NODE_URL},
            timeout=5,
        )
        logger.info(f"Registered with bootstrap at {BOOTSTRAP_URL}")
    except Exception as e:
        logger.warning(f"Failed to register with bootstrap: {e}")


def discover_peers_from_bootstrap():
    try:
        resp = http_requests.get(f"{BOOTSTRAP_URL}/peers", timeout=5)
        if resp.status_code == 200:
            peer_list = resp.json().get("peers", [])
            new_count = 0
            for url in peer_list:
                if url != NODE_URL and url not in peers:
                    peers.add(url)
                    new_count += 1
            if new_count > 0:
                logger.info(f"Discovered {new_count} new peers from bootstrap (total: {len(peers)})")
    except Exception:
        pass


def discover_peers_from_peers():
    new_count = 0
    for peer_url in list(peers):
        try:
            resp = http_requests.get(f"{peer_url}/peers", timeout=3)
            if resp.status_code == 200:
                their_peers = resp.json().get("peers", [])
                for url in their_peers:
                    if url != NODE_URL and url not in peers:
                        peers.add(url)
                        new_count += 1
        except Exception:
            pass  # Peer might be temporarily unavailable

    if new_count > 0:
        logger.info(f"Discovered {new_count} new peers via gossip (total: {len(peers)})")


def periodic_discovery():
    # Initial registration with bootstrap
    register_with_bootstrap()
    time.sleep(2)

    while True:
        discover_peers_from_bootstrap()
        discover_peers_from_peers()
        time.sleep(DISCOVERY_INTERVAL)


# Main Entry Point
if __name__ == "__main__":
    logger.info(f"Starting node {NODE_ID} at {NODE_URL}")
    logger.info(f"Storage directory: {STORAGE_DIR}")

    # Launch background peer discovery thread
    discovery_thread = threading.Thread(target=periodic_discovery, daemon=True)
    discovery_thread.start()

    app.run(host="0.0.0.0", port=NODE_PORT)
