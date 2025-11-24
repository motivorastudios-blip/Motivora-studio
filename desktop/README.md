# Motivora Studio Desktop Shell

This folder contains the Electron wrapper that packages the existing Flask + Blender workflow into a downloadable desktop app.

## Requirements

- Node.js 18+
- Python 3.9+ (already used by the Flask service)
- Blender 4.x installed locally (Motivora auto-detects the default `/Applications/Blender.app` path; override with `BLENDER_BIN` if needed)

## Scripts

```bash
cd desktop
npm install          # already run once
npm start            # launches Electron, spawns python3 ../server.py, and opens the UI
SKIP_PY_SERVER=1 npm run dev   # Connect Electron to an already-running server (useful during Flask development)
```

The Electron process spawns `python3 ../server.py` on macOS/Linux (or `python` on Windows) and pings `http://127.0.0.1:1351/status/ping` until the Flask app is ready. When you quit the desktop app the Python process is terminated automatically.

## Packaging

We can wire [`electron-builder`](https://www.electron.build/) once we’re ready to produce signed DMG/EXE artifacts. For now the development entry points give you a 1:1 preview of the final desktop experience.





