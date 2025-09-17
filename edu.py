import os
import json
import uuid
import asyncio
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request, Form
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from starlette.websockets import WebSocketState
import uvicorn

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Save students' info to sads.py as a python list
STUDENTS_FILE = "sads.py"
USERS = {}
CONNECTIONS = {}
LECTURE = {"active": False, "host": None}
RAISED_HANDS = []
MESSAGES = []
AUDIO_STREAMS = {}

def load_students():
    if os.path.exists(STUDENTS_FILE):
        try:
            import importlib.util
            spec = importlib.util.spec_from_file_location("sads", STUDENTS_FILE)
            sads = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(sads)
            return getattr(sads, "students", [])
        except Exception:
            return []
    return []

def save_students(students):
    with open(STUDENTS_FILE, "w") as f:
        f.write(f"students = {json.dumps(students, indent=2)}\n")

async def notify_all(message: dict):
    remove_ws = []
    for ws in CONNECTIONS.values():
        if ws.application_state == WebSocketState.CONNECTED:
            try:
                await ws.send_json(message)
            except Exception:
                remove_ws.append(ws)
    for ws in remove_ws:
        await disconnect_ws(ws)

async def disconnect_ws(ws):
    for k, v in list(CONNECTIONS.items()):
        if v == ws:
            del CONNECTIONS[k]
            USERS.pop(k, None)
            break

@app.get("/", response_class=HTMLResponse)
async def home():
    return FileResponse("index.html")

@app.get("/style.css")
async def style():
    return FileResponse("style.css")

@app.get("/favicon.ico")
async def favicon():
    return FileResponse("favicon.ico")

@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await ws.accept()
    user_id = str(uuid.uuid4())
    CONNECTIONS[user_id] = ws
    username = None
    phone = None
    try:
        while True:
            data = await ws.receive_json()
            if data["type"] == "register":
                username, phone = data["username"], data["phone"]
                USERS[user_id] = {"username": username, "phone": phone, "is_host": False}
                # Save user to file if not exists
                students = load_students()
                if not any(s["username"] == username and s["phone"] == phone for s in students):
                    students.append({"username": username, "phone": phone})
                    save_students(students)
                # If first, make host
                if LECTURE["host"] is None:
                    LECTURE["host"] = user_id
                    USERS[user_id]["is_host"] = True
                await notify_all({
                    "type": "user_list",
                    "users": [
                        {"username": u["username"], "is_host": u["is_host"]}
                        for u in USERS.values()
                    ]
                })
                await notify_all({
                    "type": "status",
                    "online": len(CONNECTIONS),
                    "lecture_active": LECTURE["active"],
                    "host": USERS.get(LECTURE["host"], {}).get("username")
                })
            elif data["type"] == "start_lecture":
                if USERS[user_id]["is_host"]:
                    LECTURE["active"] = True
                    await notify_all({
                        "type": "lecture_status",
                        "active": True,
                        "host": USERS[user_id]["username"]
                    })
            elif data["type"] == "end_lecture":
                if USERS[user_id]["is_host"]:
                    LECTURE["active"] = False
                    await notify_all({
                        "type": "lecture_status",
                        "active": False,
                        "host": USERS[user_id]["username"]
                    })
            elif data["type"] == "chat":
                message = {
                    "type": "chat",
                    "user": USERS[user_id]["username"],
                    "msg": data["msg"]
                }
                MESSAGES.append(message)
                await notify_all(message)
            elif data["type"] == "raise_hand":
                if user_id not in RAISED_HANDS:
                    RAISED_HANDS.append(user_id)
                await notify_all({
                    "type": "raised_hands",
                    "users": [USERS[uid]["username"] for uid in RAISED_HANDS]
                })
            elif data["type"] == "lower_hand":
                if user_id in RAISED_HANDS:
                    RAISED_HANDS.remove(user_id)
                await notify_all({
                    "type": "raised_hands",
                    "users": [USERS[uid]["username"] for uid in RAISED_HANDS]
                })
            elif data["type"] == "audio":
                # Broadcast audio to all except sender (opus base64 or PCM base64)
                for uid, ws2 in CONNECTIONS.items():
                    if uid != user_id and ws2.application_state == WebSocketState.CONNECTED:
                        try:
                            await ws2.send_json({
                                "type": "audio",
                                "user": USERS[user_id]["username"],
                                "audio": data["audio"]
                            })
                        except Exception:
                            pass
            elif data["type"] == "board":
                # Broadcast board actions
                await notify_all({
                    "type": "board",
                    "user": USERS[user_id]["username"],
                    "action": data["action"],
                    "payload": data["payload"]
                })
    except WebSocketDisconnect:
        await disconnect_ws(ws)
        if user_id == LECTURE["host"]:
            LECTURE["host"] = None
            LECTURE["active"] = False
            await notify_all({
                "type": "lecture_status",
                "active": False,
                "host": None
            })
        await notify_all({
            "type": "user_list",
            "users": [
                {"username": u["username"], "is_host": u["is_host"]}
                for u in USERS.values()
            ]
        })
        await notify_all({
            "type": "status",
            "online": len(CONNECTIONS),
            "lecture_active": LECTURE["active"],
            "host": USERS.get(LECTURE["host"], {}).get("username")
        })

