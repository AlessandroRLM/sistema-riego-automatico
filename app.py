#!/usr/bin/env python3
"""Panel local de riego: modo simulado (slider) o real (lee el Arduino por serie).
Uso: python app.py [puerto_http=8000] [/dev/ttyACM0]   ->  http://localhost:8000
Sin dependencias: el puerto serie se lee con stty + open() (solo Linux).
"""
import glob, json, os, re, select, subprocess, sys, threading, time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

# Mismos valores que el sketch
UMBRAL_ENCENDER, UMBRAL_APAGAR = 35, 55
RIE = re.compile(r"riego=(\d)")
SIL = re.compile(r"silencio=(\d)")
LINE = re.compile(r"raw=(\d+)\s+humedad=(\d+)%\s+estado=(\w+)")

state = {
    "modo": "simulado",   # simulado | real
    "humedad": 50,        # % simulado
    "bomba": False,       # bomba simulada
    "lectura": True,      # False = puerto serie liberado (p. ej. para subir el sketch)
    "manual": False,      # True = bomba forzada a mano, ignora histéresis
    "real": {"raw": None, "humedad": None, "bomba": None, "ts": 0, "puerto": None},
}
lock = threading.Lock()


def histeresis():
    """Misma lógica que loop() del Arduino."""
    if not state["bomba"] and state["humedad"] < UMBRAL_ENCENDER:
        state["bomba"] = True
    elif state["bomba"] and state["humedad"] >= UMBRAL_APAGAR:
        state["bomba"] = False


fd = None  # puerto serie abierto (lectura y escritura)


def enviar(cmd):
    """Manda comandos al Arduino (si está conectado)."""
    if fd is not None:
        try:
            os.write(fd, cmd.encode())
        except OSError:
            pass


def lector_serie(puerto_fijo):
    global fd
    while True:
        if not state["lectura"]:
            time.sleep(0.5); continue
        puerto = puerto_fijo or next(iter(sorted(glob.glob("/dev/ttyACM*") + glob.glob("/dev/ttyUSB*"))), None)
        if not puerto:
            time.sleep(2); continue
        try:
            subprocess.run(["stty", "-F", puerto, "9600", "raw", "-echo", "-hupcl"], check=True)
            fd = os.open(puerto, os.O_RDWR | os.O_NOCTTY)
            buf = b""
            while state["lectura"]:
                if not select.select([fd], [], [], 0.5)[0]:
                    continue
                datos = os.read(fd, 256)
                if not datos:
                    raise OSError
                buf += datos
                *lineas, buf = buf.split(b"\n")
                for linea in lineas:
                    txt = linea.decode(errors="ignore")
                    m = LINE.search(txt)
                    if m:
                        sil, rie = SIL.search(txt), RIE.search(txt)
                        with lock:
                            state["real"] = {"raw": int(m[1]), "humedad": int(m[2]),
                                             "bomba": m[3] == "REGANDO", "silencio": bool(sil and sil[1] == "1"), "habilitado": bool(rie and rie[1] == "1"), "ts": time.time(), "puerto": puerto}
        except Exception:
            pass
        finally:
            with lock:
                state["real"]["puerto"] = None
            if fd is not None:
                try: os.close(fd)
                except OSError: pass
                fd = None
            time.sleep(2)


