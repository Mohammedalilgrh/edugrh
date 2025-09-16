import os
import json
from datetime import datetime
from flask import Flask, render_template_string, request, jsonify, session, redirect
from flask_socketio import SocketIO, emit, join_room, leave_room

app = Flask(__name__)
app.config['SECRET_KEY'] = 'edu_secret_key_2024'
# Use eventlet to avoid any gevent C‐build issues
socketio = SocketIO(app,
                    cors_allowed_origins="*",
                    async_mode='eventlet')

# In‐memory stores
user_data = {}
online_users = {}
hands_raised = {}
lecture_active = False
next_user_id = 1

# Load persisted users
if os.path.exists('sads.py'):
    try:
        import sads
        user_data = sads.user_data
        # derive next_user_id
        existing = [int(u.split('_')[1]) for u in user_data.keys() if u.startswith('user_')]
        if existing:
            next_user_id = max(existing) + 1
    except Exception:
        pass

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
    emit('lecture_status', {'active': lecture_active})
    emit('hands_update', list(hands_raised.values()))

@socketio.on('disconnect')
def handle_disconnect():
    sid = request.sid
    if sid in online_users:
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
    if user_id and request.sid in hands_raised:
        name = hands_raised[request.sid]['user']
        del hands_raised[request.sid]
        emit('hands_update', list(hands_raised.values()), broadcast=True)
        emit('notification', {'msg': f"{name} lowered hand"}, broadcast=True)

@socketio.on('lower_specific_hand')
def handle_lower_specific_hand(data):
    sid = data.get('sid')
    if sid and sid in hands_raised:
        name = hands_raised[sid]['user']
        del hands_raised[sid]
        emit('hands_update', list(hands_raised.values()), broadcast=True)
        emit('notification', {'msg': f"{name}’s hand lowered"}, broadcast=True)

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
    # eventlet WSGI server
    socketio.run(app, host='0.0.0.0', port=port)
    

