import os
from flask import Flask, request, jsonify, send_from_directory, abort, Response
from supabase import create_client, Client

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PUBLIC_DIR = os.path.join(BASE_DIR, "public")

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_KEY = os.environ["SUPABASE_ANON_KEY"]
BUCKET = os.environ.get("SUPABASE_BUCKET", "planny-txt")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
app = Flask(__name__, static_folder=PUBLIC_DIR, static_url_path='')

@app.get("/")
def index():
    return send_from_directory(PUBLIC_DIR, "index.html")

@app.get("/api/files/<path:name>")
def api_read(name):
    try:
        data = supabase.storage.from_(BUCKET).download(name)
        return Response(data.decode("utf-8"), mimetype="text/plain; charset=utf-8")
    except Exception as e:
        return Response("", status=404, mimetype="text/plain")

@app.put("/api/files/<path:name>")
def api_write(name):
    content = request.get_data(as_text=True)
    data = content.encode("utf-8")
    try:
        supabase.storage.from_(BUCKET).update(name, data)
        mode = "update"
    except Exception:
        supabase.storage.from_(BUCKET).upload(name, data, {"contentType": "text/plain"})
        mode = "upload"
    return jsonify(ok=True, path=name, size=len(data), mode=mode)

@app.get("/healthz")
def healthz():
    return "ok"

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8000)))
