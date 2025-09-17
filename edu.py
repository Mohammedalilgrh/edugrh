from flask import Flask, render_template_string, request, jsonify, session, redirect, url_for
from flask_socketio import SocketIO, emit, join_room, leave_room, disconnect
import uuid
import json
import os
from datetime import datetime
import threading
import time

app = Flask(__name__)
app.config['SECRET_KEY'] = 'smart_board_secret_key_2024'
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')

# Global variables for session management
active_users = {}
raised_hands = []
lecture_active = False
teacher_id = None
user_data = {}

# File to store user data
USER_DATA_FILE = 'sads.py'

def save_user_data():
    """Save user data to sads.py file"""
    try:
        with open(USER_DATA_FILE, 'w') as f:
            f.write("# Student Database - Generated automatically\n")
            f.write("# Format: {'username': {'name': 'Name', 'phone': 'Phone', 'join_time': 'Time'}}\n\n")
            f.write("student_data = {\n")
            for username, data in user_data.items():
                f.write(f"    '{username}': {{\n")
                f.write(f"        'name': '{data.get('name', '')}',\n")
                f.write(f"        'phone': '{data.get('phone', '')}',\n")
                f.write(f"        'join_time': '{data.get('join_time', '')}',\n")
                f.write(f"        'total_sessions': {data.get('total_sessions', 1)}\n")
                f.write("    },\n")
            f.write("}\n\n")
            f.write(f"# Total students: {len(user_data)}\n")
            f.write(f"# Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    except Exception as e:
        print(f"Error saving user data: {e}")

def load_user_data():
    """Load user data from sads.py file if exists"""
    global user_data
    try:
        if os.path.exists(USER_DATA_FILE):
            # Read the file and extract student_data
            with open(USER_DATA_FILE, 'r') as f:
                content = f.read()
                # Execute the file to get student_data
                exec(content, globals())
                if 'student_data' in globals():
                    user_data = student_data
    except Exception as e:
        print(f"Error loading user data: {e}")

# Load existing user data on startup
load_user_data()

# HTML Template with all features
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Smart Board - Online Teaching Platform</title>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/socket.io/4.7.2/socket.io.js"></script>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        body {
            font-family: 'Arial', sans-serif;
            background: linear-gradient(135deg, #1e1e1e 0%, #2d2d2d 100%);
            color: #ffffff;
            overflow: hidden;
            height: 100vh;
        }
        
        .container {
            display: flex;
            height: 100vh;
            flex-direction: column;
        }
        
        .header {
            background: #1a1a1a;
            padding: 10px 20px;
            border-bottom: 2px solid #333;
            display: flex;
            justify-content: space-between;
            align-items: center;
            flex-wrap: wrap;
            gap: 10px;
        }
        
        .logo {
            font-size: 24px;
            font-weight: bold;
            color: #4CAF50;
        }
        
        .controls {
            display: flex;
            gap: 10px;
            flex-wrap: wrap;
            align-items: center;
        }
        
        .btn {
            padding: 8px 16px;
            border: none;
            border-radius: 25px;
            cursor: pointer;
            font-weight: bold;
            transition: all 0.3s;
            font-size: 14px;
        }
        
        .btn-primary {
            background: #4CAF50;
            color: white;
        }
        
        .btn-danger {
            background: #f44336;
            color: white;
        }
        
        .btn-warning {
            background: #ff9800;
            color: white;
        }
        
        .btn:hover {
            transform: scale(1.05);
            opacity: 0.9;
        }
        
        .main-content {
            display: flex;
            flex: 1;
            overflow: hidden;
        }
        
        .whiteboard-container {
            flex: 1;
            display: flex;
            flex-direction: column;
            background: #2d2d2d;
        }
        
        .toolbar {
            background: #1a1a1a;
            padding: 10px;
            display: flex;
            gap: 10px;
            align-items: center;
            flex-wrap: wrap;
            border-bottom: 1px solid #333;
        }
        
        .tool-group {
            display: flex;
            gap: 5px;
            align-items: center;
        }
        
        .whiteboard {
            flex: 1;
            background: #ffffff;
            cursor: crosshair;
            position: relative;
        }
        
        .sidebar {
            width: 300px;
            background: #1a1a1a;
            border-left: 2px solid #333;
            display: flex;
            flex-direction: column;
            overflow: hidden;
        }
        
        .sidebar-tabs {
            display: flex;
            border-bottom: 1px solid #333;
        }
        
        .tab {
            flex: 1;
            padding: 10px;
            text-align: center;
            cursor: pointer;
            background: #2d2d2d;
            border-right: 1px solid #333;
            transition: all 0.3s;
        }
        
        .tab.active {
            background: #4CAF50;
            color: white;
        }
        
        .tab-content {
            flex: 1;
            padding: 15px;
            overflow-y: auto;
        }
        
        .user-item {
            display: flex;
            align-items: center;
            justify-content: space-between;
            padding: 10px;
            margin: 5px 0;
            background: #2d2d2d;
            border-radius: 8px;
            border-left: 4px solid #4CAF50;
        }
        
        .user-item.teacher {
            border-left-color: #ff9800;
        }
        
        .user-item.hand-raised {
            border-left-color: #f44336;
            animation: pulse 2s infinite;
        }
        
        @keyframes pulse {
            0% { opacity: 1; }
            50% { opacity: 0.7; }
            100% { opacity: 1; }
        }
        
        .hand-raised-indicator {
            color: #f44336;
            font-weight: bold;
        }
        
        .audio-controls {
            display: flex;
            gap: 10px;
            align-items: center;
            margin: 10px 0;
        }
        
        .status {
            padding: 5px 10px;
            border-radius: 15px;
            font-size: 12px;
            font-weight: bold;
        }
        
        .status.online {
            background: #4CAF50;
            color: white;
        }
        
        .status.offline {
            background: #666;
            color: white;
        }
        
        .chat-messages {
            height: 200px;
            overflow-y: auto;
            background: #2d2d2d;
            border-radius: 8px;
            padding: 10px;
            margin: 10px 0;
        }
        
        .message {
            margin: 5px 0;
            padding: 5px 10px;
            border-radius: 15px;
            max-width: 80%;
        }
        
        .message.teacher {
            background: #4CAF50;
            margin-left: auto;
        }
        
        .message.student {
            background: #555;
        }
        
        .chat-input {
            display: flex;
            gap: 5px;
            margin-top: 10px;
        }
        
        .chat-input input {
            flex: 1;
            padding: 10px;
            border: none;
            border-radius: 20px;
            background: #333;
            color: white;
        }
        
        .modal {
            display: none;
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background: rgba(0,0,0,0.8);
            z-index: 1000;
        }
        
        .modal-content {
            position: absolute;
            top: 50%;
            left: 50%;
            transform: translate(-50%, -50%);
            background: #1a1a1a;
            padding: 30px;
            border-radius: 15px;
            border: 2px solid #4CAF50;
            max-width: 400px;
            width: 90%;
        }
        
        .form-group {
            margin: 15px 0;
        }
        
        .form-group label {
            display: block;
            margin-bottom: 5px;
            font-weight: bold;
        }
        
        .form-group input {
            width: 100%;
            padding: 12px;
            border: 1px solid #333;
            border-radius: 8px;
            background: #2d2d2d;
            color: white;
            font-size: 16px;
        }
        
        .volume-slider {
            width: 100px;
            margin: 0 10px;
        }
        
        .audio-visualizer {
            display: flex;
            align-items: end;
            gap: 2px;
            height: 30px;
            margin: 0 10px;
        }
        
        .bar {
            width: 3px;
            background: #4CAF50;
            border-radius: 2px;
            transition: height 0.1s;
        }
        
        @media (max-width: 768px) {
            .main-content {
                flex-direction: column;
            }
            
            .sidebar {
                width: 100%;
                height: 250px;
            }
            
            .controls {
                font-size: 12px;
            }
            
            .btn {
                padding: 6px 12px;
                font-size: 12px;
            }
        }
        
        .hidden {
            display: none !important;
        }
        
        .lecture-status {
            display: flex;
            align-items: center;
            gap: 10px;
            padding: 10px;
            background: #2d2d2d;
            border-radius: 8px;
            margin-bottom: 15px;
        }
        
        .status-indicator {
            width: 12px;
            height: 12px;
            border-radius: 50%;
            background: #f44336;
        }
        
        .status-indicator.active {
            background: #4CAF50;
            animation: pulse 2s infinite;
        }
    </style>
</head>
<body>
    <!-- Login Modal -->
    <div id="loginModal" class="modal" style="display: block;">
        <div class="modal-content">
            <h2 style="text-align: center; color: #4CAF50; margin-bottom: 20px;">Join Smart Board</h2>
            <form id="loginForm">
                <div class="form-group">
                    <label>Full Name:</label>
                    <input type="text" id="fullName" required placeholder="Enter your full name">
                </div>
                <div class="form-group">
                    <label>Username:</label>
                    <input type="text" id="username" required placeholder="Choose a username">
                </div>
                <div class="form-group">
                    <label>Phone Number:</label>
                    <input type="tel" id="phoneNumber" required placeholder="Enter your phone number">
                </div>
                <div class="form-group">
                    <label>Role:</label>
                    <select id="userRole" style="width: 100%; padding: 12px; border: 1px solid #333; border-radius: 8px; background: #2d2d2d; color: white; font-size: 16px;">
                        <option value="student">Student</option>
                        <option value="teacher">Teacher</option>
                    </select>
                </div>
                <button type="submit" class="btn btn-primary" style="width: 100%; margin-top: 20px;">Join Lecture</button>
            </form>
        </div>
    </div>

    <!-- Main Application -->
    <div class="container hidden" id="mainApp">
        <div class="header">
            <div class="logo">📚 Smart Board</div>
            <div class="controls">
                <span id="userInfo"></span>
                <button class="btn btn-warning" id="raiseHandBtn" onclick="toggleRaiseHand()">🙋‍♂️ Raise Hand</button>
                <button class="btn btn-primary" id="startLectureBtn" onclick="toggleLecture()">Start Lecture</button>
                <button class="btn btn-danger" onclick="leaveLecture()">Leave</button>
            </div>
        </div>
        
        <div class="main-content">
            <div class="whiteboard-container">
                <div class="toolbar">
                    <div class="tool-group">
                        <button class="btn btn-primary" onclick="setTool('pen')">✏️ Pen</button>
                        <button class="btn btn-primary" onclick="setTool('eraser')">🗑️ Eraser</button>
                        <input type="color" id="colorPicker" value="#000000" onchange="setColor(this.value)">
                        <input type="range" id="brushSize" min="1" max="20" value="3" onchange="setBrushSize(this.value)">
                        <button class="btn btn-warning" onclick="clearBoard()">Clear All</button>
                    </div>
                    <div class="tool-group">
                        <button class="btn btn-primary" onclick="setTool('line')">📏 Line</button>
                        <button class="btn btn-primary" onclick="setTool('rect')">⬛ Rectangle</button>
                        <button class="btn btn-primary" onclick="setTool('circle')">⭕ Circle</button>
                        <button class="btn btn-primary" onclick="setTool('text')">📝 Text</button>
                    </div>
                </div>
                <canvas id="whiteboard" class="whiteboard"></canvas>
            </div>
            
            <div class="sidebar">
                <div class="sidebar-tabs">
                    <div class="tab active" onclick="showTab('users')">Users</div>
                    <div class="tab" onclick="showTab('chat')">Chat</div>
                    <div class="tab" onclick="showTab('audio')">Audio</div>
                </div>
                
                <div class="tab-content">
                    <!-- Users Tab -->
                    <div id="usersTab">
                        <div class="lecture-status">
                            <div class="status-indicator" id="lectureIndicator"></div>
                            <span id="lectureStatusText">Lecture Not Started</span>
                        </div>
                        
                        <h3>Online Users (<span id="userCount">0</span>)</h3>
                        <div id="usersList"></div>
                        
                        <div style="margin-top: 20px;">
                            <h4>Raised Hands (<span id="handsCount">0</span>)</h4>
                            <div id="raisedHandsList"></div>
                        </div>
                    </div>
                    
                    <!-- Chat Tab -->
                    <div id="chatTab" class="hidden">
                        <h3>Chat Messages</h3>
                        <div class="chat-messages" id="chatMessages"></div>
                        <div class="chat-input">
                            <input type="text" id="chatInput" placeholder="Type a message..." onkeypress="sendChatOnEnter(event)">
                            <button class="btn btn-primary" onclick="sendChat()">Send</button>
                        </div>
                    </div>
                    
                    <!-- Audio Tab -->
                    <div id="audioTab" class="hidden">
                        <h3>Audio Controls</h3>
                        <div class="audio-controls">
                            <button class="btn btn-primary" id="micBtn" onclick="toggleMicrophone()">🎤 Mic Off</button>
                            <button class="btn btn-primary" id="speakerBtn" onclick="toggleSpeaker()">🔊 Speaker On</button>
                        </div>
                        
                        <div style="margin: 15px 0;">
                            <label>Volume:</label>
                            <input type="range" class="volume-slider" id="volumeSlider" min="0" max="100" value="50" onchange="setVolume(this.value)">
                            <span id="volumeValue">50%</span>
                        </div>
                        
                        <div class="audio-visualizer" id="audioVisualizer">
                            <div class="bar"></div>
                            <div class="bar"></div>
                            <div class="bar"></div>
                            <div class="bar"></div>
                            <div class="bar"></div>
                            <div class="bar"></div>
                            <div class="bar"></div>
                            <div class="bar"></div>
                        </div>
                        
                        <div style="margin-top: 15px;">
                            <h4>Audio Settings</h4>
                            <label><input type="checkbox" id="autoGainControl"> Auto Gain Control</label><br>
                            <label><input type="checkbox" id="noiseSuppression" checked> Noise Suppression</label><br>
                            <label><input type="checkbox" id="echoCancellation" checked> Echo Cancellation</label>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </div>

    <script>
        // Global variables
        let socket;
        let currentUser = null;
        let isTeacher = false;
        let handRaised = false;
        let microphoneEnabled = false;
        let speakerEnabled = true;
        let localStream = null;
        let audioContext = null;
        let analyser = null;
        let mediaRecorder = null;
        
        // Whiteboard variables
        let canvas, ctx;
        let isDrawing = false;
        let currentTool = 'pen';
        let currentColor = '#000000';
        let currentBrushSize = 3;
        let startX, startY;
        
        // Initialize application
        document.addEventListener('DOMContentLoaded', function() {
            initializeWhiteboard();
            setupEventListeners();
        });
        
        // Setup event listeners
        function setupEventListeners() {
            document.getElementById('loginForm').addEventListener('submit', handleLogin);
        }
        
        // Handle user login
        function handleLogin(e) {
            e.preventDefault();
            const fullName = document.getElementById('fullName').value;
            const username = document.getElementById('username').value;
            const phoneNumber = document.getElementById('phoneNumber').value;
            const userRole = document.getElementById('userRole').value;
            
            currentUser = {
                fullName: fullName,
                username: username,
                phoneNumber: phoneNumber,
                role: userRole,
                id: generateUniqueId()
            };
            
            isTeacher = userRole === 'teacher';
            
            // Connect to socket
            connectSocket();
            
            // Hide login modal and show main app
            document.getElementById('loginModal').style.display = 'none';
            document.getElementById('mainApp').classList.remove('hidden');
            
            // Update UI
            updateUserInterface();
        }
        
        // Connect to socket
        function connectSocket() {
            socket = io();
            
            socket.emit('user_join', currentUser);
            
            socket.on('user_joined', function(data) {
                updateUsersList(data.users);
                addChatMessage('system', `${data.user.fullName} joined the lecture`);
            });
            
            socket.on('user_left', function(data) {
                updateUsersList(data.users);
                addChatMessage('system', `${data.user.fullName} left the lecture`);
            });
            
            socket.on('users_update', function(data) {
                updateUsersList(data.users);
            });
            
            socket.on('hand_raised', function(data) {
                updateRaisedHands(data.raised_hands);
            });
            
            socket.on('lecture_status', function(data) {
                updateLectureStatus(data.active, data.teacher);
            });
            
            socket.on('chat_message', function(data) {
                addChatMessage(data.sender_role, data.message, data.sender_name);
            });
            
            socket.on('whiteboard_update', function(data) {
                drawOnCanvas(data);
            });
            
            socket.on('whiteboard_clear', function() {
                clearCanvas();
            });
            
            socket.on('audio_data', function(data) {
                if (speakerEnabled && data.user_id !== currentUser.id) {
                    playAudioData(data.audio_data);
                }
            });
        }
        
        // Update user interface
        function updateUserInterface() {
            document.getElementById('userInfo').textContent = `${currentUser.fullName} (${isTeacher ? 'Teacher' : 'Student'})`;
            
            if (!isTeacher) {
                document.getElementById('startLectureBtn').style.display = 'none';
            }
        }
        
        // Update users list
        function updateUsersList(users) {
            const usersList = document.getElementById('usersList');
            const userCount = document.getElementById('userCount');
            
            usersList.innerHTML = '';
            userCount.textContent = Object.keys(users).length;
            
            Object.values(users).forEach(user => {
                const userItem = document.createElement('div');
                userItem.className = `user-item ${user.role === 'teacher' ? 'teacher' : ''}`;
                
                const isHandRaised = user.hand_raised;
                if (isHandRaised) {
                    userItem.classList.add('hand-raised');
                }
                
                userItem.innerHTML = `
                    <div>
                        <strong>${user.fullName}</strong>
                        <div style="font-size: 12px; opacity: 0.7;">${user.username}</div>
                        ${isHandRaised ? '<span class="hand-raised-indicator">🙋‍♂️ Hand Raised</span>' : ''}
                    </div>
                    <div class="status online">Online</div>
                `;
                
                usersList.appendChild(userItem);
            });
        }
        
        // Update raised hands
        function updateRaisedHands(raisedHands) {
            const handsCount = document.getElementById('handsCount');
            const raisedHandsList = document.getElementById('raisedHandsList');
            
            handsCount.textContent = raisedHands.length;
            
            raisedHandsList.innerHTML = '';
            raisedHands.forEach(user => {
                const handItem = document.createElement('div');
                handItem.className = 'user-item hand-raised';
                handItem.innerHTML = `
                    <div>
                        <strong>${user.fullName}</strong>
                        <div style="font-size: 12px; opacity: 0.7;">Wants to speak</div>
                    </div>
                    ${isTeacher ? `<button class="btn btn-primary" onclick="givePermissionToSpeak('${user.id}')">Allow</button>` : ''}
                `;
                raisedHandsList.appendChild(handItem);
            });
        }
        
        // Toggle raise hand
        function toggleRaiseHand() {
            if (isTeacher) return;
            
            handRaised = !handRaised;
            socket.emit('toggle_hand', { raised: handRaised });
            
            const btn = document.getElementById('raiseHandBtn');
            if (handRaised) {
                btn.textContent = '✋ Lower Hand';
                btn.className = 'btn btn-danger';
            } else {
                btn.textContent = '🙋‍♂️ Raise Hand';
                btn.className = 'btn btn-warning';
            }
        }
        
        // Toggle lecture
        function toggleLecture() {
            if (!isTeacher) return;
            
            socket.emit('toggle_lecture');
        }
        
        // Update lecture status
        function updateLectureStatus(active, teacher) {
            const indicator = document.getElementById('lectureIndicator');
            const statusText = document.getElementById('lectureStatusText');
            const startBtn = document.getElementById('startLectureBtn');
            
            if (active) {
                indicator.classList.add('active');
                statusText.textContent = `Lecture Active - ${teacher}`;
                if (isTeacher) {
                    startBtn.textContent = 'End Lecture';
                    startBtn.className = 'btn btn-danger';
                }
            } else {
                indicator.classList.remove('active');
                statusText.textContent = 'Lecture Not Started';
                if (isTeacher) {
                    startBtn.textContent = 'Start Lecture';
                    startBtn.className = 'btn btn-primary';
                }
            }
        }
        
        // Leave lecture
        function leaveLecture() {
            if (confirm('Are you sure you want to leave the lecture?')) {
                socket.emit('user_leave');
                location.reload();
            }
        }
        
        // Show tab
        function showTab(tabName) {
            // Hide all tabs
            document.getElementById('usersTab').classList.add('hidden');
            document.getElementById('chatTab').classList.add('hidden');
            document.getElementById('audioTab').classList.add('hidden');
            
            // Remove active class from all tab buttons
            document.querySelectorAll('.tab').forEach(tab => tab.classList.remove('active'));
            
            // Show selected tab
            document.getElementById(tabName + 'Tab').classList.remove('hidden');
            
            // Add active class to selected tab button
            event.target.classList.add('active');
        }
        
        // Chat functions
        function sendChat() {
            const input = document.getElementById('chatInput');
            const message = input.value.trim();
            
            if (message) {
                socket.emit('send_chat', { message: message });
                input.value = '';
            }
        }
        
        function sendChatOnEnter(event) {
            if (event.key === 'Enter') {
                sendChat();
            }
        }
        
        function addChatMessage(senderRole, message, senderName = 'System') {
            const messagesContainer = document.getElementById('chatMessages');
            const messageElement = document.createElement('div');
            messageElement.className = `message ${senderRole}`;
            
            const timestamp = new Date().toLocaleTimeString();
            messageElement.innerHTML = `
                <div style="font-size: 12px; opacity: 0.7;">${senderName} - ${timestamp}</div>
                <div>${message}</div>
            `;
            
            messagesContainer.appendChild(messageElement);
            messagesContainer.scrollTop = messagesContainer.scrollHeight;
        }
        
        // Audio functions
        async function toggleMicrophone() {
            const btn = document.getElementById('micBtn');
            
            if (!microphoneEnabled) {
                try {
                    localStream = await navigator.mediaDevices.getUserMedia({
                        audio: {
                            echoCancellation: document.getElementById('echoCancellation').checked,
                            noiseSuppression: document.getElementById('noiseSuppression').checked,
                            autoGainControl: document.getElementById('autoGainControl').checked
                        }
                    });
                    
                    setupAudioProcessing();
                    microphoneEnabled = true;
                    btn.textContent = '🎤 Mic On';
                    btn.className = 'btn btn-danger';
                    
                } catch (err) {
                    alert('Could not access microphone: ' + err.message);
                }
            } else {
                if (localStream) {
                    localStream.getTracks().forEach(track => track.stop());
                }
                if (mediaRecorder) {
                    mediaRecorder.stop();
                }
                microphoneEnabled = false;
                btn.textContent = '🎤 Mic Off';
                btn.className = 'btn btn-primary';
            }
        }
        
        function toggleSpeaker() {
            const btn = document.getElementById('speakerBtn');
            speakerEnabled = !speakerEnabled;
            
            if (speakerEnabled) {
                btn.textContent = '🔊 Speaker On';
                btn.className = 'btn btn-primary';
            } else {
                btn.textContent = '🔇 Speaker Off';
                btn.className = 'btn btn-danger';
            }
        }
        
        function setVolume(value) {
            document.getElementById('volumeValue').textContent = value + '%';
            // Implement volume control for audio playback
        }
        
        async function setupAudioProcessing() {
            if (!localStream) return;
            
            audioContext = new (window.AudioContext || window.webkitAudioContext)();
            const source = audioContext.createMediaStreamSource(localStream);
            
            analyser = audioContext.createAnalyser();
            analyser.fftSize = 256;
            source.connect(analyser);
            
            // Setup MediaRecorder for audio transmission
            mediaRecorder = new MediaRecorder(localStream, { mimeType: 'audio/webm' });
            
            mediaRecorder.ondataavailable = function(event) {
                if (event.data.size > 0) {
                    const reader = new FileReader();
                    reader.onload = function() {
                        socket.emit('audio_data', {
                            audio_data: reader.result,
                            user_id: currentUser.id
                        });
                    };
                    reader.readAsArrayBuffer(event.data);
                }
            };
            
            mediaRecorder.start(100); // Send audio chunks every 100ms
            
            // Start audio visualization
            visualizeAudio();
        }
        
        function visualizeAudio() {
            if (!analyser) return;
            
            const bufferLength = analyser.frequencyBinCount;
            const dataArray = new Uint8Array(bufferLength);
            const bars = document.querySelectorAll('#audioVisualizer .bar');
            
            function updateVisualization() {
                analyser.getByteFrequencyData(dataArray);
                
                bars.forEach((bar, index) => {
                    const barIndex = Math.floor((index / bars.length) * bufferLength);
                    const barHeight = (dataArray[barIndex] / 255) * 30;
                    bar.style.height = Math.max(2, barHeight) + 'px';
                });
                
                requestAnimationFrame(updateVisualization);
            }
            
            updateVisualization();
        }
        
        function playAudioData(audioData) {
            if (!speakerEnabled) return;
            
            try {
                const audioBlob = new Blob([audioData], { type: 'audio/webm' });
                const audioUrl = URL.createObjectURL(audioBlob);
                const audio = new Audio(audioUrl);
                
                const volumeSlider = document.getElementById('volumeSlider');
                audio.volume = volumeSlider.value / 100;
                
                audio.play().catch(err => console.log('Audio play error:', err));
                
                // Clean up URL after playing
                audio.addEventListener('ended', () => {
                    URL.revokeObjectURL(audioUrl);
                });
                
            } catch (err) {
                console.log('Error playing audio:', err);
            }
        }
        
        // Whiteboard functions
        function initializeWhiteboard() {
            canvas = document.getElementById('whiteboard');
            ctx = canvas.getContext('2d');
            
            resizeCanvas();
            window.addEventListener('resize', resizeCanvas);
            
            // Mouse events
            canvas.addEventListener('mousedown', startDrawing);
            canvas.addEventListener('mousemove', draw);
            canvas.addEventListener('mouseup', stopDrawing);
            canvas.addEventListener('mouseout', stopDrawing);
            
            // Touch events for mobile
            canvas.addEventListener('touchstart', handleTouch);
            canvas.addEventListener('touchmove', handleTouch);
            canvas.addEventListener('touchend', stopDrawing);
        }
        
        function resizeCanvas() {
            const rect = canvas.getBoundingClientRect();
            canvas.width = rect.width;
            canvas.height = rect.height;
            
            // Set default drawing properties
            ctx.lineCap = 'round';
            ctx.lineJoin = 'round';
            ctx.strokeStyle = currentColor;
            ctx.lineWidth = currentBrushSize;
        }
        
        function getMousePos(e) {
            const rect = canvas.getBoundingClientRect();
            return {
                x: e.clientX - rect.left,
                y: e.clientY - rect.top
            };
        }
        
        function getTouchPos(e) {
            const rect = canvas.getBoundingClientRect();
            return {
                x: e.touches[0].clientX - rect.left,
                y: e.touches[0].clientY - rect.top
            };
        }
        
        function startDrawing(e) {
            if (!isTeacher) return; // Only teachers can draw
            
            isDrawing = true;
            const pos = getMousePos(e);
            startX = pos.x;
            startY = pos.y;
            
            if (currentTool === 'pen' || currentTool === 'eraser') {
                ctx.beginPath();
                ctx.moveTo(pos.x, pos.y);
            }
        }
        
        function draw(e) {
            if (!isDrawing || !isTeacher) return;
            
            const pos = getMousePos(e);
            const drawData = {
                tool: currentTool,
                color: currentTool === 'eraser' ? '#ffffff' : currentColor,
                size: currentBrushSize,
                startX: startX,
                startY: startY,
                endX: pos.x,
                endY: pos.y
            };
            
            if (currentTool === 'pen' || currentTool === 'eraser') {
                ctx.strokeStyle = drawData.color;
                ctx.lineWidth = drawData.size;
                ctx.lineTo(pos.x, pos.y);
                ctx.stroke();
                
                drawData.startX = pos.x;
                drawData.startY = pos.y;
                startX = pos.x;
                startY = pos.y;
            }
            
            // Send drawing data to other users
            socket.emit('whiteboard_draw', drawData);
        }
        
        function stopDrawing() {
            isDrawing = false;
            
            if (currentTool === 'line' || currentTool === 'rect' || currentTool === 'circle') {
                // Draw final shape
                drawShape(currentTool, startX, startY, event.clientX - canvas.getBoundingClientRect().left, event.clientY - canvas.getBoundingClientRect().top);
            }
        }
        
        function handleTouch(e) {
            e.preventDefault();
            
            const touch = e.touches[0];
            const mouseEvent = new MouseEvent(e.type === 'touchstart' ? 'mousedown' : e.type === 'touchmove' ? 'mousemove' : 'mouseup', {
                clientX: touch.clientX,
                clientY: touch.clientY
            });
            
            canvas.dispatchEvent(mouseEvent);
        }
        
        function drawOnCanvas(data) {
            ctx.strokeStyle = data.color;
            ctx.lineWidth = data.size;
            
            switch (data.tool) {
                case 'pen':
                case 'eraser':
                    ctx.beginPath();
                    ctx.moveTo(data.startX, data.startY);
                    ctx.lineTo(data.endX, data.endY);
                    ctx.stroke();
                    break;
                case 'line':
                    drawLine(data.startX, data.startY, data.endX, data.endY);
                    break;
                case 'rect':
                    drawRectangle(data.startX, data.startY, data.endX, data.endY);
                    break;
                case 'circle':
                    drawCircle(data.startX, data.startY, data.endX, data.endY);
                    break;
            }
        }
        
        function setTool(tool) {
            currentTool = tool;
            
            // Update cursor
            if (tool === 'eraser') {
                canvas.style.cursor = 'crosshair';
            } else {
                canvas.style.cursor = 'crosshair';
            }
            
            // Update active tool button
            document.querySelectorAll('.toolbar .btn').forEach(btn => btn.classList.remove('active'));
            event.target.classList.add('active');
        }
        
        function setColor(color) {
            currentColor = color;
        }
        
        function setBrushSize(size) {
            currentBrushSize = size;
        }
        
        function clearBoard() {
            if (!isTeacher) return;
            
            if (confirm('Are you sure you want to clear the whiteboard?')) {
                clearCanvas();
                socket.emit('whiteboard_clear');
            }
        }
        
        function clearCanvas() {
            ctx.clearRect(0, 0, canvas.width, canvas.height);
        }
        
        function drawLine(x1, y1, x2, y2) {
            ctx.beginPath();
            ctx.moveTo(x1, y1);
            ctx.lineTo(x2, y2);
            ctx.stroke();
        }
        
        function drawRectangle(x1, y1, x2, y2) {
            const width = x2 - x1;
            const height = y2 - y1;
            ctx.strokeRect(x1, y1, width, height);
        }
        
        function drawCircle(x1, y1, x2, y2) {
            const radius = Math.sqrt(Math.pow(x2 - x1, 2) + Math.pow(y2 - y1, 2));
            ctx.beginPath();
            ctx.arc(x1, y1, radius, 0, 2 * Math.PI);
            ctx.stroke();
        }
        
        function drawShape(tool, x1, y1, x2, y2) {
            ctx.strokeStyle = currentColor;
            ctx.lineWidth = currentBrushSize;
            
            const drawData = {
                tool: tool,
                color: currentColor,
                size: currentBrushSize,
                startX: x1,
                startY: y1,
                endX: x2,
                endY: y2
            };
            
            switch (tool) {
                case 'line':
                    drawLine(x1, y1, x2, y2);
                    break;
                case 'rect':
                    drawRectangle(x1, y1, x2, y2);
                    break;
                case 'circle':
                    drawCircle(x1, y1, x2, y2);
                    break;
            }
            
            socket.emit('whiteboard_draw', drawData);
        }
        
        // Utility functions
        function generateUniqueId() {
            return Math.random().toString(36).substr(2, 9) + Date.now().toString(36);
        }
        
        function givePermissionToSpeak(userId) {
            socket.emit('give_permission', { user_id: userId });
        }
        
        // Handle disconnection
        window.addEventListener('beforeunload', function() {
            if (socket) {
                socket.emit('user_leave');
            }
        });
    </script>
</body>
</html>
"""

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

@socketio.on('user_join')
def handle_user_join(data):
    user_id = request.sid
    user_info = {
        'id': user_id,
        'fullName': data['fullName'],
        'username': data['username'],
        'phoneNumber': data['phoneNumber'],
        'role': data['role'],
        'hand_raised': False,
        'speaking_permission': False,
        'join_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    }
    
    active_users[user_id] = user_info
    
    # Save user data to file
    username = data['username']
    if username in user_data:
        user_data[username]['total_sessions'] = user_data[username].get('total_sessions', 0) + 1
    else:
        user_data[username] = {
            'name': data['fullName'],
            'phone': data['phoneNumber'],
            'join_time': user_info['join_time'],
            'total_sessions': 1
        }
    
    save_user_data()
    
    # Set teacher if this is a teacher
    global teacher_id
    if data['role'] == 'teacher' and teacher_id is None:
        teacher_id = user_id
    
    # Join a room for broadcasting
    join_room('lecture_room')
    
    # Notify all users
    emit('user_joined', {
        'user': user_info,
        'users': active_users
    }, room='lecture_room')
    
    # Send current lecture status
    emit('lecture_status', {
        'active': lecture_active,
        'teacher': active_users.get(teacher_id, {}).get('fullName', 'Unknown') if teacher_id else 'None'
    })
    
    print(f"User joined: {user_info['fullName']} ({user_info['role']})")

@socketio.on('user_leave')
def handle_user_leave():
    user_id = request.sid
    if user_id in active_users:
        user_info = active_users.pop(user_id)
        
        # Remove from raised hands if present
        global raised_hands
        raised_hands = [hand for hand in raised_hands if hand['id'] != user_id]
        
        # Reset teacher if teacher leaves
        global teacher_id
        if user_id == teacher_id:
            teacher_id = None
            global lecture_active
            lecture_active = False
        
        leave_room('lecture_room')
        
        # Notify all users
        emit('user_left', {
            'user': user_info,
            'users': active_users
        }, room='lecture_room')
        
        emit('hand_raised', {'raised_hands': raised_hands}, room='lecture_room')
        
        print(f"User left: {user_info['fullName']}")

@socketio.on('disconnect')
def handle_disconnect():
    handle_user_leave()

@socketio.on('toggle_hand')
def handle_toggle_hand(data):
    user_id = request.sid
    if user_id in active_users:
        active_users[user_id]['hand_raised'] = data['raised']
        
        global raised_hands
        if data['raised']:
            if not any(hand['id'] == user_id for hand in raised_hands):
                raised_hands.append(active_users[user_id])
        else:
            raised_hands = [hand for hand in raised_hands if hand['id'] != user_id]
        
        emit('hand_raised', {'raised_hands': raised_hands}, room='lecture_room')
        emit('users_update', {'users': active_users}, room='lecture_room')

@socketio.on('toggle_lecture')
def handle_toggle_lecture():
    user_id = request.sid
    if user_id == teacher_id:
        global lecture_active
        lecture_active = not lecture_active
        
        teacher_name = active_users[teacher_id]['fullName']
        emit('lecture_status', {
            'active': lecture_active,
            'teacher': teacher_name
        }, room='lecture_room')
        
        print(f"Lecture {'started' if lecture_active else 'ended'} by {teacher_name}")

@socketio.on('send_chat')
def handle_send_chat(data):
    user_id = request.sid
    if user_id in active_users:
        user_info = active_users[user_id]
        
        emit('chat_message', {
            'message': data['message'],
            'sender_name': user_info['fullName'],
            'sender_role': user_info['role'],
            'timestamp': datetime.now().strftime('%H:%M:%S')
        }, room='lecture_room')

@socketio.on('whiteboard_draw')
def handle_whiteboard_draw(data):
    user_id = request.sid
    if user_id == teacher_id:  # Only teacher can draw
        emit('whiteboard_update', data, room='lecture_room', include_self=False)

@socketio.on('whiteboard_clear')
def handle_whiteboard_clear():
    user_id = request.sid
    if user_id == teacher_id:  # Only teacher can clear
        emit('whiteboard_clear', room='lecture_room', include_self=False)

@socketio.on('audio_data')
def handle_audio_data(data):
    user_id = request.sid
    if user_id in active_users:
        # Check if user has permission to speak (teacher always has permission)
        user_info = active_users[user_id]
        if user_info['role'] == 'teacher' or user_info.get('speaking_permission', False):
            # Broadcast audio to all other users
            emit('audio_data', {
                'audio_data': data['audio_data'],
                'user_id': user_id,
                'user_name': user_info['fullName']
            }, room='lecture_room', include_self=False)

@socketio.on('give_permission')
def handle_give_permission(data):
    user_id = request.sid
    target_user_id = data['user_id']
    
    # Only teacher can give permission
    if user_id == teacher_id and target_user_id in active_users:
        active_users[target_user_id]['speaking_permission'] = True
        
        # Remove from raised hands
        global raised_hands
        raised_hands = [hand for hand in raised_hands if hand['id'] != target_user_id]
        
        # Lower the hand
        active_users[target_user_id]['hand_raised'] = False
        
        emit('hand_raised', {'raised_hands': raised_hands}, room='lecture_room')
        emit('users_update', {'users': active_users}, room='lecture_room')
        
        # Notify the user they can speak
        emit('speaking_permission_granted', room=target_user_id)

# Health check endpoint for deployment
@app.route('/health')
def health_check():
    return jsonify({'status': 'healthy', 'users': len(active_users)})

# API endpoint to get user statistics
@app.route('/api/stats')
def get_stats():
    return jsonify({
        'total_users': len(user_data),
        'active_users': len(active_users),
        'lecture_active': lecture_active,
        'raised_hands': len(raised_hands)
    })

# Clean up inactive users periodically
def cleanup_inactive_users():
    while True:
        try:
            # This is a basic cleanup - in production you'd want more sophisticated session management
            time.sleep(300)  # Check every 5 minutes
        except Exception as e:
            print(f"Cleanup error: {e}")

# Start cleanup thread
cleanup_thread = threading.Thread(target=cleanup_inactive_users, daemon=True)
cleanup_thread.start()

if __name__ == '__main__':
    print("=" * 60)
    print("🎓 Smart Board Online Teaching Platform Starting...")
    print("=" * 60)
    print(f"📱 Local URL: http://localhost:5000")
    print(f"🌐 For global access, deploy to: https://edugrh.onrender.com")
    print("=" * 60)
    print("Features:")
    print("✅ Interactive Whiteboard with drawing tools")
    print("✅ Real-time audio chat with noise suppression")
    print("✅ User management with phone number collection")
    print("✅ Raise hand system for student interaction")
    print("✅ Dark mode responsive design")
    print("✅ Teacher controls for lecture management")
    print("✅ Multi-device support (Android, iOS, Desktop)")
    print("✅ User data saved to sads.py file")
    print("=" * 60)
    print("🚀 Starting server...")
    
    # Get port from environment variable (for deployment) or use 5000
    port = int(os.environ.get('PORT', 5000))
    
    # Run the application
    socketio.run(app, 
                host='0.0.0.0', 
                port=port, 
                debug=False,
                allow_unsafe_werkzeug=True)
