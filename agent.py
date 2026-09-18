import json
import operator
from typing import Annotated

from typing_extensions import TypedDict
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver
from langgraph.types import interrupt, Command

import anthropic

from config import MODEL, MAX_TOKENS, load_system_prompt, load_tools
from flights import search_flights, get_booking_options, FlightSearchError
from budget_search import search_budget_carriers

_client = anthropic.Anthropic()
_system_prompt = load_system_prompt()
_tools = load_tools()

SEARCH_TOOLS = {
    "google_flights": {
        "label": "Google Flights",
        "description": (
            "Live prices, times, and direct booking links via SerpAPI. Best "
            "for major and legacy carriers; often misses budget airlines "
            "like Pegasus or Wizz Air."
        ),
    },
    "budget_deeplink": {
        "label": "Skyscanner (budget carriers)",
        "description": (
            "A direct search link for this route and date, not live data in "
            "this chat. Slower to check, but this is where low-cost carriers "
            "Google Flights misses actually show up."
        ),
    },
}

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
    "search_budget_carriers": lambda args: search_budget_carriers(
        origin=args["origin"],
        destination=args["destination"],
        outbound_date=args["outbound_date"],
        trip_type=args.get("trip_type", "one_way"),
        return_date=args.get("return_date"),
        cabin_class=args.get("cabin_class", "economy"),
        passengers=args.get("passengers", 1),
    ),
    "get_booking_options": lambda args: get_booking_options(
        booking_token=args["booking_token"],
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
        result = handler(args)
        print(f"[TOOL LOG] {name}({args}) -> {result}")
        return result
    except FlightSearchError as exc:
        print(f"[TOOL LOG] {name}({args}) -> FlightSearchError: {exc}")
        return {"error": str(exc)}
    except (KeyError, TypeError, ValueError) as exc:
        print(f"[TOOL LOG] {name}({args}) -> {type(exc).__name__}: {exc}")
        return {"error": f"Could not process this request: {exc}"}


def _extract_text(content):
    return "".join(block.text for block in content if getattr(block, "type", None) == "text")


def _find_flight_context(state, booking_token):
    if not booking_token:
        return None
    for msg in reversed(state["messages"]):
        if msg.get("role") != "user":
            continue
        content = msg.get("content")
        if not isinstance(content, list):
            continue
        for block in content:
            if not (isinstance(block, dict) and block.get("type") == "tool_result"):
                continue
            try:
                data = json.loads(block["content"])
            except (TypeError, ValueError, KeyError):
                continue
            for flight in data.get("flights", []):
                if flight.get("booking_token") == booking_token:
                    return flight
    return None


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


def _run_search_with_gate(args: dict) -> dict:
    choice = interrupt({
        "type": "search_tool_choice",
        "query": {
            "origin": args.get("origin"),
            "destination": args.get("destination"),
            "outbound_date": args.get("outbound_date"),
            "trip_type": args.get("trip_type", "one_way"),
            "return_date": args.get("return_date"),
        },
        "tools": SEARCH_TOOLS,
    })
    tool_choice = (choice or {}).get("tool", "google_flights")
    if tool_choice == "budget_deeplink":
        return _dispatch_tool("search_budget_carriers", args)
    return _dispatch_tool("search_flights", args)


def _run_booking_with_gate(state: AgentState, args: dict) -> dict:
    flight = _find_flight_context(state, args.get("booking_token"))
    confirm = interrupt({
        "type": "booking_confirmation",
        "flight": flight,
    })
    if not (confirm or {}).get("confirmed"):
        return {"cancelled": True, "message": "Booking lookup was cancelled by the user."}
    return _dispatch_tool("get_booking_options", args)


def call_tool(state: AgentState) -> dict:
    last_content = state["messages"][-1]["content"]
    tool_use = next(b for b in last_content if b.type == "tool_use")

    if tool_use.name == "search_flights":
        result = _run_search_with_gate(tool_use.input)
    elif tool_use.name == "get_booking_options":
        result = _run_booking_with_gate(state, tool_use.input)
    else:
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


def _package(result) -> dict:
    pending = result.get("__interrupt__")
    if pending:
        return {"type": "interrupt", "payload": pending[0].value}
    return {"type": "final", "text": _extract_text(result["messages"][-1]["content"])}


def chat(user_message: str, thread_id: str) -> dict:
    config = {"configurable": {"thread_id": thread_id}}
    result = _compiled.invoke(
        {"messages": [{"role": "user", "content": user_message}]},
        config=config,
    )
    return _package(result)


def resume(payload: dict, thread_id: str) -> dict:
    config = {"configurable": {"thread_id": thread_id}}
    result = _compiled.invoke(Command(resume=payload), config=config)
    return _package(result)


def get_pending_interrupt(thread_id: str):
    config = {"configurable": {"thread_id": thread_id}}
    snapshot = _compiled.get_state(config)
    for task in snapshot.tasks:
        interrupts = getattr(task, "interrupts", None)
        if interrupts:
            return interrupts[0].value
    return None


def get_history(thread_id: str) -> list:
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