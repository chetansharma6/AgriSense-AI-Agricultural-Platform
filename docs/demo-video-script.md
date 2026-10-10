# AgriSense: 75-second demo video

Record the live app at https://agrisense-ai-cyan.vercel.app in a desktop window with browser zoom at 100%. Preload both locations and the strawberry report before recording. Trim waiting time with clear cuts; leave cached-data notices visible and do not describe saved responses as fresh live fetches. Check current scores before recording; the narration avoids fixed rankings or numbers.

| Time | Screen action | Narration |
|---|---|---|
| 0:00–0:08 | Show the home headline, then scroll to the Florida map and demo controls. | “What should you plant on your Florida land? AgriSense compares 13 crops and shows why each one fits.” |
| 0:08–0:18 | Click Plant City, then Analyze my land; show the land conditions after loading. | “Let's start in Plant City. We bring together public soil, climate, and harvest data for this example growing location.” |
| 0:18–0:28 | Scroll to the ranked crop cards; point to strawberry's score. | “The crops are ranked by a calculated suitability score. Each card shows the factors and its recommended Florida growing window.” |
| 0:28–0:40 | Open Strawberry; scroll to “Why it ranked here.” Point to pH and climate factors. | “Open strawberry and you can inspect soil pH, drainage, temperature, frost risk, rainfall, and local history. Every score has a reason.” |
| 0:40–0:51 | Scroll to the loaded AI summary, pros, cons, and first steps. | “AI turns those calculated results into a plain-English report. It explains the supplied numbers; it has no role in calculating the scores.” |
| 0:51–1:04 | Return home, click Belle Glade, then Analyze my land; show muck conditions and rankings, and highlight sugarcane. | “Now switch to Belle Glade. Different soil changes the recommendations. Here, muck suitability matters, and sugarcane is among the strong options in our saved example.” |
| 1:04–1:11 | Open “About the data”; show the three-step pipeline and source cards. | “USDA and NASA data feed a transparent scoring engine, using crop requirements drawn from UF/IFAS guidance.” |
| 1:11–1:15 | Finish on the home headline or a title card with the live URL. | “AgriSense: pick a spot, see what fits, and understand why.” |

## Recording checks

- Capture a readable 1080p video with a steady cursor and no open DevTools.
- Keep narration and screen actions within the 75-second timeline.
- If the report says AI is unavailable, show that label and describe the local fallback honestly, or record again when AI is available.
- Show the actual ranking: sugarcane need not rank first in Belle Glade.
- Demo locations represent growing regions, not verified individual farm records.
## Judge walkthrough

1. Start with `/api/health` or the loaded app so the judge sees the service is
   reachable.
2. Choose Plant City and show the 13 ranked crops.
3. Open strawberry and point out the six factor scores, growing window, local
   history, and UF/IFAS links.
4. Explain that the ranking is deterministic and that the AI only writes the
   bounded explanation.
5. Choose Belle Glade and point out the muck-soil behavior and changed crop
   fit. This is the clearest contrast between locations.
6. Show provenance, source status, warnings, and confidence. If a provider is
   unavailable, show the missing factor and warning rather than hiding it.
7. If the AI provider is unavailable, show that the local report still gives
   useful next steps.

## Questions to answer plainly

- The score is a reproducible suitability index, not a probability, yield
  forecast, or profit estimate.
- Missing sources produce null factors and warnings; they are not fabricated
  as zeroes. The available factors are renormalized.
- Exact official demo locations use committed demo responses in `DEMO_MODE`;
  that path is intentionally deterministic and should not be described as a
  fresh live fetch.
- The project has tests for formulas, provider failures, contracts, demo
  responses, and response integrity. It does not claim field validation,
  production uptime, or load-test results.

Closing line: “The model writes the explanation, but the recommendation is
calculated from traceable data and deterministic rules.”
