# server_render.py — Flask + GitHub Contents API + Auth (admin/user) + anti-lag
import os
import time
import json
import base64
import logging
import traceback
from hashlib import sha256
from functools import wraps

import requests
from flask import (
    Flask, request, send_from_directory, Response,
    jsonify, abort, make_response, session
)
from flask_cors import CORS
from werkzeug.security import check_password_hash

# ----------------------------------------------------
# Config base
# ----------------------------------------------------
BASE_DIR   = os.path.dirname(os.path.abspath(__file__))
PUBLIC_DIR = os.path.join(BASE_DIR, "public")

GITHUB_REPO   = os.environ.get("GITHUB_REPO", "").strip()          # es. "glr76/PlannyWeb"
GITHUB_BRANCH = os.environ.get("GITHUB_BRANCH", "main").strip()
GITHUB_TOKEN  = os.environ.get("GITHUB_TOKEN", "").strip()

# Prefisso cartella nel repo dove tenere i file (di default 'public/')
GITHUB_DIR_PREFIX = os.environ.get("GITHUB_DIR_PREFIX", "public/").strip()
if GITHUB_DIR_PREFIX and not GITHUB_DIR_PREFIX.endswith("/"):
    GITHUB_DIR_PREFIX += "/"

if not GITHUB_REPO:
    raise RuntimeError("Set GITHUB_REPO (es. 'utente/repo') nelle ENV")

_GH_API = "https://api.github.com"

# anti-lag: cache di scrittura in memoria (path -> {content, ts, sha})
WRITE_CACHE_TTL = 120.0
_WRITE_CACHE: dict[str, dict] = {}
_LAST_CACHE_HIT = False

# ----------------------------------------------------
# App & CORS
# ----------------------------------------------------
# Statici serviti da /public alla radice (/, /favicon.ico, /file.png, …)
app = Flask(__name__, static_folder="public", static_url_path="")
CORS(app, resources={r"/api/*": {"origins": "*"}})  # API restano accessibili

logging.basicConfig(level=logging.INFO)
log = app.logger

# ----------------------------------------------------
# Auth (sessione + ruoli)
# ----------------------------------------------------
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "change-me")

USERS_JSON = os.environ.get("USERS_JSON", "{}").strip()
try:
    USERS = json.loads(USERS_JSON) if USERS_JSON else {}
except Exception:
    log.error("USERS_JSON malformato: usare JSON valido")
    USERS = {}

def get_user(username: str):
    return USERS.get(username or "")

def login_user(username: str):
    session.clear()
    session["user"] = username
    session["role"] = (USERS.get(username) or {}).get("role")

def logout_user():
    session.clear()

def current_user():
    return session.get("user")

def current_role():
    return session.get("role")

def requires_role(min_role="read"):
    """Protegge una route in base al ruolo ('read' o 'write')."""
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            role = current_role()
            if role is None:
                return jsonify(ok=False, error="authentication required"), 401
            if min_role == "write" and role != "write":
                return jsonify(ok=False, error="permission denied"), 403
            return f(*args, **kwargs)
        return wrapper
    return decorator

@app.post("/login")
def login_post():
    """Body: JSON {"username":"...", "password":"..."}"""
    try:
        data = request.get_json(force=True, silent=False) or {}
        username = (data.get("username") or "").strip()
        password = data.get("password") or ""
        if not username or not password:
            return jsonify(ok=False, error="missing credentials"), 400
        u = get_user(username)
        if not u or not check_password_hash(u.get("pw_hash", ""), password):
            return jsonify(ok=False, error="invalid username/password"), 401
        login_user(username)
        return jsonify(ok=True, user=username, role=u.get("role")), 200
    except Exception as e:
        log.error(f"[login] {e}\n{traceback.format_exc()}")
        return jsonify(ok=False, error=str(e)), 500

@app.post("/logout")
def logout_post():
    logout_user()
    return jsonify(ok=True)

@app.get("/me")
def me():
    return jsonify(ok=True, user=current_user(), role=current_role())

# (opzionale) paginetta di test login
@app.get("/login")
def login_page():
    html = """
    <!doctype html><meta charset="utf-8"><title>Login</title>
    <form id="f"><input name="username" placeholder="username">
    <input name="password" type="password" placeholder="password">
    <button>Login</button></form>
    <script>
    f.onsubmit = async (e)=>{e.preventDefault();
      const body = {username:f.username.value, password:f.password.value};
      const r = await fetch('/login',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
      alert(await r.text()); location.href='/'}
    </script>
    """
    return html

