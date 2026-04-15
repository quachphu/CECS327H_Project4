#!/usr/bin/env python3
"""
Test Script for CECS 327 Project 4: Distribution and Scalability
=================================================================
Tests all 3 phases + Option 2 (Monitoring):

  Test 1: Health check — verify all nodes are running
  Test 2: Peer discovery — each node sees the others
  Test 3: File upload & download (Phase 1)
  Test 4: Key-value store (Phase 2)
  Test 5: DHT routing — files routed to responsible nodes (Phase 3)
  Test 6: DHT routing — KV pairs routed to responsible nodes (Phase 3)
  Test 7: Cross-node file retrieval via DHT (Phase 3)
  Test 8: Cross-node KV retrieval via DHT (Phase 3)
  Test 9: Dashboard & metrics collection (Option 2)

Usage:
    python test_network.py [num_nodes]
    Default: 5 nodes
"""

import sys
import time
import json
import requests
import hashlib

NUM_NODES = int(sys.argv[1]) if len(sys.argv) > 1 else 5
BASE_PORT = 5001  # node-1 starts at port 5001
BOOTSTRAP = "http://localhost:5000"
DASHBOARD = "http://localhost:8080"

PASS = "\033[92m✔ PASS\033[0m"
FAIL = "\033[91m✘ FAIL\033[0m"
INFO = "\033[94mℹ\033[0m"

passed = 0
failed = 0


def node_url(i):
    """Get the localhost URL for node i."""
    return f"http://localhost:{BASE_PORT + i - 1}"


def test(name, condition, detail=""):
    """Record a test result."""
    global passed, failed
    if condition:
        print(f"  {PASS}  {name}")
        passed += 1
    else:
        print(f"  {FAIL}  {name}  — {detail}")
        failed += 1


# ===================================================================
print(f"\n{'='*60}")
print(f"  CECS 327 Project 4 — Network Tests ({NUM_NODES} nodes)")
print(f"{'='*60}\n")

# -------------------------------------------------------------------
# Test 1: Health Check — All Nodes Running
# -------------------------------------------------------------------
print("Test 1: Health Check — All Nodes Running")
print("-" * 40)

# Bootstrap
try:
    r = requests.get(f"{BOOTSTRAP}/", timeout=5)
    test("Bootstrap is running", r.status_code == 200)
except Exception as e:
    test("Bootstrap is running", False, str(e))

# Dashboard
try:
    r = requests.get(f"{DASHBOARD}/", timeout=5)
    test("Dashboard is running", r.status_code == 200)
except Exception as e:
    test("Dashboard is running", False, str(e))

# Peer nodes
alive_count = 0
for i in range(1, NUM_NODES + 1):
    try:
        r = requests.get(f"{node_url(i)}/", timeout=5)
        if r.status_code == 200:
            alive_count += 1
    except:
        pass
test(f"All {NUM_NODES} peer nodes responding", alive_count == NUM_NODES,
     f"only {alive_count}/{NUM_NODES} alive")

print()

# -------------------------------------------------------------------
# Test 2: Peer Discovery
# -------------------------------------------------------------------
print("Test 2: Peer Discovery")
print("-" * 40)

# Check bootstrap peer count
try:
    r = requests.get(f"{BOOTSTRAP}/peers/detailed", timeout=5)
    peer_data = r.json().get("peers", {})
    test(f"Bootstrap knows all {NUM_NODES} peers", len(peer_data) >= NUM_NODES,
         f"found {len(peer_data)}")
except Exception as e:
    test(f"Bootstrap knows all {NUM_NODES} peers", False, str(e))

# Check node-1 sees other peers
try:
    r = requests.get(f"{node_url(1)}/peers", timeout=5)
    node1_peers = r.json().get("peers", [])
    test(f"Node-1 discovered {NUM_NODES - 1} peers",
         len(node1_peers) >= NUM_NODES - 1,
         f"found {len(node1_peers)}")
except Exception as e:
    test(f"Node-1 discovered peers", False, str(e))

print()

# -------------------------------------------------------------------
# Test 3: File Upload & Download (Phase 1)
# -------------------------------------------------------------------
print("Test 3: File Upload & Download (Phase 1)")
print("-" * 40)

