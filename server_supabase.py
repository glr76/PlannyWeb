import os
from flask import Flask, request, jsonify, send_from_directory, Response
from supabase import create_client, Client
from werkzeug.utils import secure_filename

# --- Percorsi ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PUBLIC_DIR = os.path.join(BASE_DIR, "public")  # qui stanno index.html, js, css, immagini

# --- Env vars richieste (Render → Settings → Environment) ---
#   SUPABASE_URL        = https://<tuo-progetto>.supabase.co  (senza / finale)
#   SUPABASE_ANON_KEY   = <service_role key>                  (NON usare anon read-only)
#   SUPABASE_BUCKET     = planny-txt                          (o il tuo nome bucket)
SUPABASE_URL = os.environ["SUPABASE_URL"].strip().rstrip("/")
SUPABASE_KEY = os.environ["SUPABASE_ANON_KEY"]
BUCKET       = os.environ.get("SUPABASE_BUCKET", "planny-txt")

# --- Client Supabase ---
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# Statici serviti da /static per evitare conflitti con /api/*
app = Flask(__name__, static_folder=PUBLIC_DIR, static_url_path="/static")


# ---------- STATIC ----------
@app.get("/")
def index():
    index_path = os.path.join(PUBLIC_DIR, "index.html")
    if not os.path.exists(index_path):
        return "index.html non trovato in /public", 404
    return send_from_directory(PUBLIC_DIR, "index.html")


# ---------- HELPERS ----------
def _safe_name(name: str) -> str:
    # rimuovi spazi/a-capo e path strani; es.: "selections_2026.txt"
    return secure_filename(os.path.basename(name.strip()))

def _download_text(path: str) -> str:
    try:
        data = supabase.storage.from_(BUCKET).download(path)
        return data.decode("utf-8", errors="replace")
    except Exception:
        return ""  # se non esiste, restituiamo vuoto

def _upload_text(path: str, content: str) -> str:
    data = content.encode("utf-8")
    try:
        # prova a sovrascrivere
        supabase.storage.from_(BUCKET).update(path, data)
        return "update"
    except Exception:
        # se non esiste, crea
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

# (opzionale ma utile per debug)
@app.get("/api/files/list")
def api_list_files():
    try:
        items = supabase.storage.from_(BUCKET).list("", {"limit": 200})
        files = [{"name": it.get("name"), "updated_at": it.get("updated_at")} for it in items]
        return jsonify(ok=True, bucket=BUCKET, files=files)
    except Exception as e:
        return jsonify(ok=False, error=str(e)), 500

@app.get("/healthz")
def healthz():
    return "ok"


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8000)))
