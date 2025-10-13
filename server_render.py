# server_supabase.py — Flask + GitHub Contents API (read/write .txt) con anti-lag
import os
import time
import json
import base64
import logging
import traceback
from hashlib import sha256

import requests
from flask import Flask, request, send_from_directory, Response, jsonify, abort, make_response
from flask_cors import CORS

# ----------------------------------------------------
# Config
# ----------------------------------------------------
BASE_DIR   = os.path.dirname(os.path.abspath(__file__))
PUBLIC_DIR = os.path.join(BASE_DIR, "public")

GITHUB_REPO   = os.environ.get("GITHUB_REPO", "").strip()          # es. "glr76/PlannyWeb"
GITHUB_BRANCH = os.environ.get("GITHUB_BRANCH", "main").strip()
GITHUB_TOKEN  = os.environ.get("GITHUB_TOKEN", "").strip()
if not GITHUB_REPO:
    raise RuntimeError("Set GITHUB_REPO (es. 'utente/repo') nelle ENV")
_GH_API = "https://api.github.com"

# anti-lag: cache di scrittura in memoria (path -> {content, ts, sha})
WRITE_CACHE_TTL = 120.0  # secondi
_WRITE_CACHE: dict[str, dict] = {}
_LAST_CACHE_HIT = False

app = Flask(__name__, static_folder=PUBLIC_DIR, static_url_path="/static")
CORS(app, resources={r"/api/*": {"origins": "*"}})

logging.basicConfig(level=logging.INFO)
log = app.logger


# ----------------------------------------------------
# Helpers
# ----------------------------------------------------
def _nocache_headers(extra: dict | None = None) -> dict:
    h = {
        "Cache-Control": "no-store, no-cache, max-age=0, must-revalidate",
        "Pragma": "no-cache",
        "Expires": "0",
        "X-Content-Type-Options": "nosniff",
        "X-Debug-Source": "render-flask",
        "X-Debug-Time": time.strftime("%H:%M:%S"),
    }
    if extra:
        h.update(extra)
    return h

def _sanitize(name: str) -> str:
    name = (name or "").strip().replace("\\", "/")
    while "//" in name:
        name = name.replace("//", "/")
    if name.startswith("/"):
        name = name[1:]
    if ".." in name:
        raise ValueError("Invalid path")
    return name

def _sha(txt: str) -> str:
    return sha256((txt or "").encode("utf-8")).hexdigest()

def _etag(txt: str) -> str:
    return f'W/"{_sha(txt)}"'


# ----------------------------------------------------
# GitHub Contents API
# ----------------------------------------------------
def _gh_headers():
    h = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "planny-server/1.0",
        # suggeriamo rievalidazione
        "Cache-Control": "no-cache",
    }
    if GITHUB_TOKEN:
        h["Authorization"] = f"Bearer {GITHUB_TOKEN}"
    return h

def _gh_get_file(path: str) -> tuple[str, str | None]:
    """
    Ritorna (content_text, sha) se il file esiste, altrimenti ("", None).
    """
    url = f"{_GH_API}/repos/{GITHUB_REPO}/contents/{path}"
    r = requests.get(
        url,
        headers=_gh_headers(),
        params={"ref": GITHUB_BRANCH, "_t": str(time.time())},  # bust proxy caches
        timeout=20,
    )
    if r.status_code == 200:
        j = r.json()
        b64 = (j.get("content") or "").encode()
        content = base64.b64decode(b64.replace(b"\n", b"")).decode("utf-8", "replace")
        return content, j.get("sha")
    if r.status_code == 404:
        return "", None
    raise RuntimeError(f"GitHub GET {r.status_code}: {r.text[:200]}")

