FROM python:3.11-slim

WORKDIR /app

# Install dependencies for the bootstrap node
RUN pip install --no-cache-dir flask flask-cors requests

# Copy bootstrap application
COPY bootstrap.py .

EXPOSE 5000

CMD ["python", "bootstrap.py"]
