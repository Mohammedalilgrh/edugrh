import os
import json
from flask import Flask, render_template, request, redirect, url_for
from flask_socketio import SocketIO, emit

app = Flask(__name__)
app.config['SECRET_KEY'] = 'secret!'
socketio = SocketIO(app)

# User data (in-memory, not persistent)
users = {}
whiteboard_data = []
audio_streams = {}  # Store audio stream data

# Load user data from file (sads.json)
def load_user_data():
    try:
        with open('sads.json', 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        return {}

# Save user data to file (sads.json)
def save_user_data(data):
    with open('sads.json', 'w') as f:
        json.dump(data, f)

users = load_user_data()

@app.route('/')
def index():
    return render_template('index.html', users=users.values())

@app.route('/login', methods=['POST'])
def login():
    username = request.form['username']
    phone_number = request.form['phone_number']

    # Basic validation (you should add more robust validation)
    if not username or not phone_number:
        return "Username and phone number are required."

    user_id = request.sid  # Use session ID as a unique user ID
    users[user_id] = {'username': username, 'phone_number': phone_number}
    save_user_data(users)
    return redirect(url_for('index'))

@socketio.on('connect')
def connect_handler():
    print('Client connected')
    emit('user_list', list(users.values()), broadcast=True)
    emit('whiteboard_data', whiteboard_data)
    # Initialize audio stream for the user
    audio_streams[request.sid] = None

@socketio.on('disconnect')
def disconnect():
    user_id = request.sid
    if user_id in users:
        del users[user_id]
        save_user_data(users)
        emit('user_list', list(users.values()), broadcast=True)
    # Clean up audio stream
    if user_id in audio_streams:
        del audio_streams[user_id]
    print('Client disconnected')

@socketio.on('whiteboard_event')
def handle_whiteboard_event(data):
    whiteboard_data.append(data)
    emit('whiteboard_event', data, broadcast=True, include_self=False)

@socketio.on('clear_whiteboard')
def handle_clear_whiteboard():
    global whiteboard_data
    whiteboard_data = []
    emit('clear_whiteboard', broadcast=True)

@socketio.on('raise_hand')
def handle_raise_hand(user_id):
    emit('hand_raised', user_id, broadcast=True)

@socketio.on('end_lecture')
def handle_end_lecture():
    emit('lecture_ended', broadcast=True)

@socketio.on('audio_stream')
def handle_audio_stream(data):
    # Store audio stream data (this is a simplified approach)
    audio_streams[request.sid] = data
    # Broadcast audio stream to all other clients
    emit('audio_stream', {'user_id': request.sid, 'audio': data}, broadcast=True, include_self=False)

@socketio.on('request_audio_stream')
def handle_request_audio_stream(user_id):
    # Send the audio stream data to the requesting user
    if user_id in audio_streams and audio_streams[user_id]:
        emit('audio_stream', {'user_id': user_id, 'audio': audio_streams[user_id]}, room=request.sid)

if __name__ == '__main__':
    # Ensure sads.json exists
    if not os.path.exists('sads.json'):
        with open('sads.json', 'w') as f:
            json.dump({}, f)

    # The following line is removed for Render deployment with Gunicorn
    # socketio.run(app, debug=True, host='0.0.0.0')
    pass  # Keep the script executable, but don't run the server directly