# ---- HTML/JS/CSS for the app (single-file hosting) ----

with open("index.html", "w") as f:
    f.write(r"""
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8" />
<meta name="viewport" content="width=device-width,initial-scale=1" />
<title>EduGRH SmartBoard</title>
<link rel="stylesheet" href="/style.css">
<link rel="icon" href="/favicon.ico">
</head>
<body>
<div id="app" class="dark">
  <div class="header">
    <h2>EduGRH SmartBoard</h2>
    <span id="lecture-status"></span>
    <span id="online-status"></span>
  </div>
  <div id="register-form" class="modal">
    <h3>Join Lecture</h3>
    <input id="username" placeholder="Username">
    <input id="phone" placeholder="Phone Number">
    <button onclick="register()">Join</button>
  </div>
  <div id="main-ui" style="display:none;">
    <div class="topbar">
      <span id="host-controls" style="display:none;">
        <button onclick="startLecture()">Start Lecture</button>
        <button onclick="endLecture()">End Lecture</button>
      </span>
      <span>
        <button onclick="raiseHand()" id="handBtn">Raise Hand ✋</button>
        <button onclick="lowerHand()" id="lowerHandBtn" style="display:none;">Lower Hand ✋</button>
        <button onclick="toggleMic()" id="micBtn">🎤 Enable Mic</button>
      </span>
      <span id="userlist"></span>
    </div>
    <div class="mainrow">
      <div class="board-col">
        <canvas id="board" width="800" height="400"></canvas>
        <div class="tools">
          <select id="tool">
            <option value="pen">Pen</option>
            <option value="eraser">Eraser</option>
          </select>
          <input type="color" id="color" value="#f8c471">
          <input type="range" id="size" min="2" max="20" value="5">
          <button onclick="clearBoard()">Clear</button>
        </div>
      </div>
      <div class="chat-col">
        <div class="chatbox" id="chat"></div>
        <input id="chatmsg" placeholder="Type message..." onkeydown="if(event.key==='Enter'){sendChat()}">
        <button onclick="sendChat()">Send</button>
        <div id="raisedHands"></div>
      </div>
    </div>
  </div>
</div>
<script>
let ws, username, phone, isHost=false, micOn=false, audioStream=null, audioCtx=null, audioInput=null, processor=null, handRaised=false;
const url = (window.location.protocol==='https:'?'wss':'ws')+'://'+window.location.host+'/ws';

function register() {
  username = document.getElementById('username').value.trim();
  phone = document.getElementById('phone').value.trim();
  if (!username || !phone) return alert('Please enter username and phone');
  ws = new WebSocket(url);
  ws.onopen = () => {
    ws.send(JSON.stringify({type:'register', username, phone}));
    document.getElementById('register-form').style.display = 'none';
    document.getElementById('main-ui').style.display = '';
  };
  ws.onmessage = (e) => {
    const d = JSON.parse(e.data);
    if (d.type==='user_list'){
      let ulist = '';
      d.users.forEach(u=>{ ulist += `<span class="user${u.is_host?' host':''}">${u.username}${u.is_host?' (Host)':''}</span>`; });
      document.getElementById('userlist').innerHTML = ulist;
    }
    if (d.type==='status'){
      document.getElementById('online-status').innerText = `Online: ${d.online}`;
      document.getElementById('lecture-status').innerText = d.lecture_active ? "Lecture: LIVE" : "Lecture: Ended";
      if (d.host && d.host===username) {
        isHost = true;
        document.getElementById('host-controls').style.display = '';
      }
    }
    if (d.type==='lecture_status'){
      document.getElementById('lecture-status').innerText = d.active ? "Lecture: LIVE" : "Lecture: Ended";
    }
    if (d.type==='chat'){
      document.getElementById('chat').innerHTML += `<div><b>${d.user}:</b> ${d.msg}</div>`;
      document.getElementById('chat').scrollTop = 1e6;
    }
    if (d.type==='raised_hands'){
      const hands = d.users.map(u=>`<div>${u} ✋</div>`).join('');
      document.getElementById('raisedHands').innerHTML = hands;
    }
    if (d.type==='audio'){
      // Play incoming audio
      playAudio(d.audio);
    }
    if (d.type==='board'){
      drawRemote(d);
    }
  };
  ws.onclose = ()=>{ alert('Disconnected. Please refresh.'); };
}

function sendChat() {
  let msg = document.getElementById('chatmsg').value.trim();
  if (!msg) return;
  ws.send(JSON.stringify({type:'chat', msg}));
  document.getElementById('chatmsg').value = '';
}

function startLecture() { ws.send(JSON.stringify({type:'start_lecture'})); }
function endLecture() { ws.send(JSON.stringify({type:'end_lecture'})); }

function raiseHand() {
  ws.send(JSON.stringify({type:'raise_hand'}));
  document.getElementById('handBtn').style.display='none';
  document.getElementById('lowerHandBtn').style.display='';
  handRaised = true;
}
function lowerHand() {
  ws.send(JSON.stringify({type:'lower_hand'}));
  document.getElementById('handBtn').style.display='';
  document.getElementById('lowerHandBtn').style.display='none';
  handRaised = false;
}

function toggleMic() {
  if (!micOn) enableMic();
  else disableMic();
}

async function enableMic() {
  try {
    audioStream = await navigator.mediaDevices.getUserMedia({audio:true});
    audioCtx = new (window.AudioContext || window.webkitAudioContext)({sampleRate:16000});
    audioInput = audioCtx.createMediaStreamSource(audioStream);
    processor = audioCtx.createScriptProcessor(2048,1,1);
    audioInput.connect(processor);
    processor.connect(audioCtx.destination);
    processor.onaudioprocess = function(e){
      const input = e.inputBuffer.getChannelData(0);
      // Convert to 16bit PCM
      let pcm = new Int16Array(input.length);
      for(let i=0;i<input.length;i++) pcm[i] = input[i]*0x7FFF;
      // Send as base64
      let b64 = btoa(String.fromCharCode.apply(null, new Uint8Array(pcm.buffer)));
      ws.send(JSON.stringify({type:'audio',audio:b64}));
    }
    document.getElementById('micBtn').innerText = '🎤 Mic ON';
    micOn = true;
  } catch(e) {
    alert('Mic error: '+e);
  }
}

function disableMic() {
  if(processor)processor.disconnect();
  if(audioInput)audioInput.disconnect();
  if(audioStream)audioStream.getTracks().forEach(t=>t.stop());
  document.getElementById('micBtn').innerText = '🎤 Enable Mic';
  micOn = false;
}

function playAudio(b64) {
  // Decode base64 PCM16, play with Web Audio API
  const pcm = atob(b64);
  const buf = new ArrayBuffer(pcm.length);
  const view = new Uint8Array(buf);
  for(let i=0;i<pcm.length;i++) view[i]=pcm.charCodeAt(i);
  const audioCtx2 = new (window.AudioContext || window.webkitAudioContext)({sampleRate:16000});
  const floatBuf = new Float32Array(buf.byteLength/2);
  for(let i=0;i<floatBuf.length;i++) {
    floatBuf[i]= (new Int16Array(buf)[i])/0x7FFF;
  }
  const audioBuffer = audioCtx2.createBuffer(1,floatBuf.length,16000);
  audioBuffer.getChannelData(0).set(floatBuf);
  const src = audioCtx2.createBufferSource();
  src.buffer = audioBuffer;
  src.connect(audioCtx2.destination);
  src.start();
}

//// Whiteboard Implementation ////
let board = document.getElementById('board');
let ctx = board.getContext('2d');
let drawing = false, lastX=0, lastY=0;
let tool = 'pen', color='#f8c471', size=5;

document.getElementById('tool').onchange = e=>tool = e.target.value;
document.getElementById('color').onchange = e=>color = e.target.value;
document.getElementById('size').onchange = e=>size = e.target.value;

board.onpointerdown = e=>{
  drawing=true; lastX=e.offsetX; lastY=e.offsetY;
};
board.onpointerup = e=>{
  if(drawing) sendBoard('end', {});
  drawing = false;
};
board.onpointermove = e=>{
  if(!drawing)return;
  ctx.lineWidth=size;
  ctx.strokeStyle=tool==='pen'?color:'#222';
  ctx.globalCompositeOperation = tool==='pen'?'source-over':'destination-out';
  ctx.beginPath();
  ctx.moveTo(lastX,lastY);
  ctx.lineTo(e.offsetX,e.offsetY);
  ctx.stroke();
  sendBoard('draw', {x1:lastX, y1:lastY, x2:e.offsetX, y2:e.offsetY, tool, color, size});
  lastX=e.offsetX; lastY=e.offsetY;
}

function sendBoard(action, payload) {
  ws.send(JSON.stringify({type:'board', action, payload}));
}
function drawRemote(d) {
  if(d.action==='draw'){
    ctx.lineWidth=d.payload.size;
    ctx.strokeStyle=d.payload.tool==='pen'?d.payload.color:'#222';
    ctx.globalCompositeOperation = d.payload.tool==='pen'?'source-over':'destination-out';
    ctx.beginPath();
    ctx.moveTo(d.payload.x1,d.payload.y1);
    ctx.lineTo(d.payload.x2,d.payload.y2);
    ctx.stroke();
  }
  if(d.action==='clear'){
    ctx.clearRect(0,0,board.width,board.height);
  }
}
function clearBoard() {
  ctx.clearRect(0,0,board.width,board.height);
  sendBoard('clear', {});
}
</script>
</body>
</html>
""")

