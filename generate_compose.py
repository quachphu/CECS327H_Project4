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
9. https://codezup.com/flask-app-deployment-on-docker-compose/
10. https://betterstack.com/community/guides/scaling-docker/docker-compose-getting-started/ 
"""

import sys
import yaml

NUM_NODES = int(sys.argv[1]) if len(sys.argv) > 1 else 5

compose = {
    "version": "3.8",
    "services": {},
    "networks": {
        "p2p-net": {
            "driver": "bridge",
        }
    },
}

# Bootstrap Node 
compose["services"]["bootstrap"] = {
    "build": {
        "context": ".",
        "dockerfile": "bootstrap.Dockerfile",
    },
    "container_name": "bootstrap",
    "ports": ["5000:5000"],
    "networks": ["p2p-net"],
    "restart": "unless-stopped",
}

# Dashboard Node — Option 2: Visualization & Monitoring
compose["services"]["dashboard"] = {
    "build": {
        "context": ".",
        "dockerfile": "dashboard.Dockerfile",
    },
    "container_name": "dashboard",
    "ports": ["8080:8080"],
    "environment": {
        "BOOTSTRAP_URL": "http://bootstrap:5000",
        "POLL_INTERVAL": "5",
    },
    "networks": ["p2p-net"],
    "depends_on": ["bootstrap"],
    "restart": "unless-stopped",
}

# Peer Nodes 
for i in range(1, NUM_NODES + 1):
    node_name = f"node-{i}"
    host_port = 5000 + i  

    compose["services"][node_name] = {
        "build": {
            "context": ".",
            "dockerfile": "Dockerfile",
        },
        "container_name": node_name,
        "ports": [f"{host_port}:5000"],
        "environment": {
            "NODE_ID": node_name,
            "NODE_PORT": "5000",
            "BOOTSTRAP_URL": "http://bootstrap:5000",
            "NODE_HOST": node_name,
            "DISCOVERY_INTERVAL": "10",
            "STORAGE_DIR": "/app/storage",
        },
        "volumes": [
            f"./storage/{node_name}:/app/storage",  # Persistent file storage
        ],
        "networks": ["p2p-net"],
        "depends_on": ["bootstrap"],
        "restart": "unless-stopped",
    }

# Write docker-compose.yml
with open("docker-compose.yml", "w") as f:
    yaml.dump(compose, f, default_flow_style=False, sort_keys=False)

print(f"Generated docker-compose.yml with bootstrap + dashboard + {NUM_NODES} peer nodes")
print(f"Bootstrap:http://localhost:5000")
print(f"Dashboard:http://localhost:8080")
for i in range(1, NUM_NODES + 1):
    print(f"  Node-{i}:     http://localhost:{5000 + i}")
