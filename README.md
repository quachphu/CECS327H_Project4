# CECS 327 — Group Project 4: Distribution and Scalability

**Course:** CECS 327 – Intro to Networks and Distributed Computing  
**Due:** May 2, 2026 at 11:55 PM

---

## Overview

This project extends the previous P2P network (Project 3) to support decentralized storage and retrieval via Docker containers. Each node can:

- **Phase 1:** Upload and download files from local storage
- **Phase 2:** Insert and query key-value pairs (in-memory store)
- **Phase 3:** Distribute storage using a SHA-1 based Distributed Hash Table (DHT)
- **Option 2 (Bonus):** Visualization & Monitoring dashboard with D3.js network graph, Chart.js traffic charts, and real-time metrics

---

## Architecture

```
                    ┌─────────────┐
                    │  Bootstrap   │   ← Central peer registry + metrics collector
                    │  :5000       │
                    └──────┬──────┘
           ┌───────────────┼───────────────┐
           │               │               │
     ┌─────┴─────┐  ┌─────┴─────┐  ┌─────┴─────┐
     │  Node-1    │  │  Node-2    │  │  Node-N    │
     │  :5001     │  │  :5002     │  │  :500N     │
     │            │  │            │  │            │
     │ • Files    │  │ • Files    │  │ • Files    │
     │ • KV Store │  │ • KV Store │  │ • KV Store │
     │ • DHT      │  │ • DHT      │  │ • DHT      │
     └────────────┘  └────────────┘  └────────────┘
           │               │               │
           └───────────────┼───────────────┘
                    ┌──────┴──────┐
                    │  Dashboard   │   ← Option 2: D3.js + Chart.js monitoring
                    │  :8080       │
                    └─────────────┘
```

### Components

| Component   | File                          | Description                                |
|-------------|-------------------------------|--------------------------------------------|
| Bootstrap   | `bootstrap.py`                | Peer registry, metrics collection          |
| Peer Node   | `node.py`                     | File storage, KV store, DHT routing        |
| Dashboard   | `dashboard/dashboard_app.py`  | Monitoring UI with D3.js + Chart.js        |
| Compose Gen | `generate_compose.py`         | Generates docker-compose.yml for N nodes   |
| Test Suite  | `test_network.py`             | Automated tests for all phases             |

---

## Prerequisites

- **Docker** (v20+) and **Docker Compose** (v2+)
- **Python 3.8+** (for running tests and generating compose file)
- Python packages: `pip install requests pyyaml`

---

## How to Build, Run, and Test

### Step 1: Generate docker-compose.yml

```bash
# Default: 5 nodes (change the number as needed)
python generate_compose.py 5
```

### Step 2: Build and start all containers

```bash
docker-compose up -d --build
```

### Step 3: Wait for nodes to register with bootstrap (~15 seconds)

```bash
sleep 15
```

### Step 4: Run the test suite

```bash
python test_network.py 5
```

### Step 5: Open the dashboard (Option 2)

Open **http://localhost:8080** in your browser to see:
- Real-time network graph showing all active peers and connections
- Message traffic chart updating over time
- Active peer list with file/KV counts per node
- Recent events log showing uploads, downloads, KV operations, and DHT forwards

---

## Manual Testing with curl

### Phase 1: File Upload & Download

```bash
# Upload a file to node-1
curl -F 'file=@mydoc.txt' http://localhost:5001/upload

# Download the file
curl http://localhost:5001/download/mydoc.txt -o mydoc_downloaded.txt

# List files on node-1
curl http://localhost:5001/files
```

### Phase 2: Key-Value Store

```bash
# Store a key-value pair
curl -X POST http://localhost:5001/kv \
     -H "Content-Type: application/json" \
     -d '{"key": "color", "value": "blue"}'

# Retrieve the value
curl http://localhost:5001/kv/color
```

### Phase 3: DHT Routing (automatic)

DHT routing happens transparently. When you upload a file or store a KV pair,
the receiving node computes the SHA-1 hash to determine the responsible node.
If the current node isn't responsible, it forwards the request automatically.

```bash
# Upload to node-1 — may be forwarded to node-3 by DHT
curl -F 'file=@mydata.csv' http://localhost:5001/upload
# Response shows: {"stored_on": "node-3", ...}

# Download from any node — DHT routes to the correct node
curl http://localhost:5002/download/mydata.csv
```

---

## Option 2: Visualization & Monitoring Dashboard

The dashboard at **http://localhost:8080** provides:

1. **Network Graph** (D3.js force-directed layout)
   - Each node shown as a circle with its ID
   - Edges represent known peer connections
   - Drag nodes to explore the topology
   - Color indicates alive (blue) vs. down (red)

2. **Traffic Chart** (Chart.js line chart)
   - Tracks total events and active peer count over time
   - Updates every 3 seconds

3. **Active Peers Panel**
   - Shows each node's status (ALIVE/DOWN)
   - Displays file count, KV count, and request totals

4. **Events Log**
   - Recent metric events: uploads, downloads, KV operations, DHT forwards
   - Color-coded by event type

### Metrics Architecture

Nodes report metrics to bootstrap's `/metrics/report` endpoint. The dashboard
polls `/metrics` and each node's `/status` to build the live view.

---

## Stopping the Network

```bash
docker-compose down
```

To also remove volumes (storage data):

```bash
docker-compose down -v
rm -rf storage/
```

---

## Project Structure

```
p2p-project4/
├── bootstrap.py              # Bootstrap node (peer registry + metrics)
├── node.py                   # P2P node (Phase 1, 2, 3 + metrics)
├── dashboard/
│   ├── dashboard_app.py      # Dashboard Flask app (Option 2)
│   └── templates/
│       └── dashboard.html    # Dashboard UI (D3.js + Chart.js)
├── Dockerfile                # Node container image
├── bootstrap.Dockerfile      # Bootstrap container image
├── dashboard.Dockerfile      # Dashboard container image
├── generate_compose.py       # Generates docker-compose.yml
├── docker-compose.yml        # Generated orchestration file
├── test_network.py           # Automated test suite
└── README.md                 # This file
```

---

## Team Contributions

| Member | Contributions |
|--------|---------------|
| [Name 1] | [Describe contributions] |
| [Name 2] | [Describe contributions] |
| [Name 3] | [Describe contributions] |

---

## Demonstration Video

[Insert YouTube/video link here]
