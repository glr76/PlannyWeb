import os
from flask import Flask, request, jsonify, send_from_directory, Response, abort
from supabase import create_client, Client

# --- Percorsi ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PUBLIC_DIR = os.path.join(BASE_DIR, "public")

# --- Env ---
SUPABASE_URL = os.environ["SUPABASE_URL"].rstrip("/")
SUPABASE_KEY = os.environ["SUPABASE_ANON_KEY"]
BUCKET       = os.environ.get("SUPABASE_BUCKET", "planny-txt")

# --- Client unico ---
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# Statici da / (index.html) e /static/*
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
    # rimuove path traversal e whitespace
    return os.path.basename(name.strip())

def _upload_bytes(path: str, data: bytes) -> str:
    # una sola chiamata: upsert True -> sovrascrive se esiste
    supabase.storage.from_(BUCKET).upload(
        path,
        data,
        {
            "contentType": "text/plain; charset=utf-8",
            "upsert": True,
        },
    )
    return "upsert"

def _download_str(path: str) -> str:
    # scarica bytes e DECODE -> stringa utf-8 (così il browser non tratta come binario)
    b = supabase.storage.from_(BUCKET).download(path)
    return b.decode("utf-8", "replace")


# ---------- API ----------
@app.get("/api/files/<path:name>")
def api_read_file(name: str):
    fname = _safe_name(name)
    try:
        text = _download_str(fname)  # <- STRINGA
        print(f"[GET] {fname} -> {len(text)} chars")
        headers = {
            "Cache-Control": "no-store, max-age=0",
            "X-Bucket": BUCKET,
            "X-Path": fname,
            # Evita sniffing che potrebbe cambiare il comportamento
            "X-Content-Type-Options": "nosniff",
        }
        # Risposta testuale: il browser non scarica, fetch() funziona
        return Response(text, mimetype="text/plain; charset=utf-8", headers=headers)
    except Exception as e:
        print(f"[GET] {fname} -> 404 ({e})")
        headers = {
            "Cache-Control": "no-store, max-age=0",
            "X-Bucket": BUCKET,
            "X-Path": fname,
            "X-Content-Type-Options": "nosniff",
        }
        return Response("", status=404, mimetype="text/plain; charset=utf-8", headers=headers)

@app.put("/api/files/<path:name>")
def api_write_file(name: str):
    fname = _safe_name(name)
    data = request.get_data(cache=False, as_text=False) or b""
    if b"\x00" in data:
        abort(400, "binary data not allowed")
    mode = _upload_bytes(fname, data)
    print(f"[PUT] {fname} <- {len(data)} bytes ({mode})")
    return jsonify(ok=True, bucket=BUCKET, path=fname, mode=mode, size=len(data))

# utile per controllare cosa c'è dentro al bucket
@app.get("/api/files/list")
def api_list_files():
    try:
        items = supabase.storage.from_(BUCKET).list("", {"limit": 500})
        files = [{"name": it.get("name"), "updated_at": it.get("updated_at")} for it in items]
        print(f"[LIST] {len(files)} files")
        return jsonify(ok=True, bucket=BUCKET, count=len(files), files=files)
    except Exception as e:
        print(f"[LIST] ERR {e}")
        return jsonify(ok=False, error=str(e)), 500

@app.get("/healthz")
def healthz():
    return "ok"


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8000)))
