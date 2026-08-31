from urllib.parse import unquote_plus
from flask import Flask, render_template, request, jsonify

from agent import chat, get_history
import booking_links

app = Flask(__name__)


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
        reply = chat(message, thread_id)
        return jsonify({"status": "success", "message": reply})
    except Exception as exc:
        return jsonify({"status": "error", "message": str(exc)}), 500


@app.route("/history/<thread_id>")
def history_endpoint(thread_id):
    return jsonify({"messages": get_history(thread_id)})


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