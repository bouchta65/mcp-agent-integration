"""
MCP Inventory Agent Client.

Connects the local FastMCP inventory server to a Microsoft Foundry agent and
returns chat responses for the Flask interface.
"""

import asyncio
import json
import logging
import os
import sys
import threading
import uuid
from contextlib import AsyncExitStack
from pathlib import Path
from typing import Any

from azure.ai.projects import AIProjectClient
from azure.ai.projects.models import FunctionTool, PromptAgentDefinition
from azure.identity import DefaultAzureCredential
from dotenv import load_dotenv
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from openai.types.responses.response_input_param import FunctionCallOutput


APP_DIR = Path(__file__).resolve().parent
SERVER_PATH = APP_DIR / "server.py"

load_dotenv(APP_DIR / ".env")

logger = logging.getLogger(__name__)


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
        user_history_item = {"role": "user", "content": user_message}
        self.conversation_history.append(user_history_item)

        agent = None
        agent_name = f"inventory-agent-ui-{uuid.uuid4().hex[:10]}"

        try:
            async with AsyncExitStack() as exit_stack:
                session = await self._connect_to_server(exit_stack)
                tools = (await session.list_tools()).tools

                functions_dict = {
                    tool.name: self._make_tool_func(session, tool.name)
                    for tool in tools
                }

                mcp_function_tools: list[FunctionTool] = []
                for tool in tools:
                    mcp_function_tools.append(
                        FunctionTool(
                            name=tool.name,
                            description=tool.description,
                            parameters={
                                "type": "object",
                                "properties": {},
                                "additionalProperties": False,
                            },
                            strict=True,
                        )
                    )

                with (
                    DefaultAzureCredential() as credential,
                    AIProjectClient(
                        endpoint=self.project_endpoint,
                        credential=credential,
                    ) as project_client,
                    project_client.get_openai_client() as openai_client,
                ):
                    try:
                        agent = project_client.agents.create_version(
                            agent_name=agent_name,
                            definition=PromptAgentDefinition(
                                model=self.model_deployment,
                                instructions=(
                                    "You are an inventory assistant. Use the available MCP tools "
                                    "to answer questions about inventory levels and weekly sales. "
                                    "Recommend restock if item inventory is below 10 and weekly "
                                    "sales are above 15. Recommend clearance if item inventory is "
                                    "above 20 and weekly sales are below 5."
                                ),
                                tools=mcp_function_tools,
                            ),
                        )

                        response = openai_client.responses.create(
                            input=self.conversation_history,
                            extra_body={
                                "agent_reference": {
                                    "name": agent.name,
                                    "type": "agent_reference",
                                }
                            },
                        )

                        while True:
                            tool_outputs = []
                            for item in response.output:
                                if item.type != "function_call":
                                    continue

                                required_function = functions_dict.get(item.name)
                                if required_function is None:
                                    continue

                                kwargs = json.loads(item.arguments or "{}")
                                output = await required_function(**kwargs)
                                tool_outputs.append(
                                    FunctionCallOutput(
                                        type="function_call_output",
                                        call_id=item.call_id,
                                        output=self._tool_result_text(output),
                                    )
                                )

                            if not tool_outputs:
                                break

                            response = openai_client.responses.create(
                                input=tool_outputs,
                                previous_response_id=response.id,
                                extra_body={
                                    "agent_reference": {
                                        "name": agent.name,
                                        "type": "agent_reference",
                                    }
                                },
                            )

                        assistant_message = response.output_text
                        self.conversation_history.append(
                            {"role": "assistant", "content": assistant_message}
                        )
                        self._trim_history()
                        return assistant_message
                    finally:
                        if agent is not None:
                            try:
                                project_client.agents.delete_version(
                                    agent_name=agent.name,
                                    agent_version=agent.version,
                                )
                            except Exception:
                                logger.exception("Failed to delete temporary agent version")

        except Exception as exc:
            if self.conversation_history and self.conversation_history[-1] == user_history_item:
                self.conversation_history.pop()
            logger.exception("Error communicating with MCP inventory agent")
            raise RuntimeError(
                "Unable to communicate with the MCP inventory agent. "
                "Check Azure authentication, .env values, and the local MCP server."
            ) from exc
    @staticmethod
    def _make_tool_func(session: ClientSession, tool_name: str):
        async def tool_func(**kwargs: Any):
            return await session.call_tool(tool_name, kwargs)

        tool_func.__name__ = tool_name
        return tool_func

    @staticmethod
    def _tool_result_text(output: Any) -> str:
        content = getattr(output, "content", None)
        if content:
            first_item = content[0]
            text = getattr(first_item, "text", None)
            if text is not None:
                return text
        return str(output)

    def _trim_history(self) -> None:
        user_message_count = sum(
            1
            for item in self.conversation_history
            if item.get("role") == "user"
        )

        while user_message_count > self.max_history:
            for index, item in enumerate(self.conversation_history):
                if item.get("role") == "user":
                    self.conversation_history.pop(index)
                    if (
                        index < len(self.conversation_history)
                        and self.conversation_history[index].get("role") == "assistant"
                    ):
                        self.conversation_history.pop(index)
                    user_message_count -= 1
                    break
