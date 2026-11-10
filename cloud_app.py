"""Protected MASTER CAD AI web application: fixed parametric operations only."""
import os, json, uuid, secrets, threading, tempfile, io
from datetime import timedelta
from pathlib import Path
from flask import Flask, jsonify, request, redirect, session, render_template_string, Response, send_file, abort
from mastercad.geometry import build, mesh_data
from mastercad.interpret import interpret
from mastercad.image_quotes import inspect_image
from mastercad.backends import capability, infer_with_gpu
from mastercad.history import operations
from mastercad.postgres_store import init_db, save_model, project_list, get_project, get_export, dsn
from mastercad.disegno import bp as disegno_bp
from mastercad.reverse import bp as reverse_bp
from mastercad.progetto import bp as progetto_bp
from mastercad.home import bp as home_bp
from mastercad.tavola import bp as tavola_bp
from mastercad.ciclo import bp as ciclo_bp
from mastercad.preventivo import bp as preventivo_bp
from mastercad.fattibilita import bp as fattibilita_bp
from mastercad.libreria import bp as libreria_bp
from mastercad.ar import bp as ar_bp, init_db as ar_init_db
from mastercad.qualita import bp as qualita_bp, init_db as qualita_init_db
from mastercad.corso import bp as corso_bp, init_db as corso_init_db
from mastercad.officina import bp as officina_bp, init_db as officina_init_db
from mastercad.versioni import bp as versioni_bp, init_db as versioni_init_db
from mastercad.tolleranze import bp as tolleranze_bp
from mastercad.generativo import bp as generativo_bp
from mastercad.assiemi import bp as assiemi_bp, init_db as assiemi_init_db

app=Flask(__name__)
app.config.update(SECRET_KEY=os.getenv("FLASK_SECRET_KEY") or secrets.token_urlsafe(48),
                  SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE="Lax",
                  SESSION_COOKIE_SECURE=os.getenv("COOKIE_SECURE","1")!="0",
                  MAX_CONTENT_LENGTH=16_000_000,
                  PERMANENT_SESSION_LIFETIME=timedelta(hours=8))
OUTPUT=Path(os.getenv("MASTER_CAD_OUTPUT","/tmp/mastercad-projects"))
app.register_blueprint(disegno_bp)
app.register_blueprint(reverse_bp)
app.register_blueprint(progetto_bp)
for _bp in (home_bp, tavola_bp, ciclo_bp, preventivo_bp, fattibilita_bp, libreria_bp, ar_bp, qualita_bp, corso_bp,
            officina_bp, versioni_bp, tolleranze_bp, generativo_bp, assiemi_bp):
    app.register_blueprint(_bp)
# pagine aperte senza login: accesso, salute, vista AR condivisa con il QR, ingresso allievi
PUBBLICHE=("/health","/login","/corso/entra")
PUBBLICHE_PREFISSI=("/ar/v/","/ar/static/","/home/static/","/corso/static/")
# l'allievo usa il CAD e gli strumenti, ma non il pannello docente né l'elenco di tutti i progetti
VIETATE_ALLIEVO=("/corso/docente","/api/corso/docente","/api/projects")
_LOCK=threading.Lock()
LOGIN="""<!doctype html><html lang="it"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>MASTER CAD AI · Accesso</title>
<style>body{background:#0b1424;color:#e5f2ff;display:grid;place-items:center;min-height:100vh;font:16px system-ui}main{background:#15253b;border:1px solid #36546d;border-radius:16px;padding:30px;width:min(400px,85vw)}input,button{width:100%;box-sizing:border-box;padding:14px;margin-top:12px;border-radius:8px;font:inherit}input{background:#101a2b;color:white;border:1px solid #658099}button{background:#208aad;color:white;border:0;cursor:pointer}.err{color:#ffb0b0}</style></head><body><main><h1>MASTER CAD AI</h1><p>CAD 3D da voce e descrizioni in italiano</p>
{% if error %}<p class="err">{{error}}</p>{% endif %}<form method="post" action="/login"><label>Password del servizio<input type="password" name="password" required autocomplete="current-password"></label><button>Accedi</button></form><p style="font-size:13px"><a style="color:#9fd8f0" href="/corso/entra">Sei un allievo? Entra con il codice del corso →</a></p><p style="font-size:12px">Configura MASTER_CAD_PASSWORD nelle Variables di Railway.</p></main></body></html>"""

@app.before_request
def auth():
    if request.path in PUBBLICHE or request.path.startswith(PUBBLICHE_PREFISSI): return
    allievo=session.get("allievo")
    if allievo and not session.get("ok"):
        if request.path.startswith(VIETATE_ALLIEVO):
            if request.path.startswith("/api/"): return jsonify(error="Riservato al docente"),403
            return redirect("/")
    elif not os.getenv("MASTER_CAD_PASSWORD") or not session.get("ok"):
        if request.path.startswith("/api/"): return jsonify(error="Accesso richiesto"),401
        return redirect("/login")
    if request.method not in ("GET","HEAD","OPTIONS"):
        expected=session.get("csrf","")
        supplied=request.headers.get("X-CSRF-Token","")
        if not expected or not secrets.compare_digest(supplied,expected):
            return jsonify(error="Token di sicurezza non valido"),403

@app.after_request
def headers(response):
    response.headers["Cache-Control"]="no-store"
    response.headers["X-Content-Type-Options"]="nosniff"
    response.headers["X-Frame-Options"]="DENY"
    response.headers["Content-Security-Policy"]="default-src 'self'; img-src 'self' data: blob:; style-src 'self' 'unsafe-inline'; script-src 'self' 'unsafe-inline' 'wasm-unsafe-eval'; connect-src 'self' blob: data:; worker-src 'self' blob:; media-src 'self' blob:"
    return response

