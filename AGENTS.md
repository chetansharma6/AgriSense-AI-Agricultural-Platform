# AgriSense — project brief for AI coding agents

## What we are building
Target user: beginner and small-scale Florida farmers

AgriSense helps small and mid-scale Florida farmers decide what to plant.
The user picks a location in Florida (map click or lat/lon). The app returns
a ranked list of 13 crops ordered by a 0-100 suitability score, and a report
per crop: score breakdown by factor, local yield and price history, pros and
cons, general guidance, and UF/IFAS Extension links.

Hackathon scope: software only, Florida only, 13 crops. No robotics, no
sensors, no user accounts, no database (JSON/CSV files only).

## Team and ownership
- Person A owns backend/ (Python). Branches: a/<feature>.
- Person B owns frontend/ (Next.js). Branches: b/<feature>.
- Shared files (AGENTS.md, CLAUDE.md, docs/api-contract.md, README.md,
  .claude/, .githooks/) change only on a branch named shared/<change> and
  both people must agree.
- Never edit the other person's folder unless the prompt says so.
- Never commit directly to main. Work on a branch, push it, open a PR.

## Git authorship (required)
- Commits are authored ONLY by the human running this session, using their
  existing git config user.name and user.email. Never change git config
  user.name or user.email, never pass --author, never use -c user.*.
- Never add AI attribution anywhere: no "Co-Authored-By:" trailers, no
  "Generated with ...", "Created by ...", or "AI-assisted" lines, and no
  links to AI sessions, in commit messages, PR titles or PR descriptions.
- Commit messages: one short imperative summary line, optional body that
  explains what changed. Nothing else.
- The repo's .githooks/commit-msg strips AI co-author lines as a safety
  net. Keep git config core.hooksPath set to .githooks.

## Stack
- backend/: Python 3.11+, FastAPI, uvicorn, pandas, httpx, pydantic,
  python-dotenv, pytest. Data cached in backend/data/.
- frontend/: Next.js (App Router, TypeScript, src/ dir), Tailwind CSS,
  Recharts, react-leaflet + leaflet, @anthropic-ai/sdk (server side only).

## Core design rule
Scores are DETERMINISTIC and EXPLAINABLE: computed in Python from data and
a crop requirements table. The LLM only writes plain-language text from those
numbers. The LLM never invents scores, yields, prices or product names.

## Data sources (all free)
- USDA NRCS Soil Data Access (SSURGO), no key: soil pH, organic matter,
  sand/clay, drainage class. Endpoint:
  https://sdmdataaccess.sc.egov.usda.gov/Tabular/post.rest
- NASA POWER daily point API, no key: temperature, precipitation, solar.
  https://power.larc.nasa.gov/api/temporal/daily/point
- USDA NASS Quick Stats, free key in env var NASS_API_KEY: county yields,
  state prices. https://quickstats.nass.usda.gov/api/api_GET/
- FCC Census Area API, no key: lat/lon -> county name and FIPS.
  https://geo.fcc.gov/api/census/area
- Do NOT use NOAA's deprecated CDO v2 API.

## Florida specifics
- Bounding box: lat 24.3 to 31.1, lon -87.7 to -79.9.
- Most FL vegetables grow Sep-May, not summer. Every crop has fl_windows (one
  or more Florida growing windows); climate factors are scored per window
  and the best window wins.
- South Florida may have zero freeze days: frost-free days = 365 is valid.
- Everglades Agricultural Area has muck (organic) soils: organic matter > 20%
  means texture "muck".
- Extension source: UF/IFAS Extension, EDIS (edis.ifas.ufl.edu).

## Crops (id: NASS commodity_desc / class_desc)
peanut: PEANUTS | cotton: COTTON | field_corn: CORN (grain) |
soybean: SOYBEANS | sugarcane: SUGARCANE | tomato: TOMATOES |
watermelon: MELONS / WATERMELON | strawberry: STRAWBERRIES | potato: POTATOES |
sweet_corn: SWEET CORN | snap_bean: BEANS / SNAP | bell_pepper: PEPPERS / BELL |
cabbage: CABBAGE

## Demo locations
marianna 30.80,-85.25 | hastings 29.71,-81.50 | plant_city 28.03,-82.15 |
belle_glade 26.68,-80.68

## API contract
Source of truth: docs/api-contract.md. Frontend types in
frontend/src/lib/types.ts must match it exactly.

## Rules for agents
- Small, readable functions with type hints / TypeScript types.
- Never hardcode secrets. Read keys from env vars. Never print keys.
- Never commit .env or .env.local.
- When a task is done: run the relevant tests or build, then git add, commit
  (following Git authorship above), and git push the current branch.
- If something in a prompt conflicts with this file, ask before proceeding.
