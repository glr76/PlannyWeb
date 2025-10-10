import os
from flask import Flask, request, jsonify, send_from_directory, abort, Response
from supabase import create_client, Client

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PUBLIC_DIR = os.path.join(BASE_DIR, "public")

# Environment variables required
SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_KEY = os.environ["SUPABASE_ANON_KEY"]
BUCKET = os.environ.get("SUPABASE_BUCKET", "planny-txt")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
app = Flask(__name__, static_folder=PUBLIC_DIR, static_url_path='')

# ---------- STATIC ----------
@app.get("/")
def index():
    index_path = os.path.join(PUBLIC_DIR, "index.html")
    if not os.path.exists(index_path):
        return "index.html non trovato in /public", 404
    return send_from_directory(PUBLIC_DIR, "index.html")

@app.get("/<path:asset>")
def static_files(asset):
    path = os.path.join(PUBLIC_DIR, asset)
    if not os.path.exists(path):
        abort(404)
    directory, fname = os.path.split(path)
    return send_from_directory(directory, fname)

# ---------- FILE API via Supabase Storage ----------
def _download_text(path: str) -> str:
    try:
        res = supabase.storage.from_(BUCKET).download(path)
        return res.decode("utf-8")
    except Exception:
        return ""

def _upload_text(path: str, content: str) -> None:
    data = content.encode("utf-8")
    try:
        # Try update first, fallback to upload
        supabase.storage.from_(BUCKET).update(path, data)
    except Exception:
        supabase.storage.from_(BUCKET).upload(path, data, {"contentType": "text/plain; charset=utf-8"})

@app.get("/api/files/<path:name>")
def api_read_file(name):
    # keep same contract: return text/plain
    data = _download_text(name)
    status = 200 if data != "" else 404
    resp = Response(data, mimetype="text/plain; charset=utf-8", status=status)
    resp.headers["Cache-Control"] = "no-store, max-age=0"
    return resp

@app.put("/api/files/<path:name>")
def api_write_file(name):
    raw = request.get_data() or b""
    _upload_text(name, raw.decode("utf-8", errors="replace"))
    return jsonify(ok=True, path=name)

@app.get("/healthz")
def healthz():
    return "ok"

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8000)))
