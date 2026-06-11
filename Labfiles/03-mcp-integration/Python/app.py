"""
Flask interface for the MCP inventory agent lab.
"""

from flask import Flask, jsonify, render_template, request

from mcp_agent_client import MCPInventoryAgentClient


app = Flask(__name__, template_folder=".", static_folder="static")

AGENT_SETUP_MESSAGE = (
    "Your MCP inventory agent is not connected yet. "
    "Check Azure sign-in, PROJECT_ENDPOINT, and MODEL_DEPLOYMENT_NAME in your `.env` file, "
    "then restart this interface."
)

try:
    agent = MCPInventoryAgentClient()
except Exception as exc:
    print(f"Warning: Failed to initialize MCP inventory agent client: {exc}")
    agent = None


@app.route("/")
@app.route("/index.html")
def index():
    return render_template("index.html")


@app.route("/documentation.html")
def documentation():
    return render_template("documentation.html")


@app.route("/chat", methods=["POST"])
def chat():
    if not agent:
        return jsonify({"response": AGENT_SETUP_MESSAGE})

    data = request.json or {}
    user_message = data.get("message", "").strip()
    if not user_message:
        return jsonify({"error": "Message is required"}), 400

    response = agent.send_message(user_message)
    return jsonify({"response": response})


@app.route("/reset", methods=["POST"])
def reset():
    if agent:
        agent.reset_conversation()
    return jsonify({"status": "success"})


if __name__ == "__main__":
    app.run(debug=False, port=5001)