# server_supabase.py
import os
import io
import logging
import traceback
import time
from hashlib import sha256

from flask import Flask, request, send_from_directory, Response, jsonify, abort, make_response
from flask_cors import CORS
from supabase import create_client, Client

# ----------------------------------------------------
# Config
# ----------------------------------------------------
BASE_DIR   = os.path.dirname(os.path.abspath(__file__))
PUBLIC_DIR = os.path.join(BASE_DIR, "public")

SUPABASE_URL = os.environ["SUPABASE_URL"].rstrip("/")
# Preferisci la Service Role (due nomi possibili), altrimenti fallback a ANON
SUPABASE_KEY = (
    os.environ.get("SUPABASE_SERVICE_ROLE")
    or os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    or os.environ["SUPABASE_ANON_KEY"]
)
BUCKET = os.environ.get("SUPABASE_BUCKET", "planny-txt")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

app = Flask(__name__, static_folder=PUBLIC_DIR, static_url_path="/static")
CORS(app, resources={r"/api/*": {"origins": "*"}})

logging.basicConfig(level=logging.INFO)
log = app.logger


# ----------------------------------------------------
# Helpers Storage
# ----------------------------------------------------
def _sanitize(name: str) -> str:
    """Evita percorsi strani e normalizza gli slash."""
    name = (name or "").strip().replace("\\", "/")
    while "//" in name:
        name = name.replace("//", "/")
    if name.startswith("/"):
        name = name[1:]
    if ".." in name:
        raise ValueError("Invalid path")
    return name


def _download_text(path: str) -> str:
    try:
        data = supabase.storage.from_(BUCKET).download(path)
        return data.decode("utf-8", "replace")
    except Exception as e:
        log.warning(f"[download] fail '{path}': {e}")
        return ""


def _upload_text(path: str, content: str):
    """
    Scrive il file assicurando metadata anti-cache nel bucket.
    Tenta update; se fallisce, fa upload (creazione).
    """
    data_bytes = content.encode("utf-8")
    file_opts = {
        "contentType": "text/plain; charset=utf-8",
        # molte versioni di supabase-py accettano 'upsert' e 'cacheControl' qui
        "upsert": True,
        "cacheControl": "0",
    }

    # 1) Tenta UPDATE (se esiste già)
    supabase.storage.from_(BUCKET).upload(path, data_bytes, file_opts) 


def _nocache_headers(extra: dict | None = None) -> dict:
    h = {
        "Cache-Control": "no-store, no-cache, max-age=0, must-revalidate",
        "Pragma": "no-cache",
        "Expires": "0",
        "X-Content-Type-Options": "nosniff",
    }
    if extra:
        h.update(extra)
    return h


# ----------------------------------------------------
# API FILES - JSON (raccomandato)
# ----------------------------------------------------
@app.get("/api/files/text/<path:name>")
def api_text_get(name: str):
    try:
        fname = _sanitize(name)
        txt = _download_text(fname)
        status = 200 if txt != "" else 404
        etag = sha256((txt or "").encode("utf-8")).hexdigest()
        headers = _nocache_headers({"ETag": f'W/"{etag}"'})
        resp = make_response(jsonify(ok=(status == 200), name=fname, text=txt), status)
        for k, v in headers.items():
            resp.headers[k] = v
        return resp
    except Exception as e:
        log.error(f"[GET json] '{name}': {e}\n{traceback.format_exc()}")
        return jsonify(ok=False, error=str(e)), 500


@app.put("/api/files/text/<path:name>")
def api_text_put(name: str):
    try:
        fname = _sanitize(name)
        raw = request.get_data(as_text=True) or ""

        _upload_text(fname, raw)

        sha_in = sha256(raw.encode("utf-8")).hexdigest()
        echoed = _download_text(fname)
        sha_echo = sha256((echoed or "").encode("utf-8")).hexdigest()

        attempts = 0
        while sha_echo != sha_in and attempts < 5:
            time.sleep(0.16)  # 160 ms
            echoed = _download_text(fname)
            sha_echo = sha256((echoed or "").encode("utf-8")).hexdigest()
            attempts += 1

        payload = {
            "ok": True,
            "name": fname,
            "size": len(raw),
            "echo": echoed,
            "sha_in": sha_in,
            "sha_echo": sha_echo,
            "matched": sha_echo == sha_in,
        }
        # 4) headers no-cache anche sulla risposta PUT
        headers = _nocache_headers({"ETag": f'W/"{payload["sha_echo"]}"'})
        resp = make_response(jsonify(payload), 200)
        for k, v in headers.items():
            resp.headers[k] = v
        return resp

    except Exception as e:
        log.error(f"[PUT json] '{name}': {e}\n{traceback.format_exc()}")
        return jsonify(ok=False, error=str(e)), 500


