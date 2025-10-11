# server_supabase.py
import os
import logging
from flask import Flask, request, send_from_directory, Response, jsonify, abort
from flask_cors import CORS
from supabase import create_client

# ----------------------------------------------------
# Config
# ----------------------------------------------------
BASE_DIR   = os.path.dirname(os.path.abspath(__file__))
PUBLIC_DIR = os.path.join(BASE_DIR, "public")

SUPABASE_URL = os.environ["SUPABASE_URL"]
# Service Role per scrivere in Storage (se non c'è, ripiega su anon, sconsigliato per write)
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE") or os.environ["SUPABASE_ANON_KEY"]
BUCKET       = os.environ.get("SUPABASE_BUCKET", "planny-txt")

# Supabase client
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# Flask
app = Flask(__name__, static_folder=PUBLIC_DIR, static_url_path="")
CORS(app)

# Logging utile per debug 500
logging.basicConfig(level=logging.INFO)
log = app.logger


# ----------------------------------------------------
# Helpers Storage
# ----------------------------------------------------
def _sanitize(name: str) -> str:
    # niente percorsi assoluti / traversal
    name = name.strip().replace("\\", "/")
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
        return data.decode("utf-8")
    except Exception as e:
        log.warning(f"download fail [{path}]: {e}")
        return ""

def _upload_text(path: str, content: str):
    data = content.encode("utf-8")
    try:
        # 1) tenta update (sovrascrive se esiste)
        supabase.storage.from_(BUCKET).update(path, data)
        return
    except Exception as e:
        log.info(f"update miss for [{path}] -> trying upload: {e}")
    # 2) se non esiste, crea con upload
    try:
        # alcune versioni SDK supportano upsert=True:
        # supabase.storage.from_(BUCKET).upload(path, data, {"contentType":"text/plain; charset=utf-8", "upsert": True})
        supabase.storage.from_(BUCKET).upload(path, data, {"contentType":"text/plain; charset=utf-8"})
        return
    except Exception as e:
        log.error(f"upload fail [{path}]: {e}", exc_info=True)
        raise


# ----------------------------------------------------
# STATIC
# ----------------------------------------------------
@app.get("/")
def index():
    # /public/index.html
    ix = os.path.join(PUBLIC_DIR, "index.html")
    if not os.path.exists(ix):
        return "index.html non trovato in /public", 404
    return send_from_directory(PUBLIC_DIR, "index.html")

@app.get("/<path:asset>")
def static_files(asset):
    path = os.path.join(PUBLIC_DIR, asset)
    if not os.path.exists(path):
        abort(404)
    directory, fname = os.path.split(path)
    return send_from_directory(directory, fname)


# ----------------------------------------------------
# API FILES - TEXT (legacy) e JSON (raccomandato)
# ----------------------------------------------------
# GET testo puro
@app.get("/api/files/<path:name>")
def api_read_text_legacy(name):
    try:
        name = _sanitize(name)
        txt = _download_text(name)
        if txt == "":
            return Response("", status=404, mimetype="text/plain; charset=utf-8")
        return Response(txt, mimetype="text/plain; charset=utf-8")
    except Exception as e:
        log.error(f"GET legacy error [{name}]: {e}", exc_info=True)
        return Response("error", status=500, mimetype="text/plain; charset=utf-8")

# PUT testo puro
@app.put("/api/files/<path:name>")
def api_write_text_legacy(name):
   
