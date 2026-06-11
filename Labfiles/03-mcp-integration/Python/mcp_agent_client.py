"""
MCP Inventory Agent Client.

Connects the local FastMCP inventory server to a Microsoft Foundry agent and
returns chat responses for the Flask interface.
"""

import asyncio
import os
import sys
import threading
from contextlib import AsyncExitStack
from pathlib import Path

from dotenv import load_dotenv
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


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
        with self._lock:
            return asyncio.run(self._send_message_async(user_message))

    def reset_conversation(self) -> None:
        """Clear the local chat history."""
        with self._lock:
            self.conversation_history = []

    async def _connect_to_server(self, exit_stack: AsyncExitStack) -> ClientSession:
        server_params = StdioServerParameters(
            command=sys.executable,
            args=[str(SERVER_PATH)],
            env=None,
        )

        stdio_transport = await exit_stack.enter_async_context(stdio_client(server_params))
        stdio, write = stdio_transport

        session = await exit_stack.enter_async_context(ClientSession(stdio, write))
        await session.initialize()
        return session

    async def _send_message_async(self, user_message: str) -> str:
        async with AsyncExitStack() as exit_stack:
            session = await self._connect_to_server(exit_stack)
            tools = (await session.list_tools()).tools
            return "Connected to MCP tools: " + ", ".join(tool.name for tool in tools)