HTML = """<!doctype html><meta charset=utf-8><meta name=viewport content="width=device-width,initial-scale=1">
<title>Riego</title>
<style>
body{font-family:system-ui;max-width:480px;margin:2rem auto;padding:0 1rem;background:#0f172a;color:#e2e8f0}
.card{background:#1e293b;border-radius:12px;padding:1rem 1.2rem;margin-bottom:1rem}
.bar{height:28px;background:#334155;border-radius:14px;overflow:hidden;position:relative}
.fill{height:100%;background:#38bdf8;transition:width .3s}
.mark{position:absolute;top:0;bottom:0;width:2px;background:#f8fafc88}
.big{font-size:2.2rem;font-weight:700}
.pump{display:inline-block;padding:.3rem .9rem;border-radius:99px;font-weight:600}
.on{background:#16a34a}.off{background:#475569}
input[type=range]{width:100%;appearance:none;height:8px;border-radius:99px;background:#334155;cursor:pointer;margin:.4rem 0}
input[type=range]::-webkit-slider-thumb{appearance:none;width:22px;height:22px;border-radius:50%;background:#38bdf8;border:3px solid #0f172a}
input[type=range]::-moz-range-thumb{width:18px;height:18px;border-radius:50%;background:#38bdf8;border:3px solid #0f172a}
.row{display:flex;justify-content:space-between;align-items:center;gap:.8rem;flex-wrap:wrap}
button{padding:.55rem 1rem;border:1px solid #475569;border-radius:8px;font:inherit;cursor:pointer;background:#334155;color:#e2e8f0}
button:hover{background:#3f4f66}
#bon{background:#16a34a;border-color:#16a34a}#boff{background:#b91c1c;border-color:#b91c1c}
.btns{display:flex;flex-wrap:wrap;gap:.5rem;margin-top:.9rem}
.sw{display:flex;align-items:center;gap:.8rem;cursor:pointer}
.sw input{appearance:none;width:3rem;height:1.6rem;border-radius:99px;background:#475569;position:relative;cursor:pointer;margin:0;flex:none;transition:background .2s}
.sw input::after{content:"";position:absolute;top:3px;left:3px;width:calc(1.6rem - 6px);height:calc(1.6rem - 6px);border-radius:50%;background:#fff;transition:transform .2s}
.sw input:checked{background:#16a34a}.sw input:checked::after{transform:translateX(1.4rem)}
small{color:#94a3b8;display:block;margin-top:.4rem}
</style>
<h2>💧 Riego automático</h2>
<div class=card><div class=row><label class=sw><input type=checkbox id=real role=switch>
<span>Modo <b id=mlabel></b></span></label><button id=blec></button></div><small id=info></small><small>Apagado = simulado · Encendido = lee el sensor real</small></div>
<div class=card>
 <div class=big><span id=pct>0</span>%</div>
 <div class=bar><div class=fill id=fill></div><div class=mark style="left:35%"></div><div class=mark style="left:55%"></div></div>
 <small>Marcas: enciende &lt;35%, apaga ≥55% · pulsos de 5 s con pausa de 5 s</small>
 <small>El riego automático espera a que pulses «Iniciar» tras conectar el Arduino.</small>
 <div id=sim style="margin-top:1.2rem"><input type=range id=slider min=0 max=100>
  <small>Humedad simulada (la histéresis decide la bomba)</small></div>
</div>
<div class=card>Bomba: <span class="pump off" id=pump>APAGADA</span>
 <div id=man class=btns><button id=bon>Encender</button><button id=boff>Apagar</button><button id=bbuz></button><button id=bini></button>
 </div><small id=mn></small></div>
<script>
const $=id=>document.getElementById(id);let silencio=false,habilitado=false,s0={lectura:true};
const post=b=>fetch('/api',{method:'POST',body:JSON.stringify(b)}).then(refresh);
$('real').onchange=e=>post({modo:e.target.checked?'real':'simulado'});
$('slider').oninput=e=>post({humedad:+e.target.value});
$('bon').onclick=()=>post({bomba:true});$('boff').onclick=()=>post({bomba:false});$('blec').onclick=()=>post({lectura:!s0.lectura});$('bini').onclick=()=>post({habilitado:!habilitado});$('bbuz').onclick=()=>post({silencio:!silencio});
async function refresh(){
 const s=s0=await (await fetch('/api')).json(), r=s.real, real=s.modo=='real';
 const fresh=r.humedad!=null&&Date.now()/1000-r.ts<5, ok=real&&fresh;
 const pct=real?(r.humedad??0):s.humedad, on=(real||fresh)?!!r.bomba:s.bomba;
 $('real').checked=real;$('mlabel').textContent=real?'REAL (sensor)':'SIMULADO';
 $('pct').textContent=real&&!ok?'--':pct;$('fill').style.width=pct+'%';
 $('pump').textContent=on?'ENCENDIDA':'APAGADA';$('pump').className='pump '+(on?'on':'off');
 habilitado=fresh&&!!r.habilitado;$('bini').textContent=habilitado?'⏹ Detener riego automático':'▶ Iniciar riego automático';$('bini').style.background=habilitado?'#b45309':'#0369a1';
 silencio=!!r.silencio;$('bbuz').textContent=silencio?'🔇 Buzzer silenciado':'🔔 Buzzer activo';
 $('sim').style.display=real?'none':'';
 if(document.activeElement!==$('slider'))$('slider').value=s.humedad;
 $('mn').textContent=s.manual?'(forzada a mano hasta que la humedad cruce un umbral)':'';
 $('blec').textContent=s.lectura?'⏸ Detener lectura':'▶ Reanudar lectura';
 $('info').textContent=!s.lectura?'Lectura detenida: puerto serie libre (ya puedes subir el sketch).':real?(ok?`raw=${r.raw} · ${r.puerto}`:'Sin datos del Arduino (¿conectado? ¿Monitor Serie cerrado?)'):'';
}
setInterval(refresh,250);refresh();
</script>"""


class H(BaseHTTPRequestHandler):
    def _send(self, body, ctype="application/json"):
        data = body.encode()
        self.send_response(200)
        self.send_header("Content-Type", ctype + "; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        if self.path == "/api":
            with lock:
                self._send(json.dumps(state))
        else:
            self._send(HTML, "text/html")

    def do_POST(self):
        try:
            body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))))
        except ValueError:
            self.send_error(400); return
        with lock:
            if body.get("modo") in ("simulado", "real"):
                state["modo"] = body["modo"]
                enviar(f"H{state['humedad']}\nA\n" if body["modo"] == "simulado" else "R\nA\n")
            if isinstance(body.get("humedad"), int):
                state["humedad"] = max(0, min(100, body["humedad"]))
                state["manual"] = False
                histeresis()
                if state["modo"] == "simulado":
                    enviar(f"H{state['humedad']}\nA\n")
            if isinstance(body.get("bomba"), bool):
                state["bomba"], state["manual"] = body["bomba"], True
                enviar("1\n" if body["bomba"] else "0\n")
            if isinstance(body.get("silencio"), bool):
                enviar("S\n" if body["silencio"] else "V\n")
            if isinstance(body.get("habilitado"), bool):
                enviar("E\n" if body["habilitado"] else "D\n")
            if isinstance(body.get("lectura"), bool):
                state["lectura"] = body["lectura"]
        self._send("{}")

    def log_message(self, *a):
        pass


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8000
    threading.Thread(target=lector_serie, args=(sys.argv[2] if len(sys.argv) > 2 else None,), daemon=True).start()
    print(f"http://localhost:{port}")
    ThreadingHTTPServer(("127.0.0.1", port), H).serve_forever()
