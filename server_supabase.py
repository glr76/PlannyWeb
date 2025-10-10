import os
from flask import Flask, request, jsonify, send_from_directory, Response, abort
from supabase import create_client, Client

# --- Percorsi ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PUBLIC_DIR = os.path.join(BASE_DIR, "public")

# --- Env vars (Render -> Settings -> Environment) ---
# SUPABASE_URL       = https://<project>.supabase.co   (senza / finale)
# SUPABASE_ANON_KEY  = <chiave>  (può essere anon o service_role se scrivi)
# SUPABASE_BUCKET    = planny-txt (o il tuo bucket)
SUPABASE_URL = os.environ["SUPABASE_URL"].rstrip("/")
SUPABASE_KEY = os.environ["SUPABASE_ANON_KEY"]
BUCKET       = os.environ.get("SUPABASE_BUCKET", "planny-txt")

# --- Client unico (riuso connessioni) ---
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# Statici serviti da / (index.html) e /static/* se vuoi
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
    # impedisci path traversal; tieni solo l'ultimo segmento
    return os.path.basename(name.strip())

def _upload_bytes(path: str, data: bytes) -> str:
    # una sola chiamata: upsert True => sovrascrive se già esiste
    supabase.storage.from_(BUCKET).upload(
        path,
        data,
        {
            "contentType": "text/plain; charset=utf-8",
            "upsert": True,
        },
    )
    return "upsert"

def _download_bytes(path: str) -> bytes:
    return supabase.storage.from_(BUCKET).download(path)


# ---------- API ----------
@app.get("/api/files/<path:name>")
def api_read_file(name: str):
    fname = _safe_name(name)
    try:
        data = _download_bytes(fname)  # bytes
        # rispondi come testo; i client leggono correttamente UTF-8
        return Response(data, mimetype="text/plain; charset=utf-8", headers={
            "Cache-Control": "no-store, max-age=0",
            "X-Bucket": BUCKET,
            "X-Path": fname,
        })
    except Exception:
        return Response("", status=404, mimetype="text/plain; charset=utf-8", headers={
            "Cache-Control": "no-store, max-age=0",
            "X-Bucket": BUCKET,
            "X-Path": fname,
        })

@app.put("/api/files/<path:name>")
def api_write_file(name: str):
    fname = _safe_name(name)
    data = request.get_data(cache=False, as_text=False) or b""
    if b"\x00" in data:
        abort(400, "binary data not allowed")
    mode = _upload_bytes(fname, data)
    # risposta minimale e veloce
    return jsonify(ok=True, bucket=BUCKET, path=fname, mode=mode, size=len(data))

# (opzionale) elenco file nel bucket, utile per debug
@app.get("/api/files/list")
def api_list_files():
    try:
        items = supabase.storage.from_(BUCKET).list("", {"limit": 500})
        files = [{
            "name": it.get("name"),
            "updated_at": it.get("updated_at"),
            "id": it.get("id"),
        } for it in items]
        return jsonify(ok=True, bucket=BUCKET, count=len(files), files=files)
    except Exception as e:
        return jsonify(ok=False, error=str(e)), 500

@app.get("/healthz")
def healthz():
    return "ok"


if __name__ == "__main__":
    # per esecuzione locale
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8000)))
