"use client";

import { useEffect } from "react";
import { CircleMarker, MapContainer, TileLayer, Tooltip, useMap, useMapEvents } from "react-leaflet";
import "leaflet/dist/leaflet.css";

export interface MapPoint {
  lat: number;
  lon: number;
}

export interface DemoPin extends MapPoint {
  name: string;
}

export interface FloridaMapProps {
  value: MapPoint | null;
  onChange: (lat: number, lon: number) => void;
  demoPins: readonly DemoPin[];
}

function MapClicks({ onChange }: Pick<FloridaMapProps, "onChange">) {
  useMapEvents({
    click: ({ latlng }) => onChange(latlng.lat, latlng.lng),
  });
  return null;
}

function MapViewport({ value }: Pick<FloridaMapProps, "value">) {
  const map = useMap();
  const lat = value?.lat;
  const lon = value?.lon;

  useEffect(() => {
    if (lat !== undefined && lon !== undefined) {
      // Avoid a pending Leaflet zoom animation when navigating immediately to results.
      map.setView([lat, lon], 9, { animate: false });
    }
  }, [map, lat, lon]);

  useEffect(() => {
    const observer = new ResizeObserver(() => map.invalidateSize());
    observer.observe(map.getContainer());
    map.invalidateSize();
    return () => observer.disconnect();
  }, [map]);

  return null;
}

export default function FloridaMap({ value, onChange, demoPins }: FloridaMapProps) {
  return (
    <MapContainer
      center={[27.8, -83.0]}
      zoom={6}
      minZoom={5}
      maxBounds={[[23.3, -88.7], [32.1, -78.9]]}
      maxBoundsViscosity={1}
      style={{ height: "100%", width: "100%" }}
      className="rounded-lg bg-sand"
      aria-label="Select a Florida farm location"
    >
      <TileLayer
        url="https://tile.openstreetmap.org/{z}/{x}/{y}.png"
        attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
      />
      <MapClicks onChange={onChange} />
      <MapViewport value={value} />
      {demoPins.map((pin) => (
        <CircleMarker
          key={`${pin.name}:${pin.lat}:${pin.lon}`}
          center={[pin.lat, pin.lon]}
          radius={9}
          bubblingMouseEvents={false}
          pathOptions={{ color: "#2f6b3a", fillColor: "#7fb069", fillOpacity: 1, weight: 2 }}
          eventHandlers={{ click: () => onChange(pin.lat, pin.lon) }}
        >
          <Tooltip>{pin.name}</Tooltip>
        </CircleMarker>
      ))}
      {value && (
        <CircleMarker
          center={[value.lat, value.lon]}
          radius={9}
          interactive={false}
          pathOptions={{ color: "#ffffff", fillColor: "#e9a23b", fillOpacity: 1, weight: 3 }}
        />
      )}
    </MapContainer>
  );
}
