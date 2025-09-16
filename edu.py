import os
import json
from datetime import datetime
from flask import Flask, render_template_string, request, jsonify, session, redirect
from flask_socketio import SocketIO, emit, join_room, leave_room

app = Flask(__name__)
app.config['SECRET_KEY'] = 'edu_secret_key_2024'
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='gevent')

# Global data storage
user_data = {}
online_users = {}
hands_raised = {}
lecture_active = False
next_user_id = 1

# Load existing user data
if os.path.exists('sads.py'):
    try:
        with open('sads.py', 'r') as f:
            content = f.read()
            if content.strip():
                exec(content)
    except:
        pass

# Save user data
def save_user_data():
    with open('sads.py', 'w') as f:
        f.write(f"user_data = {json.dumps(user_data, indent=2)}\n")

@app.route('/')
def index():
    return redirect('/classroom')

@app.route('/classroom')
def classroom():
    return render_template_string(HTML_TEMPLATE)

@app.route('/api/join', methods=['POST'])
def api_join():
    global next_user_id
    name = request.form.get('name')
    phone = request.form.get('phone')
    
    if not name or not phone:
        return jsonify({'error': 'Name and phone are required'}), 400
    
    user_id = f"user_{next_user_id}"
    next_user_id += 1
    
    user_data[user_id] = {
        'id': user_id,
        'name': name, 
        'phone': phone, 
        'joined_at': datetime.now().isoformat()
    }
    
    session['user_id'] = user_id
    save_user_data()
    return jsonify({'success': True, 'user_id': user_id})

@app.route('/api/users')
def api_get_users():
    return jsonify(list(user_data.values()))

@app.route('/api/online')
def api_get_online():
    return jsonify(list(online_users.values()))

@app.route('/api/hands')
def api_get_hands():
    return jsonify(list(hands_raised.values()))

@socketio.on('connect')
def handle_connect():
    pass

@socketio.on('join_room')
def handle_join(data):
    user_id = session.get('user_id')
    if not user_id or user_id not in user_data:
        emit('error', {'msg': 'Not logged in'})
        return
    join_room('classroom')
    online_users[request.sid] = {
        'id': user_id, 
        'name': user_data[user_id]['name'],
        'sid': request.sid
    }
    emit('online_update', list(online_users.values()), broadcast=True)
    emit('lecture_status', {'active': lecture_active}, broadcast=False)
    emit('hands_update', list(hands_raised.values()), broadcast=False)

@socketio.on('disconnect')
def handle_disconnect():
    sid = request.sid
    if sid in online_users:
        name = online_users[sid]['name']
        if sid in hands_raised:
            del hands_raised[sid]
        del online_users[sid]
        emit('online_update', list(online_users.values()), broadcast=True)
        emit('hands_update', list(hands_raised.values()), broadcast=True)

@socketio.on('draw')
def handle_draw(data):
    emit('draw', data, broadcast=True, include_self=False)

@socketio.on('clear')
def handle_clear():
    emit('clear', {}, broadcast=True)

@socketio.on('raise_hand')
def handle_raise_hand():
    user_id = session.get('user_id')
    if user_id and user_id in user_data and request.sid not in hands_raised:
        hands_raised[request.sid] = {
            'user': user_data[user_id]['name'], 
            'id': user_id,
            'sid': request.sid
        }
        emit('hands_update', list(hands_raised.values()), broadcast=True)
        emit('notification', {'msg': f"{user_data[user_id]['name']} raised hand"}, broadcast=True)

@socketio.on('lower_hand')
def handle_lower_hand():
    user_id = session.get('user_id')
    if user_id and user_id in user_data and request.sid in hands_raised:
        del hands_raised[request.sid]
        emit('hands_update', list(hands_raised.values()), broadcast=True)
        emit('notification', {'msg': f"{user_data[user_id]['name']} lowered hand"}, broadcast=True)

@socketio.on('start_lecture')
def start_lecture():
    global lecture_active
    lecture_active = True
    emit('lecture_status', {'active': True}, broadcast=True)
    emit('notification', {'msg': "Lecture started"}, broadcast=True)

