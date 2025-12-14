# Render preview deployment

Use these commands when configuring a **Web Service** on Render to preview AOD remotely.

## Build command
Render runs the build step in a clean environment. Install dependencies from PyPI directly—Render cannot reach the Replit package proxy referenced in `pip.conf`.

```bash
pip install -r requirements.txt
```

## Start command
Render injects a `$PORT` environment variable. Bind to it with Uvicorn so the service responds on the provided port:

```bash
uvicorn main:app --host 0.0.0.0 --port $PORT
```

## Notes
- Ensure `DATABASE_URL` is set in the Render dashboard (Environment tab). You need a Postgres-style connection string (Render Postgres or Supabase). Replit DB URLs will not work because the app expects Postgres.
- If you need to add build-time tools (e.g., `uv`), use the same `pip install ...` pattern without `PIP_CONFIG_FILE` so installs keep using PyPI.
- If your Render environment requires a custom index, set `PIP_INDEX_URL`/`PIP_EXTRA_INDEX_URL` explicitly; avoid `pip.conf` because it points to the Replit proxy.
- No Procfile is required; Render uses the start command directly.
