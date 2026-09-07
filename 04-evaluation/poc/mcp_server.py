"""The four Service Desk tools, served over MCP on stdin/stdout.

This exists so the comparison is fair. OpenCode and Claude Code each ship their
own toolset -- read, edit, bash, grep, web fetch -- and those toolsets are not
the same. Compare them as they come and you learn that two different tool lists
behave differently, which nobody needed an evaluation to discover.

So both harnesses are handed exactly these four tools and nothing else, out of
the same `environment.py` the in-process baseline uses, against the same frozen
fixtures. What is left varying is the harness and the model, which is what the
question was.

There is no framework here either. An MCP stdio server is a program that reads
one JSON-RPC object per line and writes one back:

    -> {"method": "initialize", ...}          <- capabilities and a name
    -> {"method": "tools/list"}               <- the four schemas
    -> {"method": "tools/call", "params": {"name": "run_sql", ...}}
                                              <- whatever the function returned

Run it by hand to see that:

    echo '{"jsonrpc":"2.0","id":1,"method":"tools/list"}' | python3 mcp_server.py
"""
import json
import sys

from environment import DISPATCH, TOOL_SCHEMAS

PROTOCOL = "2025-06-18"
SERVER = {"name": "servicedesk", "version": "1.0.0"}


def tools():
    """The MCP shape of a tool differs from the OpenAI one only in spelling."""
    out = []
    for name, schema in TOOL_SCHEMAS.items():
        fn = schema["function"]
        out.append({"name": name, "description": fn["description"],
                    "inputSchema": fn["parameters"]})
    return out


def handle(msg):
    """Return a response dict, or None for a notification."""
    method, mid = msg.get("method"), msg.get("id")

    if method == "initialize":
        # Echo the client's protocol version back when it names one, so this
        # server does not have to be revised every time the spec moves.
        version = (msg.get("params") or {}).get("protocolVersion") or PROTOCOL
        return {"protocolVersion": version,
                "capabilities": {"tools": {"listChanged": False}},
                "serverInfo": SERVER}

    if method in ("notifications/initialized", "notifications/cancelled"):
        return None                                     # notifications get no reply

    if method == "ping":
        return {}

    if method == "tools/list":
        return {"tools": tools()}

    if method == "tools/call":
        params = msg.get("params") or {}
        name = params.get("name")
        args = params.get("arguments") or {}
        if name not in DISPATCH:
            return {"content": [{"type": "text", "text": f"No such tool: {name}"}],
                    "isError": True}
        try:
            result = DISPATCH[name](**args)
        except TypeError as e:
            return {"content": [{"type": "text", "text": f"Bad arguments: {e}"}],
                    "isError": True}
        except Exception as e:
            return {"content": [{"type": "text", "text": f"{type(e).__name__}: {e}"}],
                    "isError": True}
        # A refusal is a RESULT, not a transport error: the model is meant to
        # read it and adapt. Flagging it isError would hide it behind the
        # harness's own error handling, and the evaluation would never see how
        # the agent responded to being told no.
        return {"content": [{"type": "text", "text": result}]}

    if mid is None:
        return None
    return {"_error": {"code": -32601, "message": f"Method not found: {method}"}}


def main():
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except json.JSONDecodeError:
            continue

        result = handle(msg)
        if result is None or msg.get("id") is None:
            continue
        reply = {"jsonrpc": "2.0", "id": msg["id"]}
        if "_error" in result:
            reply["error"] = result["_error"]
        else:
            reply["result"] = result
        sys.stdout.write(json.dumps(reply) + "\n")
        sys.stdout.flush()


if __name__ == "__main__":
    main()