def _gh_put_file(path: str, content: str, sha: str | None) -> str:
    """
    Crea/aggiorna un file nel repo (branch configurato).
    Se 'sha' è None fa create, altrimenti update.
    Ritorna la sha del nuovo blob.
    """
    url = f"{_GH_API}/repos/{GITHUB_REPO}/contents/{path}"
    payload = {
        "message": f"update {path} via API",
        "content": base64.b64encode(content.encode("utf-8")).decode(),
        "branch": GITHUB_BRANCH,
    }
    if sha:
        payload["sha"] = sha
    r = requests.put(url, headers=_gh_headers(), data=json.dumps(payload), timeout=30)
    if r.status_code in (200, 201):
        j = r.json()
        return (j.get("content") or {}).get("sha", "")
    if r.status_code == 409:
        raise RuntimeError("Git conflict (409): file aggiornato da un altro commit. Ricarica e riprova.")
    raise RuntimeError(f"GitHub PUT {r.status_code}: {r.text[:300]}")

def _gh_list(prefix: str = "") -> list[dict]:
    """
    Lista file nella directory 'prefix' (solo primo livello).
    """
    url = f"{_GH_API}/repos/{GITHUB_REPO}/contents/{prefix}"
    r = requests.get(
        url,
        headers=_gh_headers(),
        params={"ref": GITHUB_BRANCH, "_t": str(time.time())},
        timeout=20,
    )
    if r.status_code == 200:
        items = r.json()
        out = []
        for it in items:
            if it.get("type") == "file":
                out.append({"name": it.get("name"), "path": it.get("path"), "sha": it.get("sha"), "type": "file"})
        return out
    if r.status_code == 404:
        return []
    raise RuntimeError(f"GitHub LIST {r.status_code}: {r.text[:200]}")


# ----------------------------------------------------
# I/O con anti-lag
# ----------------------------------------------------
def _serve_from_write_cache(path: str) -> str | None:
    global _LAST_CACHE_HIT
    e = _WRITE_CACHE.get(path)
    if not e:
        _LAST_CACHE_HIT = False
        return None
    if (time.time() - e["ts"]) > WRITE_CACHE_TTL:
        _WRITE_CACHE.pop(path, None)
        _LAST_CACHE_HIT = False
        return None
    _LAST_CACHE_HIT = True
    return e["content"]

def _download_text(path: str) -> str:
    cached = _serve_from_write_cache(path)
    if cached is not None:
        return cached
    try:
        txt, _cur_sha = _gh_get_file(path)
        # lettura da GitHub = miss
        global _LAST_CACHE_HIT
        _LAST_CACHE_HIT = False
        return txt
    except Exception as e:
        log.warning(f"[download-gh] fail '{path}': {e}")
        return ""

def _upload_text(path: str, content: str):
    try:
        _current, cur_sha = _gh_get_file(path)     # sha corrente (se c'è)
        new_sha = _gh_put_file(path, content, cur_sha)
        log.info(f"[upload-gh] wrote '{path}' sha={new_sha[:8] if new_sha else 'unknown'}")
        # anti-lag: metti subito in cache per servire letture istantanee
        _WRITE_CACHE[path] = {"content": content, "ts": time.time(), "sha": new_sha}
    except Exception as e:
        log.error(f"[upload-gh] fail '{path}': {e}\n{traceback.format_exc()}")
        raise


# ----------------------------------------------------
# Error handler (JSON per /api/*)
# ----------------------------------------------------
@app.errorhandler(Exception)
def _on_error(e):
    if request.path.startswith("/api/"):
        log.error(f"[unhandled] {e}\n{traceback.format_exc()}")
        return jsonify(ok=False, error=str(e)), 500
    raise e


# ----------------------------------------------------
# API FILES - JSON (raccomandato)
# ----------------------------------------------------
@app.get("/api/files/text/<path:name>")
def api_text_get(name: str):
    fname = _sanitize(name)
    txt = _download_text(fname)
    status = 200 if txt != "" else 404
    resp = make_response(jsonify(ok=(status == 200), name=fname, text=txt), status)
    resp.headers.update(_nocache_headers({"ETag": _etag(txt)}))
    resp.headers["X-Write-Cache"] = "hit" if _LAST_CACHE_HIT else "miss"
    return resp

