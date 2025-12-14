# AOD Preview UI

This repository now includes a standalone React + Tailwind UI for showcasing AOD with fully mocked data. Preview mode is enabled by default so you can deploy without any database or backend services.

## Render Preview Mode

Use these settings for a zero-backend "pretty preview" deployment on Render:

- **Environment variables**
  - `PREVIEW_MODE=true` (default; ensures mocks are used and no backend calls run)
  - `API_BASE_URL` (optional; only used when `PREVIEW_MODE=false`)
- **Build command**: `npm install && npm run build`
- **Start command**: `npm start`
- **Port**: Render-provided `$PORT` is respected automatically by the Vite preview server

When `PREVIEW_MODE` is on, the UI loads data from `/src/mocks/*`, never initializes database clients, and renders instantly with mock JSON fixtures. If you turn preview mode off, the UI will call `API_BASE_URL` but will fall back to the same fixtures if the API is unreachable.

## Local usage

```bash
npm install
npm run dev  # serves on http://localhost:5173
```

Build and preview the production bundle locally:

```bash
npm run build
npm start
```
