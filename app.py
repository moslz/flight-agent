from flask import Flask, render_template, request, jsonify

from agent import chat

app = Flask(__name__)


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/chat", methods=["POST"])
def chat_endpoint():
    messages = request.json.get("messages", [])
    try:
        reply = chat(messages)
        return jsonify({"status": "success", "message": reply})
    except Exception as exc:
        return jsonify({"status": "error", "message": str(exc)}), 500


if __name__ == "__main__":
    app.run(debug=True, port=5000)
