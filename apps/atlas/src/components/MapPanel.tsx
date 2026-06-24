import { useEffect } from "react"
import L from "leaflet"
import { GeoJSON, MapContainer, TileLayer, useMap } from "react-leaflet"
import type { Feature, FeatureCollection, GeoJsonObject, Geometry } from "geojson"
import { boundsCenter, boundsSpan, featureBounds, isPointLikeBounds } from "../lib/geometry"

type MapPanelProps = {
  raw?: FeatureCollection
  issues?: FeatureCollection
  cleaned?: FeatureCollection | null
  bounds?: [number, number, number, number]
  showRaw: boolean
  showIssues: boolean
  showCleaned: boolean
  selectedIssueId?: string | null
  focusFeature?: Feature<Geometry> | null
  onIssueSelect?: (feature: Feature<Geometry>) => void
}

function FitBounds({ bounds }: { bounds?: [number, number, number, number] }) {
  const map = useMap()
  useEffect(() => {
    if (!bounds) return
    const fitted = L.latLngBounds([bounds[1], bounds[0]], [bounds[3], bounds[2]])
    if (fitted.isValid()) {
      map.fitBounds(fitted, { padding: [24, 24], maxZoom: 12 })
    }
  }, [bounds, map])
  return null
}

function FocusIssue({ feature }: { feature?: Feature<Geometry> | null }) {
  const map = useMap()
  useEffect(() => {
    if (!feature) return
    const bounds = featureBounds(feature)
    if (bounds && (isPointLikeBounds(bounds) || boundsSpan(bounds) < 0.002)) {
      map.flyTo(boundsCenter(bounds), 18, { duration: 0.8 })
      return
    }
    if (bounds) {
      const fitted = L.latLngBounds([bounds[1], bounds[0]], [bounds[3], bounds[2]])
      if (fitted.isValid()) {
        map.flyToBounds(fitted.pad(0.2), { maxZoom: 17, animate: true, duration: 0.8 })
      }
    }
  }, [feature, map])
  return null
}

function layerStyle(feature?: Feature<Geometry>) {
  const type = feature?.geometry?.type ?? ""
  if (type.includes("Line")) {
    return { color: "#67e8f9", weight: 2, opacity: 0.78 }
  }
  if (type.includes("Polygon")) {
    return { color: "#38bdf8", fillColor: "#0ea5e9", fillOpacity: 0.18, weight: 1.2, opacity: 0.78 }
  }
  return { color: "#67e8f9", weight: 2, opacity: 0.8 }
}

function cleanedStyle(feature?: Feature<Geometry>) {
  const type = feature?.geometry?.type ?? ""
  if (type.includes("Line")) {
    return { color: "#34d399", weight: 2.5, opacity: 0.88, dashArray: "4 4" }
  }
  return { color: "#34d399", fillColor: "#34d399", fillOpacity: 0.14, weight: 1.5, opacity: 0.88, dashArray: "4 4" }
}

function issueStyle(selectedIssueId?: string | null) {
  return (feature?: Feature<Geometry>) => {
  const severity = String(feature?.properties?.severity ?? "").toLowerCase()
  const color = severity === "high" || severity === "critical" ? "#fb7185" : "#facc15"
    const selected = feature?.properties?.issue_id === selectedIssueId
    return {
      color,
      fillColor: color,
      fillOpacity: selected ? 0.54 : 0.32,
      weight: selected ? 6 : 3,
      opacity: selected ? 1 : 0.94,
      className: selected ? "selected-issue-geometry" : "issue-geometry",
    }
  }
}

function pointLayer(selectedIssueId?: string | null) {
  return (feature: Feature<Geometry>, latlng: L.LatLng) => {
  const severity = String(feature.properties?.severity ?? "").toLowerCase()
  const color = severity ? (severity === "high" ? "#fb7185" : "#facc15") : "#67e8f9"
    const selected = feature.properties?.issue_id === selectedIssueId
  return L.circleMarker(latlng, {
      radius: selected ? 10 : severity ? 7 : 5,
    color,
    fillColor: color,
      fillOpacity: selected ? 0.94 : severity ? 0.78 : 0.58,
      weight: selected ? 3 : 1,
      className: selected ? "selected-issue-geometry" : "issue-geometry",
  })
}
}

export default function MapPanel({
  raw,
  issues,
  cleaned,
  bounds,
  showRaw,
  showIssues,
  showCleaned,
  selectedIssueId,
  focusFeature,
  onIssueSelect,
}: MapPanelProps) {
  return (
    <div className="map-shell">
      <MapContainer className="map" center={[39.5, -98.35]} zoom={4} maxZoom={20} scrollWheelZoom>
        <TileLayer
          attribution='&copy; OpenStreetMap contributors &copy; CARTO'
          url="https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png"
          maxZoom={20}
          maxNativeZoom={18}
        />
        <FitBounds bounds={bounds} />
        <FocusIssue feature={focusFeature} />
        {raw && showRaw ? (
          <GeoJSON key={`raw-${showRaw}`} data={raw as GeoJsonObject} style={layerStyle} pointToLayer={pointLayer()} />
        ) : null}
        {cleaned && showCleaned ? (
          <GeoJSON key={`cleaned-${showCleaned}`} data={cleaned as GeoJsonObject} style={cleanedStyle} pointToLayer={pointLayer()} />
        ) : null}
        {issues && showIssues ? (
          <GeoJSON
            key={`issues-${showIssues}-${selectedIssueId ?? "none"}`}
            data={issues as GeoJsonObject}
            style={issueStyle(selectedIssueId)}
            pointToLayer={pointLayer(selectedIssueId)}
            onEachFeature={(feature, layer) => {
              layer.on("click", () => onIssueSelect?.(feature as Feature<Geometry>))
            }}
          />
        ) : null}
      </MapContainer>
    </div>
  )
}