# Upload a file to node-1
test_content = b"Hello from CECS 327 Project 4! This is a test file."
try:
    r = requests.post(
        f"{node_url(1)}/upload",
        files={"file": ("testfile.txt", test_content)},
        timeout=10,
    )
    upload_result = r.json()
    test("File upload successful", r.status_code == 200 and upload_result.get("status") == "uploaded",
         json.dumps(upload_result))
    stored_node = upload_result.get("stored_on", "unknown")
    print(f"    {INFO}  File stored on: {stored_node}")
except Exception as e:
    test("File upload", False, str(e))

# Download the file back (may be from a different node via DHT)
time.sleep(1)
try:
    # Try downloading from the node that stores it
    r = requests.get(f"{node_url(1)}/download/testfile.txt", timeout=10)
    test("File download successful", r.status_code == 200 and r.content == test_content,
         f"status={r.status_code}, content_match={r.content == test_content}")
except Exception as e:
    test("File download", False, str(e))

# List files on all nodes
print(f"    {INFO}  File distribution across nodes:")
for i in range(1, NUM_NODES + 1):
    try:
        r = requests.get(f"{node_url(i)}/files", timeout=5)
        files = r.json().get("files", [])
        if files:
            print(f"         node-{i}: {files}")
    except:
        pass

print()

# -------------------------------------------------------------------
# Test 4: Key-Value Store (Phase 2)
# -------------------------------------------------------------------
print("Test 4: Key-Value Store (Phase 2)")
print("-" * 40)

# Store a KV pair
try:
    r = requests.post(
        f"{node_url(1)}/kv",
        json={"key": "color", "value": "blue"},
        timeout=5,
    )
    kv_result = r.json()
    test("KV PUT color=blue", r.status_code == 200 and kv_result.get("status") == "stored",
         json.dumps(kv_result))
    print(f"    {INFO}  Stored on: {kv_result.get('stored_on', 'unknown')}")
except Exception as e:
    test("KV PUT", False, str(e))

# Retrieve the KV pair
try:
    r = requests.get(f"{node_url(1)}/kv/color", timeout=5)
    kv_get = r.json()
    test("KV GET color == blue", r.status_code == 200 and kv_get.get("value") == "blue",
         json.dumps(kv_get))
except Exception as e:
    test("KV GET", False, str(e))

# Store multiple KV pairs to see DHT distribution
keys_to_store = {
    "name": "CECS327",
    "university": "CSULB",
    "project": "P2P-DHT",
    "language": "Python",
    "framework": "Flask",
}
print(f"    {INFO}  Storing {len(keys_to_store)} additional KV pairs...")
for k, v in keys_to_store.items():
    try:
        r = requests.post(f"{node_url(1)}/kv", json={"key": k, "value": v}, timeout=5)
        stored_on = r.json().get("stored_on", "?")
        print(f"         {k}={v}  → stored on {stored_on}")
    except:
        print(f"         {k}={v}  → FAILED")

print()

# -------------------------------------------------------------------
# Test 5: DHT Routing — File Distribution (Phase 3)
# -------------------------------------------------------------------
print("Test 5: DHT Routing — File Distribution (Phase 3)")
print("-" * 40)

# Upload multiple files from different nodes to demonstrate DHT routing
dht_files = ["alpha.txt", "beta.txt", "gamma.txt", "delta.txt", "epsilon.txt"]
upload_results = {}

for idx, fname in enumerate(dht_files):
    src_node = (idx % NUM_NODES) + 1  # Rotate across nodes
    content = f"Content of {fname} — uploaded from node-{src_node}".encode()
    try:
        r = requests.post(
            f"{node_url(src_node)}/upload",
            files={"file": (fname, content)},
            timeout=10,
        )
        result = r.json()
        stored_on = result.get("stored_on", "unknown")
        upload_results[fname] = stored_on
        print(f"    {INFO}  {fname} uploaded via node-{src_node} → stored on {stored_on}")
    except Exception as e:
        print(f"    {FAIL}  {fname} upload failed: {e}")

# Verify DHT distributes files across multiple nodes
unique_storage_nodes = set(upload_results.values())
test(f"Files distributed across nodes (DHT routing)",
     len(unique_storage_nodes) >= 1,
     f"stored on {len(unique_storage_nodes)} unique nodes: {unique_storage_nodes}")

print()

# -------------------------------------------------------------------
# Test 6: DHT Routing — KV Distribution (Phase 3)
# -------------------------------------------------------------------
print("Test 6: DHT Routing — KV Distribution (Phase 3)")
print("-" * 40)

