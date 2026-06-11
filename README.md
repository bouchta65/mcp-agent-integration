# MCP Agent Integration

A Python lab project that demonstrates how to connect Microsoft Foundry agents with Model Context Protocol (MCP) tools.

This project includes a local FastMCP server, a command-line MCP client, a remote MCP agent sample, and a Flask web interface for chatting with an inventory assistant.

## Features

- Local MCP server built with FastMCP
- MCP tools for inventory levels and weekly sales
- Microsoft Foundry agent integration
- Function tool bridge between MCP tools and the agent
- Flask chat interface
- GitHub Pages-friendly HTML interface
- Instruction page for the MCP lab

## Project Structure

```text
mcp-agent-integration/
├── index.html
├── documentation.html
├── Labfiles/
│   └── 03-mcp-integration/
│       └── Python/
│           ├── app.py
│           ├── agent.py
│           ├── client.py
│           ├── server.py
│           ├── mcp_agent_client.py
│           ├── requirements.txt
│           └── static/
│               ├── style.css
│               └── script.js
└── Instructions/
    └── Exercises/
        └── 03-mcp-integration.md
