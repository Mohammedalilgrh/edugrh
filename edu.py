import uvicorn,os,json
from fastapi import FastAPI,WebSocket
from fastapi.responses import HTMLResponse

app=FastAPI()
USERS,WS,HS=[],[],[]

@app.get("/")
def root():
    return HTMLResponse(open("i.html").read())

@app.websocket("/ws")
async def ws(ws:WebSocket):
    await ws.accept()
    u,p=None,None
    try:
        while 1:
            d=await ws.receive_json()
            if d["t"]=="reg":
                u,p=d["u"],d["p"]
                USERS.append((u,p))
                WS.append(ws)
                save_users()
                await bc({"t":"usr","l":USERS})
            elif d["t"]=="msg":
                await bc({"t":"msg","u":u,"m":d["m"]})
            elif d["t"]=="brd":
                await bc({"t":"brd","d":d["d"]})
            elif d["t"]=="aud":
                await bc({"t":"aud","a":d["a"]},ws)
            elif d["t"]=="hand":
                if u not in HS: HS.append(u)
                await bc({"t":"hands","hs":HS})
            elif d["t"]=="down":
                if u in HS: HS.remove(u)
                await bc({"t":"hands","hs":HS})
    except:
        if ws in WS: WS.remove(ws)
        if (u,p) in USERS: USERS.remove((u,p))
        if u in HS: HS.remove(u)
        await bc({"t":"usr","l":USERS})

def save_users():
    with open("sads.py","w") as f:
        f.write("sads="+json.dumps(USERS))

async def bc(m,exc=None):
    for w in WS:
        if w!=exc:
            try: await w.send_json(m)
            except: pass

with open("i.html","w") as f: f.write('''<!doctype html><html><body style="background:#111;color:#f8c471;"><div id=r><h2>EduGRH</h2><input id=u placeholder="Name"><input id=p placeholder="Phone"><button onclick="R()">Join</button></div><div id=a style="display:none"><canvas id=b width=800 height=400 style="background:#181818;border-radius:8px;"></canvas><br><input id=m placeholder="chat"><button onclick="M()">Send</button><button onclick="H()">✋</button><button onclick="D()">Down</button><button onclick="X()">Mic</button><div id=c></div><div id=h></div></div><script>let ws,u,p,ctx,drw=0,lx,ly,mc=0,au,pr;function R(){u=u.value=document.getElementById("u").value;p=p.value=document.getElementById("p").value;ws=new WebSocket((location.protocol==="https:"?"wss://":"ws://")+location.host+"/ws");ws.onopen=()=>{ws.send(JSON.stringify({t:"reg",u:u,p:p}));r.style.display="none";a.style.display="block";ctx=b.getContext("2d");};ws.onmessage=(e)=>{let d=JSON.parse(e.data);if(d.t=="usr"){c.innerHTML=d.l.map(x=>x[0]+"<br>").join("");}if(d.t=="msg"){c.innerHTML+="<div><b>"+d.u+":</b> "+d.m+"</div>";}if(d.t=="brd"){let x=d.d;ctx.lineWidth=x[2];ctx.strokeStyle=x[3];ctx.beginPath();ctx.moveTo(x[0],x[1]);ctx.lineTo(x[4],x[5]);ctx.stroke();}if(d.t=="aud"){if(!mc){let ab=atob(d.a),buf=new ArrayBuffer(ab.length),vw=new Uint8Array(buf);for(let i=0;i<ab.length;i++)vw[i]=ab.charCodeAt(i);let ac=new(window.AudioContext||window.webkitAudioContext)({sampleRate:16000}),f32=new Float32Array(buf.byteLength/2);for(let i=0;i<f32.length;i++)f32[i]=new Int16Array(buf)[i]/32768;let abf=ac.createBuffer(1,f32.length,16000);abf.getChannelData(0).set(f32);let s=ac.createBufferSource();s.buffer=abf;s.connect(ac.destination);s.start();}}if(d.t=="hands"){h.innerHTML="Hands:"+d.hs.join(", ");}};}function M(){ws.send(JSON.stringify({t:"msg",m:m.value}));m.value="";}b.onpointerdown=e=>{drw=1;lx=e.offsetX;ly=e.offsetY;};b.onpointermove=e=>{if(drw){ctx.lineWidth=3;ctx.strokeStyle="#f8c471";ctx.beginPath();ctx.moveTo(lx,ly);ctx.lineTo(e.offsetX,e.offsetY);ctx.stroke();ws.send(JSON.stringify({t:"brd",d:[lx,ly,3,"#f8c471",e.offsetX,e.offsetY]}));lx=e.offsetX;ly=e.offsetY;}};b.onpointerup=e=>{drw=0;};function H(){ws.send(JSON.stringify({t:"hand"}));}function D(){ws.send(JSON.stringify({t:"down"}));}function X(){if(mc)return mc=0;if(navigator.mediaDevices){navigator.mediaDevices.getUserMedia({audio:true}).then(s=>{au=new(window.AudioContext||window.webkitAudioContext)({sampleRate:16000});pr=au.createMediaStreamSource(s);let p=au.createScriptProcessor(2048,1,1);pr.connect(p);p.connect(au.destination);p.onaudioprocess=function(e){let i=e.inputBuffer.getChannelData(0),pcm=new Int16Array(i.length);for(let j=0;j<i.length;j++)pcm[j]=i[j]*32767;let btoa=window.btoa(String.fromCharCode.apply(null,new Uint8Array(pcm.buffer)));ws.send(JSON.stringify({t:"aud",a:btoa}));};mc=1;});}}</script></body></html>''')

if not os.path.exists("sads.py"): open("sads.py","w").write("sads=[]")
if __name__=="__main__":
    uvicorn.run(app,host="0.0.0.0",port=int(os.environ.get("PORT",10000)))