@socketio.on('end_lecture')
def end_lecture():
    global lecture_active
    lecture_active = False
    emit('lecture_status', {'active': False}, broadcast=True)
    emit('notification', {'msg': "Lecture ended"}, broadcast=True)

@socketio.on('audio_message')
def handle_audio_message(data):
    user_id = session.get('user_id')
    if user_id and user_id in user_data:
        data['user'] = user_data[user_id]['name']
        emit('audio_message', data, broadcast=True, include_self=False)

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    socketio.run(app, host='0.0.0.0', port=port)

# HTML Template with Dark Mode and Audio Chat
HTML_TEMPLATE = '''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>EduBoard - Online Classroom</title>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/socket.io/4.0.1/socket.io.js"></script>
    <style>
        :root {
            --bg-primary: #121212;
            --bg-secondary: #1e1e1e;
            --bg-tertiary: #2d2d2d;
            --text-primary: #ffffff;
            --text-secondary: #bbbbbb;
            --accent-primary: #4a86e8;
            --accent-secondary: #3a76d8;
            --success: #4caf50;
            --warning: #ff9800;
            --danger: #f44336;
            --info: #2196f3;
        }
        
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
        }
        
        body {
            background-color: var(--bg-primary);
            color: var(--text-primary);
            height: 100vh;
            overflow: hidden;
        }
        
        .container {
            display: flex;
            height: 100vh;
        }
        
        .sidebar {
            width: 280px;
            background-color: var(--bg-secondary);
            padding: 20px;
            display: flex;
            flex-direction: column;
            border-right: 1px solid var(--bg-tertiary);
            overflow-y: auto;
        }
        
        .main-content {
            flex: 1;
            display: flex;
            flex-direction: column;
            position: relative;
        }
        
        .header {
            background-color: var(--bg-secondary);
            padding: 15px 20px;
            display: flex;
            justify-content: space-between;
            align-items: center;
            border-bottom: 1px solid var(--bg-tertiary);
        }
        
        .logo {
            font-size: 1.5rem;
            font-weight: bold;
            color: var(--accent-primary);
        }
        
        .controls {
            display: flex;
            gap: 10px;
            flex-wrap: wrap;
        }
        
        .btn {
            background-color: var(--accent-primary);
            color: white;
            border: none;
            padding: 8px 15px;
            border-radius: 4px;
            cursor: pointer;
            font-weight: 500;
            transition: background-color 0.3s;
        }
        
        .btn:hover {
            background-color: var(--accent-secondary);
        }
        
        .btn-danger {
            background-color: var(--danger);
        }
        
        .btn-danger:hover {
            background-color: #d32f2f;
        }
        
        .btn-success {
            background-color: var(--success);
        }
        
        .btn-success:hover {
            background-color: #388e3c;
        }
        
        .btn-warning {
            background-color: var(--warning);
        }
        
        .btn-warning:hover {
            background-color: #f57c00;
        }
        
        .btn-sm {
            padding: 5px 10px;
            font-size: 0.9rem;
        }
        
        .canvas-container {
            flex: 1;
            position: relative;
            overflow: hidden;
            background-color: #000;
        }
        
        #whiteboard {
            position: absolute;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            cursor: crosshair;
        }
        
        .tool-panel {
            background-color: var(--bg-secondary);
            padding: 15px;
            display: flex;
            flex-wrap: wrap;
            gap: 10px;
            border-bottom: 1px solid var(--bg-tertiary);
        }
        
        .color-picker {
            display: flex;
            gap: 5px;
        }
        
        .color-btn {
            width: 30px;
            height: 30px;
            border-radius: 50%;
            border: 2px solid var(--bg-tertiary);
            cursor: pointer;
        }
        
        .color-btn.active {
            border-color: white;
            transform: scale(1.1);
        }
        
        .slider-container {
            display: flex;
            align-items: center;
            gap: 10px;
        }
        
        .slider {
            width: 100px;
        }
        
        .section {
            margin-bottom: 20px;
        }
        
        .section-title {
            font-size: 1.1rem;
            margin-bottom: 10px;
            color: var(--accent-primary);
            display: flex;
            align-items: center;
            gap: 8px;
        }
        
        .user-list, .hand-list {
            max-height: 200px;
            overflow-y: auto;
        }
        
        .user-item, .hand-item {
            padding: 8px 10px;
            background-color: var(--bg-tertiary);
            border-radius: 4px;
            margin-bottom: 8px;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        
        .hand-item {
            background-color: rgba(255, 152, 0, 0.1);
            border: 1px solid var(--warning);
        }
        
        .hand-item .user-name {
            font-weight: bold;
            color: var(--warning);
        }
        
        .notification {
            position: fixed;
            top: 20px;
            right: 20px;
            padding: 15px 20px;
            background-color: var(--info);
            color: white;
            border-radius: 4px;
            box-shadow: 0 4px 12px rgba(0,0,0,0.3);
            z-index: 1000;
            transform: translateX(200%);
            transition: transform 0.3s ease;
        }
        
        .notification.show {
            transform: translateX(0);
        }
        
        .login-form {
            background-color: var(--bg-secondary);
            padding: 30px;
            border-radius: 8px;
            max-width: 400px;
            margin: 50px auto;
            box-shadow: 0 4px 20px rgba(0,0,0,0.5);
        }
        
        .form-group {
            margin-bottom: 20px;
        }
        
        .form-group label {
            display: block;
            margin-bottom: 8px;
            font-weight: 500;
        }
        
        .form-group input {
            width: 100%;
            padding: 12px;
            background-color: var(--bg-tertiary);
            border: 1px solid #444;
            border-radius: 4px;
            color: var(--text-primary);
            font-size: 1rem;
        }
        
        .form-group input:focus {
            outline: none;
            border-color: var(--accent-primary);
        }
        
        .lecture-status {
            padding: 10px;
            text-align: center;
            font-weight: bold;
            border-radius: 4px;
            margin-top: 10px;
        }
        
        .lecture-active {
            background-color: rgba(76, 175, 80, 0.2);
            color: var(--success);
            border: 1px solid var(--success);
        }
        
        .lecture-inactive {
            background-color: rgba(244, 67, 54, 0.2);
            color: var(--danger);
            border: 1px solid var(--danger);
        }
        
        .audio-controls {
            display: flex;
            align-items: center;
            gap: 10px;
            margin-top: 10px;
        }
        
        .audio-btn {
            width: 40px;
            height: 40px;
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
            background-color: var(--accent-primary);
            color: white;
            border: none;
            cursor: pointer;
            transition: all 0.3s;
        }
        
        .audio-btn.recording {
            background-color: var(--danger);
            animation: pulse 1.5s infinite;
        }
        
        @keyframes pulse {
            0% { transform: scale(1); }
            50% { transform: scale(1.1); }
            100% { transform: scale(1); }
        }
        
        .audio-wave {
            flex: 1;
            height: 30px;
            background-color: var(--bg-tertiary);
            border-radius: 4px;
            display: flex;
            align-items: center;
            padding: 0 10px;
            gap: 2px;
        }
        
        .wave-bar {
            width: 3px;
            height: 10px;
            background-color: var(--accent-primary);
            border-radius: 2px;
        }
        
        .wave-bar.active {
            background-color: var(--danger);
            height: 20px;
        }
        
        .join-link {
            background-color: var(--bg-tertiary);
            padding: 15px;
            border-radius: 4px;
            margin: 15px 0;
            text-align: center;
        }
        
        .join-link a {
            color: var(--accent-primary);
            text-decoration: none;
            font-weight: bold;
            word-break: break-all;
        }
        
        .join-link a:hover {
            text-decoration: underline;
        }
        
        @media (max-width: 768px) {
            .container {
                flex-direction: column;
            }
            
            .sidebar {
                width: 100%;
                height: auto;
                max-height: 40vh;
            }
            
            .main-content {
                height: 60vh;
            }
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="sidebar">
            <div class="section">
                <h2 class="section-title">🎓 EduBoard Classroom</h2>
                <div class="join-link">
                    <p>Direct Join Link:</p>
                    <a href="https://edugrh.onrender.com/classroom" id="join-link">https://edugrh.onrender.com/classroom</a>
                </div>
                <div id="login-form">
                    <div class="form-group">
                        <label for="name">Your Name</label>
                        <input type="text" id="name" placeholder="Enter your name">
                    </div>
                    <div class="form-group">
                        <label for="phone">Phone Number</label>
                        <input type="text" id="phone" placeholder="Enter your phone">
                    </div>
                    <button class="btn" onclick="login()">Join Class</button>
                </div>
                <div id="user-controls" style="display: none;">
                    <button class="btn btn-warning" onclick="raiseHand()">✋ Raise Hand</button>
                    <button class="btn" onclick="lowerHand()">Lower Hand</button>
                    <button class="btn btn-success" onclick="startLecture()">▶ Start Lecture</button>
                    <button class="btn btn-danger" onclick="endLecture()">⏹ End Lecture</button>
                </div>
            </div>
            
            <div class="section">
                <h3 class="section-title">👥 Online Students</h3>
                <div class="user-list" id="online-list">
                    <div class="user-item">No students online</div>
                </div>
            </div>
            
            <div class="section">
                <h3 class="section-title">✋ Raised Hands</h3>
                <div class="hand-list" id="hand-list">
                    <div class="hand-item">No hands raised</div>
                </div>
            </div>
            
            <div class="section">
                <h3 class="section-title">🎤 Audio Chat</h3>
                <div class="audio-controls">
                    <button class="audio-btn" id="mic-btn" onclick="toggleMic()">
                        <span id="mic-icon">🎤</span>
                    </button>
                    <div class="audio-wave" id="audio-wave">
                        <!-- Wave bars will be generated by JS -->
                    </div>
                </div>
            </div>
            
            <div class="section">
                <h3 class="section-title">📢 Lecture Status</h3>
                <div class="lecture-status lecture-inactive" id="lecture-status">
                    Lecture: Not Started
                </div>
            </div>
        </div>
        
        <div class="main-content">
            <div class="header">
                <div class="logo">EduBoard</div>
                <div class="controls">
                    <button class="btn btn-sm" onclick="setColor('white')">White</button>
                    <button class="btn btn-sm" onclick="setColor('red')">Red</button>
                    <button class="btn btn-sm" onclick="setColor('blue')">Blue</button>
                    <button class="btn btn-sm" onclick="setColor('green')">Green</button>
                    <button class="btn btn-sm" onclick="setColor('yellow')">Yellow</button>
                    <button class="btn btn-sm btn-danger" onclick="clearCanvas()">Clear Board</button>
                </div>
            </div>
            
            <div class="tool-panel">
                <div class="color-picker">
                    <div class="color-btn active" style="background-color: white;" onclick="setColor('white')"></div>
                    <div class="color-btn" style="background-color: red;" onclick="setColor('red')"></div>
                    <div class="color-btn" style="background-color: blue;" onclick="setColor('blue')"></div>
                    <div class="color-btn" style="background-color: green;" onclick="setColor('green')"></div>
                    <div class="color-btn" style="background-color: yellow;" onclick="setColor('yellow')"></div>
                </div>
                
                <div class="slider-container">
                    <span>Size:</span>
                    <input type="range" min="1" max="20" value="5" class="slider" id="brushSize">
                </div>
                
                <button class="btn btn-sm" onclick="setColor('black')">Eraser</button>
            </div>
            
            <div class="canvas-container">
                <canvas id="whiteboard"></canvas>
            </div>
        </div>
    </div>
    
    <div class="notification" id="notification"></div>
    
    <script>
        // Initialize variables
        let socket = io();
        let isDrawing = false;
        let lastX = 0;
        let lastY = 0;
        let color = 'white';
        let brushSize = 5;
        let mediaRecorder;
        let audioChunks = [];
        let isRecording = false;
        
        // DOM Elements
        const canvas = document.getElementById('whiteboard');
        const ctx = canvas.getContext('2d');
        const notification = document.getElementById('notification');
        const micBtn = document.getElementById('mic-btn');
        const micIcon = document.getElementById('mic-icon');
        const audioWave = document.getElementById('audio-wave');
        
        // Initialize canvas
        function resizeCanvas() {
            canvas.width = canvas.parentElement.clientWidth;
            canvas.height = canvas.parentElement.clientHeight;
        }
        
        window.addEventListener('resize', resizeCanvas);
        resizeCanvas();
        
        // Create audio wave visualization
        function createAudioWave() {
            audioWave.innerHTML = '';
            for (let i = 0; i < 20; i++) {
                const bar = document.createElement('div');
                bar.className = 'wave-bar';
                audioWave.appendChild(bar);
            }
        }
        
        createAudioWave();
        
        // Show notification
        function showNotification(msg) {
            notification.textContent = msg;
            notification.classList.add('show');
            setTimeout(() => {
                notification.classList.remove('show');
            }, 3000);
        }
        
        // Login function
        function login() {
            const name = document.getElementById('name').value;
            const phone = document.getElementById('phone').value;
            
            if (!name || !phone) {
                showNotification('Please enter name and phone');
                return;
            }
            
            fetch('/api/join', {
                method: 'POST',
                headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
                body: `name=${encodeURIComponent(name)}&phone=${encodeURIComponent(phone)}`
            })
            .then(res => res.json())
            .then(data => {
                if (data.success) {
                    document.getElementById('login-form').style.display = 'none';
                    document.getElementById('user-controls').style.display = 'block';
                    socket.emit('join_room', { name, phone });
                    showNotification(`Welcome, ${name}!`);
                } else {
                    showNotification('Error joining class');
                }
            });
        }
        
        // Set drawing color
        function setColor(c) {
            color = c;
            document.querySelectorAll('.color-btn').forEach(btn => {
                btn.classList.remove('active');
            });
            event.target.classList.add('active');
        }
        
        // Set brush size
        document.getElementById('brushSize').addEventListener('input', (e) => {
            brushSize = e.target.value;
        });
        
        // Clear canvas
        function clearCanvas() {
            ctx.clearRect(0, 0, canvas.width, canvas.height);
            socket.emit('clear');
        }
        
        // Raise hand
        function raiseHand() {
            socket.emit('raise_hand');
        }
        
        // Lower hand
        function lowerHand() {
            socket.emit('lower_hand');
        }
        
        // Start lecture
        function startLecture() {
            socket.emit('start_lecture');
        }
        
        // End lecture
        function endLecture() {
            socket.emit('end_lecture');
        }
        
        // Toggle microphone
        function toggleMic() {
            if (isRecording) {
                stopRecording();
            } else {
                startRecording();
            }
        }
        
        // Start audio recording
        async function startRecording() {
            try {
                const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
                mediaRecorder = new MediaRecorder(stream);
                audioChunks = [];
                
                mediaRecorder.ondataavailable = event => {
                    audioChunks.push(event.data);
                };
                
                mediaRecorder.onstop = () => {
                    const audioBlob = new Blob(audioChunks, { type: 'audio/webm' });
                    const reader = new FileReader();
                    reader.onload = () => {
                        const base64data = reader.result.split(',')[1];
                        socket.emit('audio_message', { audio: base64data });
                    };
                    reader.readAsDataURL(audioBlob);
                };
                
                mediaRecorder.start();
                isRecording = true;
                micBtn.classList.add('recording');
                micIcon.textContent = '⏹';
                showNotification('Recording audio...');
                
                // Simulate audio wave animation
                animateAudioWave();
            } catch (err) {
                showNotification('Microphone access denied');
                console.error('Microphone error:', err);
            }
        }
        
        // Stop audio recording
        function stopRecording() {
            if (mediaRecorder && isRecording) {
                mediaRecorder.stop();
                isRecording = false;
                micBtn.classList.remove('recording');
                micIcon.textContent = '🎤';
                showNotification('Audio sent');
            }
        }
        
        // Animate audio wave
        function animateAudioWave() {
            if (!isRecording) return;
            
            const bars = document.querySelectorAll('.wave-bar');
            bars.forEach(bar => {
                const randomHeight = Math.floor(Math.random() * 20) + 5;
                bar.style.height = `${randomHeight}px`;
                bar.classList.add('active');
            });
            
            setTimeout(() => {
                bars.forEach(bar => {
                    bar.style.height = '10px';
                    bar.classList.remove('active');
                });
            }, 300);
            
            setTimeout(animateAudioWave, 300);
        }
        
        // Drawing functions
        function startDrawing(e) {
            isDrawing = true;
            [lastX, lastY] = [e.offsetX, e.offsetY];
        }
        
        function draw(e) {
            if (!isDrawing) return;
            
            ctx.lineWidth = brushSize;
            ctx.lineCap = 'round';
            ctx.strokeStyle = color === 'black' ? '#000' : color;
            
            ctx.beginPath();
            ctx.moveTo(lastX, lastY);
            ctx.lineTo(e.offsetX, e.offsetY);
            ctx.stroke();
            
            socket.emit('draw', {
                x1: lastX,
                y1: lastY,
                x2: e.offsetX,
                y2: e.offsetY,
                color: color,
                size: brushSize
            });
            
            [lastX, lastY] = [e.offsetX, e.offsetY];
        }
        
        function stopDrawing() {
            isDrawing = false;
        }
        
        // Event listeners for drawing
        canvas.addEventListener('mousedown', startDrawing);
        canvas.addEventListener('mousemove', draw);
        canvas.addEventListener('mouseup', stopDrawing);
        canvas.addEventListener('mouseout', stopDrawing);
        
        // Touch events for mobile
        canvas.addEventListener('touchstart', (e) => {
            e.preventDefault();
            const touch = e.touches[0];
            const mouseEvent = new MouseEvent('mousedown', {
                clientX: touch.clientX,
                clientY: touch.clientY
            });
            canvas.dispatchEvent(mouseEvent);
        });
        
        canvas.addEventListener('touchmove', (e) => {
            e.preventDefault();
            const touch = e.touches[0];
            const mouseEvent = new MouseEvent('mousemove', {
                clientX: touch.clientX,
                clientY: touch.clientY
            });
            canvas.dispatchEvent(mouseEvent);
        });
        
        canvas.addEventListener('touchend', (e) => {
            e.preventDefault();
            const mouseEvent = new MouseEvent('mouseup', {});
            canvas.dispatchEvent(mouseEvent);
        });
        
        // Socket event listeners
        socket.on('draw', data => {
            ctx.lineWidth = data.size;
            ctx.lineCap = 'round';
            ctx.strokeStyle = data.color === 'black' ? '#000' : data.color;
            
            ctx.beginPath();
            ctx.moveTo(data.x1, data.y1);
            ctx.lineTo(data.x2, data.y2);
            ctx.stroke();
        });
        
        socket.on('clear', () => {
            ctx.clearRect(0, 0, canvas.width, canvas.height);
        });
        
        socket.on('online_update', users => {
            const list = document.getElementById('online-list');
            if (users.length === 0) {
                list.innerHTML = '<div class="user-item">No students online</div>';
                return;
            }
            
            list.innerHTML = '';
            users.forEach(user => {
                const div = document.createElement('div');
                div.className = 'user-item';
                div.innerHTML = `
                    <span>${user.name}</span>
                    <span style="font-size: 0.8rem; color: #888;">Joined</span>
                `;
                list.appendChild(div);
            });
        });
        
        socket.on('hands_update', hands => {
            const list = document.getElementById('hand-list');
            if (hands.length === 0) {
                list.innerHTML = '<div class="hand-item">No hands raised</div>';
                return;
            }
            
            list.innerHTML = '';
            hands.forEach(hand => {
                const div = document.createElement('div');
                div.className = 'hand-item';
                div.innerHTML = `
                    <span class="user-name">${hand.user}</span>
                    <button class="btn btn-sm btn-warning" onclick="lowerSpecificHand('${hand.id}')">Lower</button>
                `;
                list.appendChild(div);
            });
        });
        
        function lowerSpecificHand(userId) {
            showNotification(`Hand lowered for ${userId}`);
        }
        
        socket.on('lecture_status', data => {
            const status = document.getElementById('lecture-status');
            if (data.active) {
                status.textContent = 'Lecture: In Progress';
                status.className = 'lecture-status lecture-active';
            } else {
                status.textContent = 'Lecture: Not Started';
                status.className = 'lecture-status lecture-inactive';
            }
        });
        
        socket.on('notification', data => {
            showNotification(data.msg);
        });
        
        socket.on('audio_message', data => {
            showNotification(`${data.user} sent audio message`);
        });
        
        // Initialize
        document.addEventListener('DOMContentLoaded', () => {
            document.getElementById('name').focus();
        });
    </script>
</body>
</html>
