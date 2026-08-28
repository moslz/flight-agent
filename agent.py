import json
import operator
from typing import Annotated

from typing_extensions import TypedDict
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver

import anthropic

from config import MODEL, MAX_TOKENS, load_system_prompt, load_tools
from flights import search_flights, FlightSearchError

_client = anthropic.Anthropic()
_system_prompt = load_system_prompt()
_tools = load_tools()

_TOOL_HANDLERS = {
    "search_flights": lambda args: search_flights(
        origin=args["origin"],
        destination=args["destination"],
        outbound_date=args["outbound_date"],
        trip_type=args.get("trip_type", "one_way"),
        return_date=args.get("return_date"),
        cabin_class=args.get("cabin_class", "economy"),
        passengers=args.get("passengers", 1),
    ),
}


def _dispatch_tool(name, args):
    handler = _TOOL_HANDLERS.get(name)
    if handler is None:
        return {"error": f"Unknown tool: {name}"}
    try:
        return handler(args)
    except FlightSearchError as exc:
        return {"error": str(exc)}


def _extract_text(content):
    return "".join(block.text for block in content if getattr(block, "type", None) == "text")


class AgentState(TypedDict):
    messages: Annotated[list, operator.add]


def call_model(state: AgentState) -> dict:
    response = _client.messages.create(
        model=MODEL,
        max_tokens=MAX_TOKENS,
        system=_system_prompt,
        tools=_tools,
        messages=state["messages"],
    )
    return {"messages": [{"role": "assistant", "content": response.content}]}

def route_after_model(state: AgentState) -> str:
    last_content = state["messages"][-1]["content"]
    has_tool_use = any(getattr(block, "type", None) == "tool_use" for block in last_content)
    return "action" if has_tool_use else END

def call_tool(state: AgentState) -> dict:
    last_content = state["messages"][-1]["content"]
    tool_use = next(b for b in last_content if b.type == "tool_use")
    result = _dispatch_tool(tool_use.name, tool_use.input)
    return {
        "messages": [{
            "role": "user",
            "content": [{
                "type": "tool_result",
                "tool_use_id": tool_use.id,
                "content": json.dumps(result),
            }],
        }]
    }

graph = StateGraph(AgentState)
graph.add_node("agent", call_model)
graph.add_node("action", call_tool)
graph.set_entry_point("agent")
graph.add_conditional_edges("agent", route_after_model, {"action": "action", END: END})
graph.add_edge("action", "agent")

_checkpointer = MemorySaver()
_compiled = graph.compile(checkpointer=_checkpointer)


def chat(user_message: str, thread_id: str) -> str:
    config = {"configurable": {"thread_id": thread_id}}
    result = _compiled.invoke(
        {"messages": [{"role": "user", "content": user_message}]},
        config=config,
    )
    return _extract_text(result["messages"][-1]["content"])

def get_history(thread_id: str) -> list:
    """Return the display-worthy messages for a thread: real user turns and
    Claude's final text replies, skipping the tool-call/tool-result plumbing."""
    config = {"configurable": {"thread_id": thread_id}}
    snapshot = _compiled.get_state(config)
    if not snapshot.values:
        return []

    history = []
    for msg in snapshot.values.get("messages", []):
        role, content = msg["role"], msg["content"]
        if role == "user" and isinstance(content, str):
            history.append({"role": "user", "content": content})
        elif role == "assistant":
            text = _extract_text(content)
            if text:
                history.append({"role": "agent", "content": text})
    return history 