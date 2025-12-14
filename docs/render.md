# Render preview deployment

Use these commands when configuring a **Web Service** on Render to preview AOD remotely.

## Build command
Render runs the build step in a clean environment. Use the bundled proxy-safe pip configuration so dependencies install reliably:

```bash
PIP_CONFIG_FILE=./pip.conf pip install -r requirements.txt
```

## Start command
Render injects a `$PORT` environment variable. Bind to it with Uvicorn so the service responds on the provided port:

```bash
uvicorn main:app --host 0.0.0.0 --port $PORT
```

## Notes
- Ensure `DATABASE_URL` is set in the Render dashboard (Environment tab).
- If you add build-time tools (e.g., `uv`), keep the `PIP_CONFIG_FILE` prefix so installs continue to bypass the blocked MITM proxy.
- No Procfile is required; Render uses the start command directly.
