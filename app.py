from flask import Flask, render_template, request, jsonify
from flask_socketio import SocketIO, emit
from datetime import datetime
import pytz

app = Flask(__name__)
socketio = SocketIO(app)

# Hardcoded users
users = {
    "Nowrin": "nowrin007",
    "Ashikur": "ashikur01788"
}

# Store messages in memory
message_history = []

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/login', methods=['POST'])
def login():
    data = request.json
    username = data.get("username")
    password = data.get("password")
    if users.get(username) == password:
        return jsonify(success=True, history=message_history)
    return jsonify(success=False)

@socketio.on("message")
def handle_message(data):
    bd_time = datetime.now(pytz.timezone("Asia/Dhaka")).strftime("%I:%M %p")
    message = {
        "user": data["user"],
        "msg": data.get("msg", ""),
        "time": bd_time,
        "seen": False
    }

    if "file" in data:
        message["file"] = data["file"]
        message["filename"] = data["filename"]

    message_history.append(message)
    emit("message", message, broadcast=True)

@socketio.on("seen")
def handle_seen(data):
    for msg in message_history:
        if msg["user"] != data["user"]:
            msg["seen"] = True
    emit("update_seen", list(range(len(message_history))), broadcast=True)

# ✅ New: Handle typing indicator
@socketio.on("typing")
def handle_typing(data):
    emit("typing", data, broadcast=True)

if __name__ == '__main__':
    socketio.run(app, host="0.0.0.0", port=5000)
