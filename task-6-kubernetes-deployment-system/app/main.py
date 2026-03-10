import os
from flask import Flask, jsonify

app = Flask(__name__)

SERVICE_NAME = os.environ.get("SERVICE_NAME", "task-6-web-service")
VERSION = os.environ.get("APP_VERSION", "1.0.0")


@app.route("/")
def index():
    return jsonify({
        "service": SERVICE_NAME,
        "version": VERSION,
        "status": "running",
        "description": "Task 6 - Kubernetes Deployment System"
    })


@app.route("/health")
def health():
    return jsonify({"status": "healthy"}), 200


@app.route("/ready")
def ready():
    return jsonify({"status": "ready"}), 200


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)
