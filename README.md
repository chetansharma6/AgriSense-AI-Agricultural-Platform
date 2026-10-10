# AgriSense

AgriSense helps small and mid-scale Florida farmers decide what to plant by ranking 13 crops for a selected location. Each crop report includes an explainable suitability score, local yield and price history, growing guidance, and UF/IFAS Extension links.

## Team

- Person A (backend): [Name]
- Person B (frontend): [Name]

## Run the backend

Needs Python 3.11 or newer. Get a free NASS Quick Stats key at
https://quickstats.nass.usda.gov/api.

macOS / Linux:

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# edit .env and set NASS_API_KEY=your_key
uvicorn app.main:app --reload --port 8000
```

Windows (PowerShell):

```powershell
cd backend
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
# edit .env and set NASS_API_KEY=your_key
uvicorn app.main:app --reload --port 8000
```

Check http://localhost:8000/api/health returns `{"status":"ok"}`, and run the
tests with `pytest`. Set `DEMO_MODE=true` in `.env` for a live demo: if the data
sources take over 6 s or fail, a point within 25 km of a demo farm gets that
farm's saved response (backend/data/demo) and other points get a quick 503.
More detail: [backend/README.md](backend/README.md).

## Run the frontend

```bash
cd frontend
npm install
cp .env.local.example .env.local
npm run dev
```

Open http://localhost:3000. The example environment points to the backend at
http://localhost:8000 and enables mock mode for future API integration.
Keep `ANTHROPIC_API_KEY` in `.env.local` and use it only on the server.

To check the frontend:

```bash
npm run lint
npm run build
```

## First-time setup

Set your own Git identity to match your GitHub account, then enable the repository hooks:

```bash
git config user.name "Your Name"
git config user.email "your-email@example.com"
git config core.hooksPath .githooks
```