with open("style.css", "w") as f:
    f.write("""
body,html { margin:0; padding:0; font-family:sans-serif; background:#111; color:#f8c471; }
.dark { background:#111; color:#f8c471; min-height:100vh; }
.header { background:#222; color:#f8c471; padding:12px; font-size:1.1em; display:flex; justify-content:space-between; align-items:center; }
.modal { background:#222; padding:24px; border-radius:10px; max-width:300px; margin:40px auto; box-shadow:0 0 8px #444; }
input,select,button { margin:6px 0; width:100%; padding:8px; font-size:1em; background:#222; color:#f8c471; border:1px solid #444; border-radius:5px; }
button { cursor:pointer; background:#f8c471; color:#222; border:none; }
button:hover { background:#f39c12; }
.topbar { background:#222; padding:8px; display:flex; justify-content:space-between; align-items:center; }
.user { margin-right:10px; }
.user.host { color:#f39c12; font-weight:bold; }
.mainrow { display:flex; margin:0; }
.board-col { flex:2; padding:12px; }
.chat-col { flex:1; background:#222; padding:12px; border-left:2px solid #444; }
#board { width:100%; max-width:800px; background:#181818; border-radius:8px; box-shadow:0 0 11px #222; display:block; margin:0 auto; }
.tools { margin-top:8px; display:flex; gap:8px; }
.chatbox { height:300px; overflow-y:auto; background:#181818; border-radius:5px; padding:8px; margin-bottom:8px; }
#chatmsg { width:80%; }
@media (max-width:900px) {
  .mainrow { flex-direction:column; }
  .board-col, .chat-col { width:100%; }
}
""")

with open("favicon.ico", "wb") as f:
    f.write(b"\x00\x00\x01\x00\x01\x00\x10\x10\x10\x00\x00\x00\x00\x00\x68\x00\x00\x00\x16\x00\x00\x00\x28\x00\x00\x00\x10\x00\x00\x00\x10\x00\x00\x00\x01\x00\x04\x00\x00\x00\x00\x00\x40\x00\x00\x00\x13\x0B\x00\x00\x13\x0B\x00\x00\x04\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00")

# ---- End of static files ----

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    uvicorn.run(app, host="0.0.0.0", port=port)