@app.get("/health")
def health():
    return jsonify(ok=True,service="master-cad-ai",database="postgresql")

@app.route("/login",methods=["GET","POST"])
def login():
    if request.method=="GET":
        return render_template_string(LOGIN,error="Sessione scaduta: accedi nuovamente" if request.args.get("expired")=="1" else None)
    password=os.getenv("MASTER_CAD_PASSWORD","")
    if password and secrets.compare_digest(request.form.get("password",""),password):
        session.clear()
        session["ok"]=True
        session.permanent=True
        session["csrf"]=secrets.token_urlsafe(32)
        return redirect("/")
    return render_template_string(LOGIN,error="Password errata o non configurata"),401

@app.post("/logout")
def logout():
    allievo=bool(session.get("allievo"))
    session.clear()
    return jsonify(ok=True,redirect="/corso/entra" if allievo else "/login")

@app.get("/parla")
def index():
    html=(Path(__file__).parent/"web"/"index.html").read_text(encoding="utf-8")
    return Response(html.replace("/*__CSRF__*/",json.dumps(session["csrf"])),mimetype="text/html")

@app.get("/api/status")
def status():
    return jsonify(ok=True,mode="online",voice="browser",cad="CadQuery",database="postgresql",ai="interprete a regole",backends=capability(),
                   message="SpeechRecognition supportato solo in alcuni browser; la trascrizione può essere remota.")

@app.post("/api/interpret")
def interpret_api():
    data=request.get_json(silent=True)
    if not isinstance(data,dict): return jsonify(error="JSON non valido"),400
    try:
        prev=data.get("previous")
        if prev is not None and not isinstance(prev,dict): raise ValueError("Modello precedente non valido")
        spec=interpret(str(data.get("text",""))[:1500],prev)
        return jsonify(spec=spec,message="Quote comprese: controlla e costruisci il pezzo")
    except (ValueError,TypeError,KeyError) as exc:
        return jsonify(error=str(exc)[:400]),400

@app.post("/api/image/inspect")
def image_inspection():
    """Read printed dimensions, but never guess an unmeasured physical size."""
    file=request.files.get("image")
    if file is None:
        return jsonify(error="Seleziona una foto o un disegno quotato"),400
    try:
        result=inspect_image(file.read(4_000_001))
        return jsonify(result)
    except ValueError as e:
        return jsonify(error=str(e)),400
    except RuntimeError as e:
        return jsonify(error=str(e)),503

@app.post("/api/image/infer-gpu")
def gpu_image_inference():
    """Opt-in GPU inference. Keep OCR operational when a worker is missing."""
    if not capability()["gpu"]["configured"]:
        return jsonify(error="GPU NVIDIA non collegata: puoi continuare con OCR e CAD online.", fallback="/api/image/inspect"),503
    f=request.files.get("image")
    if f is None:
        return jsonify(error="Seleziona un'immagine per la ricostruzione"),400
    try:
        data=infer_with_gpu(f.read(4_000_001),
                            category=request.form.get("category","mechanical_part"))
        return jsonify(data)
    except ValueError as exc:
        return jsonify(error=str(exc)),400
    except RuntimeError as exc:
        return jsonify(error=str(exc),fallback="/api/image/inspect"),503

@app.post("/api/build")
def build_api():
    data=request.get_json(silent=True)
    if not isinstance(data,dict):return jsonify(error="JSON non valido"),400
    try:
        with _LOCK:
            obj,solid,spec=build(data.get("spec"))
            mesh=mesh_data(solid)
            token=uuid.uuid4().hex
            import cadquery as cq
            with tempfile.TemporaryDirectory(prefix="cad-render-") as tmp:
                step_path=Path(tmp)/"model.step"
                stl_path=Path(tmp)/"model.stl"
                cq.exporters.export(obj,str(step_path))
                cq.exporters.export(obj,str(stl_path),tolerance=.05,angularTolerance=.15)
                save_model(token,data.get("name") or "Modello CAD",spec,operations(spec),
                           step_path.read_bytes(),stl_path.read_bytes())
        return jsonify(id=token,spec=spec,mesh=mesh,history=operations(spec),
                       exports={"step":"/api/export/"+token+"?format=step",
                                "stl":"/api/export/"+token+"?format=stl"},
                       warning="Verificare quote, materiali, tolleranze, carichi e sicurezza prima di produrre.")
    except (ValueError,TypeError,KeyError) as exc:
        return jsonify(error=str(exc)[:400]),400
    except Exception:
        app.logger.exception("Errore costruzione CAD")
        return jsonify(error="Errore CAD: consulta i log Railway"),500

@app.get("/api/export/<token>")
def export(token):
    if len(token)!=32 or any(c not in "0123456789abcdef" for c in token):abort(400)
    fmt=request.args.get("format","step")
    if fmt not in ("step","stl"):abort(400)
    data=get_export(token,fmt)
    if data is None:abort(404)
    return send_file(io.BytesIO(data),as_attachment=True,
                     download_name="MASTER_CAD_"+token[:8]+"."+fmt,
                     mimetype="application/step" if fmt=="step" else "model/stl")

@app.get("/api/projects")
def list_projects():
    return jsonify(project_list())


@app.get("/api/projects/<token>")
def read_project(token):
    try:
        project=get_project(token)
    except ValueError:
        abort(400)
    if project is None:
        abort(404)
    return jsonify(project)


@app.errorhandler(413)
def too_big(_):
    return jsonify(error="File troppo grande"),413

# Required PostgreSQL: ensure tables exist before serving CAD requests.
init_db()
ar_init_db()
qualita_init_db()
corso_init_db()
officina_init_db()
versioni_init_db()
assiemi_init_db()
