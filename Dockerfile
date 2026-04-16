FROM python:3.11-slim
WORKDIR /app
# Install dependencies for the P2P node
RUN pip install --no-cache-dir flask flask-cors requests
# Copy node application
COPY node.py .
RUN mkdir -p /app/storage
EXPOSE 5000
CMD ["python", "node.py"]
