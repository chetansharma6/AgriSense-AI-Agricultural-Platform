# AgriSense

![AgriSense home page with the Florida map and example locations](docs/screenshots/home-map.png)

[Try the live app](https://agrisense-ai-cyan.vercel.app)

AgriSense helps small and mid-scale Florida farmers decide what to plant by ranking 13 crops for a selected location. Each crop report includes an explainable suitability score, local yield and price history, growing guidance, and UF/IFAS Extension links.

## Features

- Pick a Florida location on the map or enter latitude and longitude.
- Compare 13 crops ranked by deterministic, explainable suitability scores.
- Inspect six factors and the best Florida growing window for each crop.
- Review regional yield and price history, missing-data warnings, and UF/IFAS links.
- Read a plain-language AI report grounded in the calculated crop data, with a local fallback when AI is unavailable.

## How it works

USDA SSURGO soil data, NASA POWER climate history, and USDA NASS harvest and price records feed a Python scoring engine. It compares crop requirements across Florida growing windows, ranks the crops, and supplies the results to a server-side AI report generator. The AI does not calculate the scores.

Read the [methodology](docs/methodology.md) for factor weights, missing-data handling, and limitations. The four demo choices are example growing locations, not verified individual farms.

## Screenshot gallery

### Florida map and location controls

![Florida map, demo locations, and coordinate inputs](docs/screenshots/home-controls.png)

### Plant City results

![Land conditions for the Plant City example location](docs/screenshots/plant-city-conditions.png)

![Plant City crop rankings with strawberry, potato, and watermelon](docs/screenshots/plant-city-results.png)

### Strawberry report

![Strawberry AI summary with pros, cons, and first steps](docs/screenshots/strawberry-report.png)

### About AgriSense

![Public data to calculated score to AI explanation](docs/screenshots/about.png)

![AgriSense public data sources](docs/screenshots/about-sources.png)

![The six suitability factors and their weights](docs/screenshots/about-factors.png)

Screenshots capture example responses; scores and reports can change as data changes. The strawberry screenshot shows the report section; its crop-detail factor chart is not pictured.

For a walkthrough, see the [75-second demo video script](docs/demo-video-script.md).

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
http://localhost:8000 with mock mode disabled. Start the backend before
using the frontend; set `NEXT_PUBLIC_USE_MOCKS=true` only for an offline UI demo.
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
Vercel Links:

  Inspect         https://vercel.com/rich5369/agrisense-ai/B2T3nyRfFb2vzo9wmnYeFRyo9d7G
  Production      https://agrisense-t2dq1ryjw-rich5369.vercel.ap
  Production      https://agrisense-t2dq1ryjw-rich5369.vercel.app
▲ Aliased         https://agrisense-ai-cyan.vercel.app