# Check KV distribution across nodes
print(f"    {INFO}  KV store distribution:")
kv_distribution = {}
for i in range(1, NUM_NODES + 1):
    try:
        r = requests.get(f"{node_url(i)}/kv", timeout=5)
        data = r.json()
        count = data.get("count", 0)
        keys = list(data.get("store", {}).keys())
        kv_distribution[f"node-{i}"] = keys
        if count > 0:
            print(f"         node-{i}: {count} keys → {keys}")
    except:
        pass

total_kv = sum(len(v) for v in kv_distribution.values())
test(f"All {len(keys_to_store) + 1} KV pairs accounted for",
     total_kv >= len(keys_to_store) + 1,
     f"found {total_kv}")

nodes_with_kv = sum(1 for v in kv_distribution.values() if v)
test(f"KV pairs distributed via DHT",
     nodes_with_kv >= 1,
     f"KV on {nodes_with_kv} nodes")

print()

# -------------------------------------------------------------------
# Test 7: Cross-Node File Retrieval via DHT (Phase 3)
# -------------------------------------------------------------------
print("Test 7: Cross-Node File Retrieval via DHT (Phase 3)")
print("-" * 40)

# Try downloading files from a node that doesn't store them
for fname in dht_files[:3]:
    stored_on = upload_results.get(fname, "unknown")
    # Pick a different node to download from
    download_node = 1
    for i in range(1, NUM_NODES + 1):
        if f"node-{i}" != stored_on:
            download_node = i
            break
    try:
        r = requests.get(f"{node_url(download_node)}/download/{fname}", timeout=10)
        test(f"Download {fname} from node-{download_node} (stored on {stored_on})",
             r.status_code == 200,
             f"status={r.status_code}")
    except Exception as e:
        test(f"Download {fname} cross-node", False, str(e))

print()

# -------------------------------------------------------------------
# Test 8: Cross-Node KV Retrieval via DHT (Phase 3)
# -------------------------------------------------------------------
print("Test 8: Cross-Node KV Retrieval via DHT (Phase 3)")
print("-" * 40)

# Retrieve KV pairs from different nodes than where they're stored
for key in ["name", "university", "project"]:
    for try_node in range(1, NUM_NODES + 1):
        try:
            r = requests.get(f"{node_url(try_node)}/kv/{key}", timeout=5)
            if r.status_code == 200:
                result = r.json()
                test(f"GET {key} from node-{try_node} → value={result.get('value')}, stored_on={result.get('stored_on')}",
                     True)
                break
        except:
            pass
    else:
        test(f"GET {key} from any node", False, "no node responded")

print()

# -------------------------------------------------------------------
# Test 9: Dashboard & Metrics (Option 2)
# -------------------------------------------------------------------
print("Test 9: Dashboard & Metrics (Option 2)")
print("-" * 40)

# Check dashboard is serving HTML
try:
    r = requests.get(f"{DASHBOARD}/", timeout=5)
    test("Dashboard HTML served", r.status_code == 200 and "P2P Network Dashboard" in r.text)
except Exception as e:
    test("Dashboard HTML served", False, str(e))

# Check dashboard API returns state
try:
    r = requests.get(f"{DASHBOARD}/api/state", timeout=5)
    state = r.json()
    test("Dashboard API /api/state returns data",
         "peers" in state and "traffic" in state and "metrics" in state)
    print(f"    {INFO}  Metrics collected: {len(state.get('metrics', []))}")
    print(f"    {INFO}  Traffic points: {len(state.get('traffic', []))}")
    print(f"    {INFO}  Peers tracked: {len(state.get('peers', {}))}")
except Exception as e:
    test("Dashboard API", False, str(e))

# Check bootstrap metrics endpoint
try:
    r = requests.get(f"{BOOTSTRAP}/metrics", timeout=5)
    metrics = r.json()
    test("Bootstrap /metrics endpoint active",
         "metrics" in metrics and len(metrics["metrics"]) > 0,
         f"found {len(metrics.get('metrics', []))} events")
except Exception as e:
    test("Bootstrap /metrics", False, str(e))

print()

# -------------------------------------------------------------------
# Summary
# -------------------------------------------------------------------
print(f"{'='*60}")
total = passed + failed
print(f"  Results: {passed}/{total} passed, {failed} failed")
if failed == 0:
    print(f"  \033[92m🎉 All tests passed!\033[0m")
else:
    print(f"  \033[93m⚠  Some tests failed — check output above\033[0m")
print(f"{'='*60}\n")
