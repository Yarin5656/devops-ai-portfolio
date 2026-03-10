"""
Task 4 - CI/CD Pipeline Demo Application
A minimal Flask web service exposing a health-check endpoint.
"""

from flask import Flask, jsonify

app = Flask(__name__)


@app.route("/health", methods=["GET"])
def health():
    """Return service health status."""
    return jsonify({"status": "ok", "service": "task-4-cicd-pipeline"}), 200


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
