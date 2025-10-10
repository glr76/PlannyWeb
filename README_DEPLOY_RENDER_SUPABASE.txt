# Deploy gratis: Render (Flask) + Supabase Storage

Questa cartella contiene i file per mettere **online** la tua app:
- `server_supabase.py`: server Flask che serve `/public` e legge/scrive i `.txt` su **Supabase Storage**.
- `requirements.txt`: dipendenze (Flask, gunicorn, supabase).
- `Procfile`: comando di avvio per Render.

## Passi

1. **Supabase**
   - Crea progetto su Supabase → **Storage → New Bucket** (es. `planny-txt`).
   - Vai su **Settings → API** e copia: **Project URL** e **anon public key**.

2. **Render (piano free)**
   - Crea un nuovo **Web Service** collegando questa cartella (o zip).
   - In **Environment** aggiungi:
     - `SUPABASE_URL` = URL progetto
     - `SUPABASE_ANON_KEY` = anon key
     - `SUPABASE_BUCKET` = planny-txt
   - Build & Deploy. Otterrai un URL pubblico HTTPS.

3. **Compatibilità con il tuo frontend**
   - Le chiamate al tuo front-end che usavano `PUT /api/files/<name>` e `GET /api/files/<name>` continuano a funzionare **senza modifiche**.
   - I file vengono salvati nel bucket con il **path esatto** `<name>` (es. `selections_2026.txt`, `planny_log_2026.txt`).

4. **Test rapido**
   - `GET https://TUO-SERVICE.onrender.com/api/files/selections_2026.txt`
   - `PUT https://.../api/files/selections_2026.txt` con body testuale.

Nota: il piano free di Render va in sleep dopo inattività. Il primo hit può essere più lento.
