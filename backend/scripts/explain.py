"""Print the crop ranking and factor scores for each demo farm.

Uses the real data sources (cached after the first run). From backend/:
    python -m scripts.explain
"""

from app.config import DEMO_FARMS
from app.scoring import CRITICAL_CAP, WEIGHTS
from app.service import recommend

COLUMNS = list(WEIGHTS)


def cell(value: int | None) -> str:
    return "-" if value is None else str(value)


def main() -> None:
    header = ["Rank", "Crop", "Score", *COLUMNS, "Best window"]
    for farm, (lat, lon) in DEMO_FARMS.items():
        result = recommend(lat, lon)
        location = result["location"]
        print(f"\n{farm} ({lat}, {lon}) - {location['county']} County")
        rows = [header]
        for rank, crop in enumerate(result["crops"], start=1):
            capped = "*" if crop["limited_by"] else ""
            rows.append([str(rank), crop["name"], f"{cell(crop['score'])}{capped}",
                         *(cell(crop["factors"][name]) for name in COLUMNS), crop["season_label"]])
        widths = [max(len(row[i]) for row in rows) for i in range(len(header))]
        for row in rows:
            print(" | ".join(text.ljust(width) for text, width in zip(row, widths)).rstrip())
        for warning in result["warnings"]:
            print(f"  warning: {warning}")
    print(f"\n* capped at {CRITICAL_CAP}: a critical factor scored below the threshold")


if __name__ == "__main__":
    main()
