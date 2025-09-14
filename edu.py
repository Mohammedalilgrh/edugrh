# edu.py
import socketio
from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
import uvicorn, os

# Create FastAPI + Socket.IO
sio = socketio.AsyncServer(cors_allowed_origins="*")
app = FastAPI()
sio_app = socketio.ASGIApp(sio, app)

# Serve static frontend
if not os.path.exists("static"):
    os.mkdir("static")

app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/")
async def index():
    return FileResponse("static/index.html")

# ----- Socket.IO events -----
USERS = {}

@sio.event
async def connect(sid, environ):
    USERS[sid] = {"role": "student"}
    print(f"Student connected: {sid}")
    await sio.emit("update_users", {"count": len(USERS)})

@sio.event
async def disconnect(sid):
    USERS.pop(sid, None)
    print(f"User left: {sid}")
    await sio.emit("update_users", {"count": len(USERS)})

@sio.on("draw")
async def handle_draw(sid, data):
    if USERS[sid]["role"] == "teacher":
        await sio.emit("draw", data)

@sio.on("raise_hand")
async def handle_raise_hand(sid, data):
    await sio.emit("hand_raised", {"sid": sid})

# ----- Teacher login -----
@sio.on("set_teacher")
async def set_teacher(sid, data):
    USERS[sid]["role"] = "teacher"
    print(f"Teacher set: {sid}")
    await sio.emit("teacher_online", {"sid": sid})

if __name__ == "__main__":
    uvicorn.run(sio_app, host="0.0.0.0", port=8000)
