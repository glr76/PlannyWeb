import os
from flask import Flask, request, jsonify, send_from_directory, Response, abort
from supabase import create_client, Client
from werkzeug.utils import secure_filename

# --- Percorsi ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PUBLIC_DIR = os.path.join(BASE_DIR, "public")

# --- Env vars richieste (Render -> Settings -> Environment) ---
SUPABASE_URL = os.environ["SUPABASE_URL"].strip().rstrip("/")
SUPABASE_KEY = os.environ["SUPABASE_ANON_KEY"]
BUCKET       = os.environ.get("SUPABASE_BUCKET", "planny-txt")

# --- Client Supabase ---
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# Statici esposti sotto /static
app = Flask(__name__, static_folder=PUBLIC_DIR, static_url_path="/static")

# ---------- STATIC ----------
@app.get("/")
def index():
    index_path = os.path.join(PUBLIC_DIR, "index.html")
    if not os.path.exists(index_path):
        return "index.html non trovato in /public", 404
    return send_from_directory(PUBLIC_DIR, "index.html")

# ---------- HELPERS FILE ----------
def _safe_name(name: str) -> str:
    return secure_filename(os.path.basename(name))

def _download_text(path: str) -> str:
    try:
        data = supabase.storage.from_(BUCKET).download(path)
        return data.decode("utf-8", errors="replace")
    except Exception:
        return ""

def _upload_text(path: str, content: str):
    data = content.encode("utf-8")
    try:
        supabase.storage.from_(BUCKET).update(path, data)
        return "update"
    except Exception:
        supabase.storage.from_(BUCKET).upload(
            path, data, {"contentType": "text/plain; charset=utf-8"}
        )
        return "upload"

# ---------- API ----------
@app.get("/api/files/<path:name>")
def api_read_file(name):
    fname = _safe_name(name)
    txt = _download_text(fname)
    status = 200 if txt != "" else 404
    resp = Response(txt, status=status, mimetype="text/plain; charset=utf-8")
    resp.headers["Cache-Control"] = "no-store, max-age=0"
    resp.headers["X-Bucket"] = BUCKET
    resp.headers["X-Path"] = fname
    return resp

@app.put("/api/files/<path:name>")
def api_write_file(name):
    fname = _safe_name(name)
    raw = request.get_data() or b""
    body = raw.decode("utf-8", errors="replace")
    mode = _upload_text(fname, body)
    return jsonify(ok=True, bucket=BUCKET, path=fname, mode=mode, size=len(body))

@app.get("/healthz")
def healthz():
    return "ok"

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8000)))
