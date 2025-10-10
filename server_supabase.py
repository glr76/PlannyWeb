import os
from flask import Flask, request, jsonify, send_from_directory, Response, abort
from supabase import create_client, Client
from flask_cors import CORS

# --- Percorsi ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PUBLIC_DIR = os.path.join(BASE_DIR, "public")

# --- Env ---
SUPABASE_URL = os.environ["SUPABASE_URL"].rstrip("/")
SUPABASE_KEY = os.environ["SUPABASE_ANON_KEY"]
BUCKET       = os.environ.get("SUPABASE_BUCKET", "planny-txt")

# --- Client unico ---
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# --- App ---
app = Flask(__name__, static_folder=PUBLIC_DIR, static_url_path="/static")
CORS(app, resources={r"/api/*": {"origins": "*"}})  # consenti fetch anche da origini diverse

# ---------- STATIC ----------
@app.get("/")
def index():
    index_path = os.path.join(PUBLIC_DIR, "index.html")
    if not os.path.exists(index_path):
        return "index.html non trovato in /public", 404
    return send_from_directory(PUBLIC_DIR, "index.html")

# ---------- HELPERS ----------
def _safe_name(name: str) -> str:
    # evita traversal e whitespace; CONSERVA eventuali sottocartelle semplici se servono
    name = name.strip().replace("\\", "/")
    parts = [p for p in name.split("/") if p not in ("", ".", "..")]
    return "/".join(parts)

def _upload_bytes(path: str, data: bytes) -> str:
    supabase.storage.from_(BUCKET).upload(
        path,
        data,
        {
            "contentType": "text/plain; charset=utf-8",
            "upsert": True,  # 1 sola chiamata, sovrascrive se esiste
        },
    )
    return "upsert"

def _download_bytes(path: str) -> bytes:
    return supabase.storage.from_(BUCKET).download(path)

def _download_text(path: str) -> str:
    return _download_bytes(path).decode("utf-8", "replace")

# ---------- API TESTO **ROBUSTE** (JSON) ----------
@app.get("/api/files/text/<path:name>")
def api_text_get(name: str):
    fname = _safe_name(name)
    try:
        text = _download_text(fname)
        return jsonify(ok=True, name=fname, text=text)
    except Exception as e:
        return jsonify(ok=False, name=fname, error=str(e)), 404

@app.put("/api/files/text/<path:name>")
def api_text_put(name: str):
    fname = _safe_name(name)

    # accetta sia text/plain che application/json
    raw = request.get_data(cache=False, as_text=False) or b""
    if request.mimetype and "application/json" in request.mimetype:
        try:
            payload = request.get_json(silent=True) or {}
            text = (payload.get("text") or "").encode("utf-8")
        except Exception:
            abort(400, "invalid json")
    else:
        # text/plain (o altro) -> prendi i bytes così come arrivano
        text = raw

    if b"\x00" in text:
        abort(400, "binary data not allowed")

    mode = _upload_bytes(fname, text)
    return jsonify(ok=True, name=fname, mode=mode, size=len(text))

# ---------- API COMPATIBILITÀ (testo puro) ----------
# (Puoi continuare a usarle, ma i browser se aperti in tab potrebbero scaricare)
@app.get("/api/files/<path:name>")
def api_read_file(name: str):
    fname = _safe_name(name)
    try:
        text = _download_text(fname)
        headers = {
            "Cache-Control": "no-store, max-age=0",
            "X-Bucket": BUCKET, "X-Path": fname,
            "X-Content-Type-Options": "nosniff",
            "Content-Disposition": f'inline; filename="{os.path.basename(fname)}"',
        }
        return Response(text, mimetype="text/plain; charset=utf-8", headers=headers)
    except Exception:
        headers = {
            "Cache-Control": "no-store, max-age=0",
            "X-Bucket": BUCKET, "X-Path": fname,
            "X-Content-Type-Options": "nosniff",
            "Content-Disposition": f'inline; filename="{os.path.basename(fname)}"',
        }
        return Response("", status=404, mimetype="text/plain; charset=utf-8", headers=headers)

@app.put("/api/files/<path:name>")
def api_write_file(name: str):
    fname = _safe_name(name)
    data = request.get_data(cache=False, as_text=False) or b""
    if b"\x00" in data:
        abort(400, "binary data not allowed")
    mode = _upload_bytes(fname, data)
    return jsonify(ok=True, bucket=BUCKET, path=fname, mode=mode, size=len(data))

# ---------- Utility ----------
@app.get("/api/files/list")
def api_list_files():
    try:
        items = supabase.storage.from_(BUCKET).list("", {"limit": 1000})
        files = [{"name": it.get("name"), "updated_at": it.get("updated_at")} for it in items]
        return jsonify(ok=True, bucket=BUCKET, count=len(files), files=files)
    except Exception as e:
        return jsonify(ok=False, error=str(e)), 500

@app.get("/healthz")
def healthz():
    return "ok"

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8000)))
