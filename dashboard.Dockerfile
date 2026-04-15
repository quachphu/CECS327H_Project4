FROM python:3.11-slim

WORKDIR /app

# Install dependencies for the dashboard
RUN pip install --no-cache-dir flask flask-cors requests

# Copy dashboard application and templates
COPY dashboard/ .

EXPOSE 8080

CMD ["python", "dashboard_app.py"]
