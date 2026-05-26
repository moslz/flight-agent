import json

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


def chat(messages):
    conversation = list(messages)

    while True:
        response = _client.messages.create(
            model=MODEL,
            max_tokens=MAX_TOKENS,
            system=_system_prompt,
            tools=_tools,
            messages=conversation,
        )

        if response.stop_reason != "tool_use":
            return _extract_text(response.content)

        tool_use = next(b for b in response.content if b.type == "tool_use")
        result = _dispatch_tool(tool_use.name, tool_use.input)

        conversation.append({"role": "assistant", "content": response.content})
        conversation.append({
            "role": "user",
            "content": [{
                "type": "tool_result",
                "tool_use_id": tool_use.id,
                "content": json.dumps(result),
            }],
        })