# ----------------------------------------------------
# Helpers comuni
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
    # auto-prefix nella cartella configurata (p.es. "public/")
    if GITHUB_DIR_PREFIX and not name.startswith(GITHUB_DIR_PREFIX):
        name = GITHUB_DIR_PREFIX + name
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
        "Cache-Control": "no-cache",  # chiedi rievalidazione agli edge
    }
    if GITHUB_TOKEN:
        h["Authorization"] = f"Bearer {GITHUB_TOKEN}"
    return h

def _gh_get_file(path: str) -> tuple[str, str | None]:
    url = f"{_GH_API}/repos/{GITHUB_REPO}/contents/{path}"
    r = requests.get(
        url,
        headers=_gh_headers(),
        params={"ref": GITHUB_BRANCH, "_t": str(time.time())},
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
        global _LAST_CACHE_HIT
        _LAST_CACHE_HIT = False
        return txt
    except Exception as e:
        log.warning(f"[download-gh] fail '{path}': {e}")
        return ""

def _upload_text(path: str, content: str) -> str:
    """Scrive su GitHub e ritorna la content SHA."""
    _current, cur_sha = _gh_get_file(path)
    new_sha = _gh_put_file(path, content, cur_sha)
    log.info(f"[upload-gh] wrote '{path}' sha={new_sha[:8] if new_sha else 'unknown'} on branch {GITHUB_BRANCH}")
    _WRITE_CACHE[path] = {"content": content, "ts": time.time(), "sha": new_sha}
    return new_sha or ""

# ----------------------------------------------------
# Error handler API
# ----------------------------------------------------
@app.errorhandler(Exception)
def _on_error(e):
    if request.path.startswith("/api/"):
        log.error(f"[unhandled] {e}\n{traceback.format_exc()}")
        return jsonify(ok=False, error=str(e)), 500
    # per richieste non-API lascia il default (debug/off)
    raise e

def _resp_with_cache_header(resp, txt: str):
    resp.headers.update(_nocache_headers({"ETag": _etag(txt)}))
    resp.headers["X-Write-Cache"] = "hit" if _LAST_CACHE_HIT else "miss"
    return resp

# ----------------------------------------------------
# API FILES (JSON + text) — GET pubbliche, PUT protette
# ----------------------------------------------------
@app.get("/api/files/text/<path:name>")
def api_text_get(name: str):
    fname = _sanitize(name)
    txt = _download_text(fname)
    status = 200 if txt != "" else 404
    return _resp_with_cache_header(make_response(jsonify(
        ok=(status == 200), name=fname, text=txt
    ), status), txt)

@app.put("/api/files/text/<path:name>")
@requires_role("write")
def api_text_put(name: str):
    fname = _sanitize(name)
    raw = request.get_data(as_text=True) or ""
    commit_sha = _upload_text(fname, raw)
    echoed = _download_text(fname)
    payload = {
        "ok": True,
        "name": fname,
        "branch": GITHUB_BRANCH,
        "commit_sha": commit_sha,
        "size": len(raw),
        "echo": echoed,
        "sha_in": _sha(raw),
        "sha_echo": _sha(echoed),
        "matched": _sha(raw) == _sha(echoed),
    }
    return _resp_with_cache_header(make_response(jsonify(payload), 200), echoed)

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
@requires_role("write")
def api_write_text_legacy(name: str):
    fname = _sanitize(name)
    raw = request.get_data(as_text=True) or ""
    commit_sha = _upload_text(fname, raw)
    echoed = _download_text(fname)
    payload = {
        "ok": True,
        "path": fname,
        "branch": GITHUB_BRANCH,
        "commit_sha": commit_sha,
        "size": len(raw),
        "sha_in": _sha(raw),
        "sha_echo": _sha(echoed),
        "matched": _sha(raw) == _sha(echoed),
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
        prefix = GITHUB_DIR_PREFIX.rstrip("/") if GITHUB_DIR_PREFIX else ""
        files = _gh_list(prefix)
        return jsonify(ok=True, source="github", branch=GITHUB_BRANCH, prefix=GITHUB_DIR_PREFIX, count=len(files), files=files)
    except Exception as e:
        log.error(f"[LIST] {e}\n{traceback.format_exc()}")
        return jsonify(ok=False, error=str(e)), 500

@app.get("/healthz")
def healthz():
    return "ok"

# ----------------------------------------------------
# STATIC: index + favicon (gli altri statici li serve Flask automaticamente da /public)
# ----------------------------------------------------
@app.get("/")
def index():
    return app.send_static_file("index.html")

@app.get("/favicon.ico")
def favicon():
    return app.send_static_file("favicon.ico")

# ----------------------------------------------------
# MAIN
# ----------------------------------------------------
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8000)))
