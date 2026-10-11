"use client";

import { useState, type FormEvent } from "react";
import { ApiError, searchLocation } from "@/lib/api";
import type { LocationResult } from "@/lib/location";

interface LocationSearchProps {
  onSelect: (result: LocationResult) => void;
  selectedLabel: string;
}

export default function LocationSearch({ onSelect, selectedLabel }: LocationSearchProps) {
  const [query, setQuery] = useState("");
  const [searching, setSearching] = useState(false);
  const [results, setResults] = useState<LocationResult[]>([]);
  const [message, setMessage] = useState("");
  const [feedbackLocation, setFeedbackLocation] = useState(selectedLabel);
  const currentFeedback = feedbackLocation === selectedLabel;

  function select(result: LocationResult) {
    onSelect(result);
    setResults([]);
    setMessage("");
  }

  async function search(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (searching) return;
    const q = query.trim();
    setSearching(true);
    setFeedbackLocation(selectedLabel);
    setResults([]);
    setMessage("");
    try {
      const matches = await searchLocation(q);
      if (matches.length === 1) select(matches[0]);
      else if (matches.length > 1) {
        setResults(matches);
        setMessage("Choose a Florida location below.");
      } else setMessage(`No Florida match for "${q}". Try a nearby town or a ZIP code.`);
    } catch (error) {
      setMessage(error instanceof ApiError ? error.message : "Location search is unavailable right now. Click the map or enter coordinates instead.");
    } finally {
      setSearching(false);
    }
  }

  return (
    <div className="mb-5 min-w-0">
      <form onSubmit={search}>
        <label htmlFor="location-search" className="block text-sm font-semibold">City or ZIP code</label>
        <div className="mt-2 flex gap-2">
          <input id="location-search" type="text" value={query} onChange={(event) => setQuery(event.target.value)}
            placeholder="e.g. Plant City or 33563" required maxLength={100}
            aria-describedby="location-search-status" className="min-h-11 w-full min-w-0 rounded-lg border border-field/25 bg-white px-3 py-2" />
          <button type="submit" disabled={searching} className="min-h-11 shrink-0 rounded-lg bg-field px-4 py-2 font-semibold text-white disabled:cursor-wait disabled:opacity-60">
            {searching ? "Searching…" : "Find"}
          </button>
        </div>
      </form>
      <div id="location-search-status" aria-live="polite" aria-busy={searching}>
        {currentFeedback && message && <p className="mt-3 text-sm">{message}</p>}
        {currentFeedback && results.length > 0 && <ul className="mt-3 space-y-2" aria-label="Matching Florida locations">
          {results.map((result, index) => <li key={`${result.lat}:${result.lon}:${index}`}>
            <button type="button" onClick={() => select(result)} className="min-h-11 w-full rounded-lg border border-field/25 bg-white/70 px-3 py-2 text-left hover:bg-leaf/15">{result.label}</button>
          </li>)}
        </ul>}
        {selectedLabel && <p className="mt-3 text-sm font-semibold">{selectedLabel}</p>}
      </div>
      <p className="mt-2 text-xs text-soil">Location search: <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noopener noreferrer" className="inline-flex min-h-11 items-center underline">© OpenStreetMap contributors</a> and <a href="https://www.zippopotam.us/" target="_blank" rel="noopener noreferrer" className="inline-flex min-h-11 items-center underline">Zippopotam.us</a>.</p>
    </div>
  );
}
