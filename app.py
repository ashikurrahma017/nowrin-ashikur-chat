from flask import Flask, render_template, request, jsonify
from flask_socketio import SocketIO, emit
from flask_cors import CORS
from datetime import datetime, timedelta

app = Flask(__name__)
app.config['SECRET_KEY'] = 'love-nowrin-ashikur'
CORS(app)
socketio = SocketIO(app, cors_allowed_origins="*")

# Predefined users
users = {
    "Ashikur": "ashikur01788",
    "Nowrin": "nowrin007"
}

# In-memory message store
message_history = []

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/login", methods=["POST"])
def login():
    data = request.json
    username = data.get("username")
    password = data.get("password")
    
    if username in users and users[username] == password:
        return jsonify(success=True, history=message_history)
    else:
        return jsonify(success=False)

@socketio.on("message")
def handle_message(data):
    user = data["user"]
    msg = data["msg"]
    bd_time = datetime.utcnow() + timedelta(hours=6)
    time_str = bd_time.strftime("%I:%M %p")
    payload = {"user": user, "msg": msg, "time": time_str}
    message_history.append(payload)
    emit("message", payload, broadcast=True)

if __name__ == "__main__":
    socketio.run(app, host="0.0.0.0", port=5000)
