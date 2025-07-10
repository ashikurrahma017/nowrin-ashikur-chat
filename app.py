from flask import Flask, render_template, request, jsonify
from flask_socketio import SocketIO
from flask_cors import CORS
import os

app = Flask(__name__)
CORS(app)
socketio = SocketIO(app, cors_allowed_origins="*", async_mode="eventlet")

# Predefined users
users = {
    "Nowrin": "nowrin007",
    "Ashikur": "ashikur01788"
}

@app.route("/")
def index():
    return render_template("index.html")  # Looks in /templates/index.html

@app.route("/login", methods=["POST"])
def login():
    data = request.get_json()
    username = data.get("username")
    password = data.get("password")
    if username in users and users[username] == password:
        return jsonify({"success": True})
    return jsonify({"success": False})

@socketio.on("message")
def handle_message(data):
    socketio.emit("message", data)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    socketio.run(app, host="0.0.0.0", port=port)
