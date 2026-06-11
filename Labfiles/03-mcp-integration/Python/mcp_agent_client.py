"""
MCP Inventory Agent Client.

Connects the local FastMCP inventory server to a Microsoft Foundry agent and
returns chat responses for the Flask interface.
"""

import os
import threading
from pathlib import Path

from dotenv import load_dotenv


APP_DIR = Path(__file__).resolve().parent
SERVER_PATH = APP_DIR / "server.py"

load_dotenv(APP_DIR / ".env")


class MCPInventoryAgentClient:
    """Client for chatting with an agent that can call local MCP tools."""

    def __init__(self) -> None:
        self.project_endpoint = os.getenv("PROJECT_ENDPOINT", "").strip()
        self.model_deployment = os.getenv("MODEL_DEPLOYMENT_NAME", "").strip()

        if not self.project_endpoint:
            raise ValueError("PROJECT_ENDPOINT not found in .env")
        if not self.model_deployment:
            raise ValueError("MODEL_DEPLOYMENT_NAME not found in .env")

        self.conversation_history: list[dict[str, str]] = []
        self.max_history = 3
        self._lock = threading.Lock()

    def send_message(self, user_message: str) -> str:
        """Send a message to the MCP-enabled agent and return text output."""
        raise RuntimeError("MCP agent chat is not wired yet")

    def reset_conversation(self) -> None:
        """Clear the local chat history."""
        with self._lock:
            self.conversation_history = []