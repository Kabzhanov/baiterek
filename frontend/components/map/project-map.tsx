"use client";
// Leaflet-карта карты проектов (SPEC.md §4.6). Клиентский компонент — импортируется
// на странице ТОЛЬКО через `next/dynamic(..., { ssr: false })` (см. app/take/map/page.tsx),
// иначе `next build` падает: react-leaflet трогает `window`/`document` на модульном
// уровне, которых нет при серверном рендере.
import { useEffect } from "react";
import L from "leaflet";
import "leaflet/dist/leaflet.css";
import { MapContainer, Marker, Popup, TileLayer, useMap } from "react-leaflet";
import type { MapProject } from "@/lib/types";
import { formatAmount } from "@/lib/map-format";

// Leaflet's default marker icon references image paths that bundlers rewrite/break;
// pointing at the CDN copy of the same package version is the standard fix (the app
// already depends on the OSM tile CDN for the map itself, so this adds no new trust
// boundary).
const markerIcon = L.icon({
  iconUrl: "https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon.png",
  iconRetinaUrl: "https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon-2x.png",
  shadowUrl: "https://unpkg.com/leaflet@1.9.4/dist/images/marker-shadow.png",
  iconSize: [25, 41],
  iconAnchor: [12, 41],
  popupAnchor: [1, -34],
  shadowSize: [41, 41],
});

const KAZAKHSTAN_CENTER: [number, number] = [48.0196, 66.9237];
const DEFAULT_ZOOM = 5;

function FitOnFilterChange({ projects }: { projects: MapProject[] }) {
  const map = useMap();
  useEffect(() => {
    if (projects.length === 0) {
      map.setView(KAZAKHSTAN_CENTER, DEFAULT_ZOOM);
      return;
    }
    const bounds = L.latLngBounds(projects.map((p) => [Number(p.lat), Number(p.lng)] as [number, number]));
    map.fitBounds(bounds, { padding: [30, 30], maxZoom: 9 });
  }, [projects, map]);
  return null;
}

export function ProjectMap({
  projects,
  onSelect,
}: {
  projects: MapProject[];
  onSelect: (project: MapProject) => void;
}) {
  return (
    <MapContainer center={KAZAKHSTAN_CENTER} zoom={DEFAULT_ZOOM} className="map-canvas" scrollWheelZoom>
      <TileLayer
        attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
        url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
      />
      <FitOnFilterChange projects={projects} />
      {projects.map((project) => (
        <Marker
          key={project.id}
          position={[Number(project.lat), Number(project.lng)]}
          icon={markerIcon}
          eventHandlers={{ click: () => onSelect(project) }}
        >
          <Popup>
            <strong>{project.name}</strong>
            <br />
            {project.organization} · {formatAmount(project.amount)}
          </Popup>
        </Marker>
      ))}
    </MapContainer>
  );
}