HTML_TEMPLATE = '''
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width,initial-scale=1.0">
  <title>EduBoard - Online Classroom</title>
  <script src="https://cdnjs.cloudflare.com/ajax/libs/socket.io/4.0.1/socket.io.min.js"></script>
  <style>
    /* ... your existing dark‐mode CSS ... (omitted for brevity) */
    /* Copy/paste all the CSS from your prior template here */
  </style>
</head>
<body>
<div class="container">
  <!-- SIDEBAR -->
  <div class="sidebar">
    <!-- Login / Controls -->
    <div id="login-form">
      <div class="form-group">
        <label>Your Name</label>
        <input type="text" id="name" placeholder="Enter your name">
      </div>
      <div class="form-group">
        <label>Phone Number</label>
        <input type="text" id="phone" placeholder="Enter your phone">
      </div>
      <button class="btn" onclick="login()">Join Class</button>
    </div>
    <div id="user-controls" style="display:none;">
      <button class="btn btn-warning" onclick="raiseHand()">✋ Raise Hand</button>
      <button class="btn" onclick="lowerHand()">Lower Hand</button>
      <button class="btn btn-success" onclick="startLecture()">▶ Start Lecture</button>
      <button class="btn btn-danger" onclick="endLecture()">⏹ End Lecture</button>
    </div>
    <!-- Online List -->
    <h3>👥 Online Students</h3>
    <div id="online-list"><div class="user-item">No students online</div></div>
    <!-- Raised Hands -->
    <h3>✋ Raised Hands</h3>
    <div id="hand-list"><div class="hand-item">No hands raised</div></div>
    <!-- Lecture Status -->
    <h3>📢 Lecture Status</h3>
    <div id="lecture-status" class="lecture-status lecture-inactive">Lecture: Not Started</div>
  </div>

  <!-- MAIN CONTENT -->
  <div class="main-content">
    <div class="header">
      <div class="logo">EduBoard</div>
      <div class="controls">
        <button class="btn btn-sm" onclick="setColor('white', this)">White</button>
        <button class="btn btn-sm" onclick="setColor('red', this)">Red</button>
        <button class="btn btn-sm" onclick="setColor('blue', this)">Blue</button>
        <button class="btn btn-sm" onclick="setColor('green', this)">Green</button>
        <button class="btn btn-sm" onclick="setColor('yellow', this)">Yellow</button>
        <button class="btn btn-sm btn-danger" onclick="clearCanvas()">Clear Board</button>
      </div>
    </div>
    <div class="tool-panel">
      <div class="color-picker">
        <div class="color-btn active" style="background:white;" onclick="setColor('white', this)"></div>
        <div class="color-btn" style="background:red;" onclick="setColor('red', this)"></div>
        <div class="color-btn" style="background:blue;" onclick="setColor('blue', this)"></div>
        <div class="color-btn" style="background:green;" onclick="setColor('green', this)"></div>
        <div class="color-btn" style="background:yellow;" onclick="setColor('yellow', this)"></div>
      </div>
      <div class="slider-container">
        <span>Size:</span>
        <input type="range" min="1" max="20" value="5" id="brushSize" class="slider">
      </div>
      <button class="btn btn-sm" onclick="setColor('black', this)">Eraser</button>
    </div>
    <div class="canvas-container">
      <canvas id="whiteboard"></canvas>
    </div>
  </div>
</div>

<div class="notification" id="notification"></div>

<script>
  const socket = io();
  let isDrawing = false, lastX = 0, lastY = 0;
  let color = 'white', brushSize = 5;
  let mediaRecorder, audioChunks = [], isRecording = false;

  const canvas = document.getElementById('whiteboard');
  const ctx = canvas.getContext('2d');
  const notif = document.getElementById('notification');
  const micBtn = document.getElementById('mic-btn');
  const micIcon = document.getElementById('mic-icon');
  const audioWave = document.getElementById('audio-wave');

  function resizeCanvas() {
    canvas.width = canvas.parentElement.clientWidth;
    canvas.height = canvas.parentElement.clientHeight;
  }
  window.addEventListener('resize', resizeCanvas);
  resizeCanvas();

  function showNotification(msg) {
    notif.textContent = msg;
    notif.classList.add('show');
    setTimeout(()=>notif.classList.remove('show'), 3000);
  }

  function login() {
    const name = document.getElementById('name').value.trim();
    const phone = document.getElementById('phone').value.trim();
    if (!name||!phone) return showNotification('Name & phone required');
    fetch('/api/join', {
      method:'POST',
      headers:{'Content-Type':'application/x-www-form-urlencoded'},
      body:`name=${encodeURIComponent(name)}&phone=${encodeURIComponent(phone)}`
    })
    .then(r=>r.json())
    .then(d=>{
      if(d.success){
        document.getElementById('login-form').style.display='none';
        document.getElementById('user-controls').style.display='block';
        socket.emit('join_room',{});
        showNotification(`Welcome, ${name}!`);
      } else showNotification('Error joining');
    });
  }

  function setColor(c, btnEl){
    color = c;
    document.querySelectorAll('.color-btn').forEach(b=>b.classList.remove('active'));
    btnEl.classList.add('active');
  }
  document.getElementById('brushSize').addEventListener('input', e=>brushSize=e.target.value);

  function clearCanvas(){
    ctx.clearRect(0,0,canvas.width,canvas.height);
    socket.emit('clear');
  }
  function raiseHand(){ socket.emit('raise_hand'); }
  function lowerHand(){ socket.emit('lower_hand'); }
  function startLecture(){ socket.emit('start_lecture'); }
  function endLecture()  { socket.emit('end_lecture'); }

  function lowerSpecificHand(sid){
    socket.emit('lower_specific_hand',{sid});
  }

  // Drawing
  function startDrawing(e){
    isDrawing=true;
    [lastX,lastY] = 
      [e.offsetX||e.touches[0].clientX, e.offsetY||e.touches[0].clientY];
  }
  function draw(e){
    if(!isDrawing)return;
    let x = e.offsetX||e.touches[0].clientX;
    let y = e.offsetY||e.touches[0].clientY;
    ctx.strokeStyle = (color==='black'?'#000':color);
    ctx.lineWidth = brushSize;
    ctx.lineCap = 'round';
    ctx.beginPath();
    ctx.moveTo(lastX,lastY);
    ctx.lineTo(x,y);
    ctx.stroke();
    socket.emit('draw',{x1:lastX,y1:lastY,x2:x,y2:y,color, size:brushSize});
    [lastX,lastY]=[x,y];
  }
  function stopDrawing(){ isDrawing=false; }

  canvas.addEventListener('mousedown', startDrawing);
  canvas.addEventListener('mousemove', draw);
  canvas.addEventListener('mouseup', stopDrawing);
  canvas.addEventListener('mouseout', stopDrawing);
  // touch
  canvas.addEventListener('touchstart', e=>{ e.preventDefault(); startDrawing(e); });
  canvas.addEventListener('touchmove',  e=>{ e.preventDefault(); draw(e);  });
  canvas.addEventListener('touchend',   e=>{ e.preventDefault(); stopDrawing(); });

  // Socket events
  socket.on('draw', data=>{
    ctx.strokeStyle = (data.color==='black'?'#000':data.color);
    ctx.lineWidth = data.size;
    ctx.lineCap = 'round';
    ctx.beginPath();
    ctx.moveTo(data.x1,data.y1);
    ctx.lineTo(data.x2,data.y2);
    ctx.stroke();
  });
  socket.on('clear', ()=>ctx.clearRect(0,0,canvas.width,canvas.height));
  socket.on('online_update', users=>{
    const list = document.getElementById('online-list');
    if(!users.length) return list.innerHTML='<div class="user-item">No students online</div>';
    list.innerHTML='';
    users.forEach(u=>{
      const d=document.createElement('div');
      d.className='user-item';
      d.textContent = u.name;
      list.appendChild(d);
    });
  });
  socket.on('hands_update', hands=>{
    const list = document.getElementById('hand-list');
    if(!hands.length) return list.innerHTML='<div class="hand-item">No hands raised</div>';
    list.innerHTML='';
    hands.forEach(h=>{
      const d=document.createElement('div');
      d.className='hand-item';
      d.innerHTML = `
        <span class="user-name">${h.user}</span>
        <button class="btn btn-sm btn-warning" onclick="lowerSpecificHand('${h.sid}')">Lower</button>
      `;
      list.appendChild(d);
    });
  });
  socket.on('lecture_status', data=>{
    const s=document.getElementById('lecture-status');
    if(data.active){
      s.textContent='Lecture: In Progress';
      s.className='lecture-status lecture-active';
    } else {
      s.textContent='Lecture: Not Started';
      s.className='lecture-status lecture-inactive';
    }
  });
  socket.on('notification', d=>showNotification(d.msg));
  socket.on('audio_message', d=>showNotification(`${d.user} sent audio`));
</script>
</body>
</html>
