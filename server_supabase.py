# server_supabase.py
import os
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
# Helpers
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
    """Legge il file dal bucket e ritorna testo UTF-8 (o stringa vuota se non trovato/errore)."""
    try:
        data = supabase.storage.from_(BUCKET).download(path)
        return data.decode("utf-8", "replace")
    except Exception as e:
        log.warning(f"[download] fail '{path}': {e}")
        return ""


def _upload_text(path: str, content: str):
    """
    Scrive il file su Supabase Storage con metadata anti-cache.
    - Forza cache_control=0 (niente TTL sulla CDN)
    - Prova sia snake_case che camelCase per compatibilità tra versioni dell'SDK
    - Tenta update(); se non va, fallback su upload(upsert=True)
    """
    data_bytes = content.encode("utf-8")

    # Opzioni preferite (snake_case) per supabase-py recenti
    opts_snake = {
        "content_type": "text/plain; charset=utf-8",
        "upsert": True,
        "cache_control": "0",   # <-- TTL zero a livello CDN
    }
    # Fallback camelCase per SDK meno recenti
    opts_camel = {
        "contentType": "text/plain; charset=utf-8",
        "upsert": True,
        "cacheControl": "0",
    }

    store = supabase.storage.from_(BUCKET)

    # 1) tenta UPDATE con opzioni snake_case
    try:
        store.update(path, data_bytes, opts_snake)  # type: ignore[arg-type]
        return
    except Exception as e_snake_upd:
        log.info(f"[update snake] miss '{path}': {e_snake_upd}")

    # 2) tenta UPDATE con opzioni camelCase
    try:
        store.update(path, data_bytes, opts_camel)  # type: ignore[arg-type]
        return
    except Exception as e_camel_upd:
        log.info(f"[update camel] miss '{path}': {e_camel_upd}")

    # 3) fallback: UPLOAD con snake_case
    try:
        store.upload(path, data_bytes, opts_snake)  # type: ignore[arg-type]
        return
    except Exception as e_snake_upl:
        log.info(f"[upload snake] miss '{path}': {e_snake_upl}")

    # 4) ultimo tentativo: UPLOAD con camelCase
    try:
        store.upload(path, data_bytes, opts_camel)  # type: ignore[arg-type]
        return
    except Exception as e_camel_upl:
        log.error(f"[upload fail] '{path}': {e_camel_upl}\n{traceback.format_exc()}")
        raise


def _nocache_headers(extra: dict | None = None) -> dict:
    """Header per disabilitare cache a livello di risposta Flask / proxy a valle di Flask."""
    h = {
        "Cache-Control": "no-store, no-cache, max-age=0, must-revalidate",
        "Pragma": "no-cache",
        "Expires": "0",
        "X-Content-Type-Options": "nosniff",
    }
    if extra:
        h.update(extra)
    return h


def _sha(txt: str) -> str:
    return sha256((txt or "").encode("utf-8")).hexdigest()


def _read_back_until_match(path: str, expected_sha: str, timeout_s: float = 1.6) -> tuple[str, str, bool]:
    """
    Dopo un upload, la CDN di Storage può servire per un attimo la vecchia versione.
    Qui rileggiamo ripetutamente finché l'SHA non combacia o finché scade il timeout.
    Ritorna: (echo_text, echo_sha, matched)
    """
    start = time.time()
    delay = 0.05
    echo = _download_text(path)
    echo_sha = _sha(echo)
    while echo_sha != expected_sha and (time.time() - start) < timeout_s:
        time.sleep(delay)
        delay = min(delay * 2, 0.4)  # backoff fino a 400ms
        echo = _download_text(path)
        echo_sha = _sha(echo)
    return echo, echo_sha, (echo_sha == expected_sha)


# ----------------------------------------------------
# API FILES - JSON (raccomandato)
# ----------------------------------------------------
@app.get("/api/files/text/<path:name>")
def api_text_get(name: str):
    try:
        fname = _sanitize(name)
        txt = _download_text(fname)
        status = 200 if txt != "" else 404
        etag = _sha(txt)
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

        # 1) scrivi
        _upload_text(fname, raw)

        # 2) rileggi con retry fino a match (gestisce eventuale staleness CDN)
        sha_in = _sha(raw)
        echoed, sha_echo, matched = _read_back_until_match(fname, sha_in)

        # 3) risposta JSON con echo e SHA per verifica forte
        payload = {
            "ok": True,
            "name": fname,
            "size": len(raw),
            "echo": echoed,
            "sha_in": sha_in,
            "sha_echo": sha_echo,
            "matched": matched,
        }

        # 4) headers no-cache anche sulla risposta PUT
        headers = _nocache_headers({"ETag": f'W/"{sha_echo}"'})
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
        etag = _sha(txt)
        headers = _nocache_headers({
            "ETag": f'W/"{etag}"',
            "Content-Disposition": f'inline; filename="{os.path.basename(fname)}"',
        })
        return Response(txt, mimetype="text/plain; charset=utf-8", headers=headers)
    except Exception as e:
        log.error(f"[GET legacy] '{name}': {e}\n{traceback.format_exc()}")
        return Response("error", status=500, mimetype="text/plain; charset=utf-8", headers=_nocache_headers())


@app.put("/api/files/<path:name>")
def api_write_text_legacy(name: str):
    try:
        fname = _sanitize(name)
        raw = request.get_data(as_text=True) or ""
        _upload_text(fname, raw)

        sha_in = _sha(raw)
        echoed, sha_echo, matched = _read_back_until_match(fname, sha_in)

        payload = {
            "ok": True,
            "path": fname,
            "size": len(raw),
            "sha_in": sha_in,
            "sha_echo": sha_echo,
            "matched": matched,
        }
        # no-cache anche qui
        resp = make_response(jsonify(payload), 200)
        for k, v in _nocache_headers({"ETag": f'W/"{sha_echo}"'}).items():
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
    # cache_timeout=0 per evitare che dev browser tenga versioni vecchie
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
