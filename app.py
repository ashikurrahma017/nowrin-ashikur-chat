from flask import Flask, request, jsonify, send_file
from flask_socketio import SocketIO, emit
import eventlet

# Enable cooperative multitasking
eventlet.monkey_patch()

# Setup app and SocketIO
app = Flask(__name__)
socketio = SocketIO(app)

# Hardcoded user credentials
users = {
    "Nowrin": "nowrin007",
    "Ashikur": "ashikur01788"
}

# Serve the HTML page
@app.route('/')
def index():
    return send_file('index.html')

# Login route
@app.route('/login', methods=['POST'])
def login():
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')
    
    if username in users and users[username] == password:
        return jsonify(success=True)
    return jsonify(success=False)

# Handle chat messages
@socketio.on('message')
def handle_message(data):
    emit('message', data, broadcast=True)

# Start the app
if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=5000)