@app.put("/api/files/text/<path:name>")
def api_text_put(name: str):
    fname = _sanitize(name)
    raw = request.get_data(as_text=True) or ""
    _upload_text(fname, raw)
    echoed = _download_text(fname)  # immediato via cache
    payload = {
        "ok": True,
        "name": fname,
        "size": len(raw),
        "echo": echoed,
        "sha_in": _sha(raw),
        "sha_echo": _sha(echoed),
        "matched": _sha(raw) == _sha(echoed),
    }
    resp = make_response(jsonify(payload), 200)
    resp.headers.update(_nocache_headers({"ETag": _etag(echoed)}))
    resp.headers["X-Write-Cache"] = "hit" if _LAST_CACHE_HIT else "miss"
    return resp


# ----------------------------------------------------
# API FILES - Legacy (testo puro)
# ----------------------------------------------------
@app.get("/api/files/<path:name>")
def api_read_text_legacy(name: str):
    fname = _sanitize(name)
    txt = _download_text(fname)
    if txt == "":
        return Response("", status=404, mimetype="text/plain; charset=utf-8", headers=_nocache_headers())
    headers = _nocache_headers({
        "ETag": _etag(txt),
        "Content-Disposition": f'inline; filename="{os.path.basename(fname)}"',
    })
    resp = Response(txt, mimetype="text/plain; charset=utf-8", headers=headers)
    resp.headers["X-Write-Cache"] = "hit" if _LAST_CACHE_HIT else "miss"
    return resp

@app.put("/api/files/<path:name>")
def api_write_text_legacy(name: str):
    fname = _sanitize(name)
    raw = request.get_data(as_text=True) or ""
    _upload_text(fname, raw)
    echoed = _download_text(fname)
    payload = {
        "ok": True,
        "path": fname,
        "size": len(raw),
        "sha_in": _sha(raw),
        "sha_echo": _sha(echoed),
    }
    resp = make_response(jsonify(payload), 200)
    resp.headers.update(_nocache_headers({"ETag": _etag(echoed)}))
    resp.headers["X-Write-Cache"] = "hit" if _LAST_CACHE_HIT else "miss"
    return resp


# ----------------------------------------------------
# LIST + HEALTH
# ----------------------------------------------------
@app.get("/api/files/list")
def api_list_files():
    try:
        files = _gh_list("")  # root del repo; usa "public" se vuoi solo quella cartella
        return jsonify(ok=True, source="github", count=len(files), files=files)
    except Exception as e:
        log.error(f"[LIST] {e}\n{traceback.format_exc()}")
        return jsonify(ok=False, error=str(e)), 500

@app.get("/healthz")
def healthz():
    return "ok"


# ----------------------------------------------------
# STATIC (/public) – serviti dal repo
# ----------------------------------------------------
@app.get("/")
def index():
    ix = os.path.join(PUBLIC_DIR, "index.html")
    if not os.path.exists(ix):
        return "index.html non trovato in /public", 404
    resp = send_from_directory(PUBLIC_DIR, "index.html", cache_timeout=0)
    resp.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    resp.headers["Pragma"] = "no-cache"
    resp.headers["Expires"] = "0"
    return resp

@app.get("/<path:asset>")
def static_files(asset):
    path = os.path.join(PUBLIC_DIR, asset)
    if not os.path.exists(path):
        abort(404)
    directory, fname = os.path.split(path)
    resp = send_from_directory(directory, fname, cache_timeout=0)
    resp.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    resp.headers["Pragma"] = "no-cache"
    resp.headers["Expires"] = "0"
    return resp


# ----------------------------------------------------
# MAIN (sviluppo)
# ----------------------------------------------------
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8000)))
