from urllib.parse import unquote_plus
from flask import Flask, render_template, request, jsonify

from agent import chat, get_history, get_pending_interrupt, resume
import booking_links

app = Flask(__name__)


def _format_agent_result(result: dict) -> dict:
    if result["type"] == "interrupt":
        return {"status": "interrupt", "interrupt": result["payload"]}
    return {"status": "success", "message": result["text"]}


@app.route("/")
def index():
    return render_template("index.html")

@app.route("/chat", methods=["POST"])
def chat_endpoint():
    data = request.json or {}
    thread_id = data.get("thread_id")
    message = (data.get("message") or "").strip()

    if not thread_id:
        return jsonify({"status": "error", "message": "Missing thread_id"}), 400
    if not message:
        return jsonify({"status": "error", "message": "Empty message"}), 400

    try:
        result = chat(message, thread_id)
        return jsonify(_format_agent_result(result))
    except Exception as exc:
        return jsonify({"status": "error", "message": str(exc)}), 500


@app.route("/resume", methods=["POST"])
def resume_endpoint():
    data = request.json or {}
    thread_id = data.get("thread_id")
    payload = data.get("payload")

    if not thread_id:
        return jsonify({"status": "error", "message": "Missing thread_id"}), 400
    if payload is None:
        return jsonify({"status": "error", "message": "Missing payload"}), 400

    try:
        result = resume(payload, thread_id)
        return jsonify(_format_agent_result(result))
    except Exception as exc:
        return jsonify({"status": "error", "message": str(exc)}), 500


@app.route("/history/<thread_id>")
def history_endpoint(thread_id):
    return jsonify({
        "messages": get_history(thread_id),
        "pending_interrupt": get_pending_interrupt(thread_id),
    })


@app.route("/book/<link_id>")
def book_redirect(link_id):
    redirect_info = booking_links.get_redirect(link_id)
    if not redirect_info:
        return "This booking link has expired or is invalid. Please search again in the chat.", 404

    field_name, _, field_value = redirect_info["post_data"].partition("=")
    field_value = unquote_plus(field_value)

    return render_template(
        "booking_redirect.html",
        action_url=redirect_info["url"],
        field_name=field_name,
        field_value=field_value,
    )

if __name__ == "__main__":
    app.run(debug=True, port=5000)