# ----------------------------------------------------
# API FILES - Legacy (testo puro)
# ----------------------------------------------------
@app.get("/api/files/<path:name>")
def api_read_text_legacy(name: str):
    try:
        fname = _sanitize(name)
        txt = _download_text(fname)
        if txt == "":
            # anche 404 deve avere no-cache
            return Response(
                "",
                status=404,
                mimetype="text/plain; charset=utf-8",
                headers=_nocache_headers(),
            )
        etag = sha256(txt.encode("utf-8")).hexdigest()
        headers = _nocache_headers({
            "ETag": f'W/"{etag}"',
            "Content-Disposition": f'inline; filename="{os.path.basename(fname)}"',
        })
        return Response(txt, mimetype="text/plain; charset=utf-8", headers=headers)
    except Exception as e:
        log.error(f"[GET legacy] '{name}': {e}\n{traceback.format_exc()}")
        return Response("error", status=500, mimetype="text/plain; charset=utf-8", headers=_nocache_headers())


@app.put("/api/files/<path:name>")
@app.put("/api/files/<path:name>")
def api_write_text_legacy(name: str):
    try:
        fname = _sanitize(name)
        raw = request.get_data(as_text=True) or ""
        _upload_text(fname, raw)

        sha_in = sha256(raw.encode("utf-8")).hexdigest()
        echoed = _download_text(fname)
        sha_echo = sha256((echoed or "").encode("utf-8")).hexdigest()

        attempts = 0
        while sha_echo != sha_in and attempts < 5:
            time.sleep(0.16)
            echoed = _download_text(fname)
            sha_echo = sha256((echoed or "").encode("utf-8")).hexdigest()
            attempts += 1

        payload = {
            "ok": True,
            "path": fname,
            "size": len(raw),
            "sha_in": sha_in,
            "sha_echo": sha_echo,
            "matched": sha_echo == sha_in,
        }

        # no-cache anche qui
        resp = make_response(jsonify(payload), 200)
        for k, v in _nocache_headers({"ETag": f'W/"{payload["sha_echo"]}"'}).items():
            resp.headers[k] = v
        return resp

    except Exception as e:
        log.error(f"[PUT legacy] '{name}': {e}\n{traceback.format_exc()}")
        return jsonify(ok=False, error=str(e)), 500


# ----------------------------------------------------
# LIST + HEALTH + STUB EXPORT
# ----------------------------------------------------
@app.get("/api/files/list")
def api_list_files():
    try:
        items = supabase.storage.from_(BUCKET).list("", {"limit": 1000})
        files = [{"name": it.get("name"), "updated_at": it.get("updated_at")} for it in items]
        return jsonify(ok=True, bucket=BUCKET, count=len(files), files=files)
    except Exception as e:
        log.error(f"[LIST] {e}\n{traceback.format_exc()}")
        return jsonify(ok=False, error=str(e)), 500


@app.post("/api/export/xlsx/save")
def api_export_xlsx_save():
    # Stub per evitare 404 finché l'export non serve
    return jsonify(ok=True, skipped=True, reason="xlsx export disabled")


@app.get("/healthz")
def healthz():
    return "ok"


# ----------------------------------------------------
# STATIC (/public) – dichiarato DOPO le API per non interferire
# ----------------------------------------------------
@app.get("/")
def index():
    ix = os.path.join(PUBLIC_DIR, "index.html")
    if not os.path.exists(ix):
        return "index.html non trovato in /public", 404
    return send_from_directory(PUBLIC_DIR, "index.html", cache_timeout=0)


@app.get("/<path:asset>")
def static_files(asset):
    # NON si occupa di /api/... (quelle route hanno la precedenza)
    path = os.path.join(PUBLIC_DIR, asset)
    if not os.path.exists(path):
        abort(404)
    directory, fname = os.path.split(path)
    return send_from_directory(directory, fname, cache_timeout=0)


# ----------------------------------------------------
# MAIN (sviluppo)
# ----------------------------------------------------
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8000)))
