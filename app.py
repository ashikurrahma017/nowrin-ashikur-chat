from flask import Flask, render_template, request, jsonify
from flask_socketio import SocketIO, emit
from datetime import datetime
import pytz
import os
import json

app = Flask(__name__, template_folder="templates")
socketio = SocketIO(app)

DATA_FILE = "messages.json"

# Load saved messages
def load_messages():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r") as f:
            return json.load(f)
    return []

# Save messages
def save_messages():
    with open(DATA_FILE, "w") as f:
        json.dump(messages, f)

messages = load_messages()
seen_users = set()

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/login", methods=["POST"])
def login():
    data = request.get_json()
    username = data.get("username")
    password = data.get("password")
    if username and password:
        return jsonify({"success": True, "history": messages})
    return jsonify({"success": False})

@socketio.on("message")
def handle_message(data):
    tz = pytz.timezone("Asia/Dhaka")
    now = datetime.now(tz).strftime("%I:%M %p")
    message = {
        "user": data["user"],
        "msg": data.get("msg"),
        "time": now,
        "seen": False,
        "file": data.get("file"),
        "filename": data.get("filename")
    }
    messages.append(message)
    save_messages()
    emit("message", message, broadcast=True)

@socketio.on("seen")
def handle_seen(data):
    seen_users.add(data["user"])
    for msg in messages:
        if msg["user"] != data["user"]:
            msg["seen"] = True
    save_messages()
    emit("update_seen", broadcast=True)

if __name__ == "__main__":
    socketio.run(app, host="0.0.0.0", port=10000)
