import { memo, useEffect } from "react"
import L from "leaflet"
import { GeoJSON, MapContainer, Pane, TileLayer, useMap } from "react-leaflet"
import "leaflet/dist/leaflet.css"
import type { Feature, FeatureCollection, GeoJsonObject, Geometry } from "geojson"
import { boundsCenter, boundsSpan, featureBounds, isPointLikeBounds } from "../lib/geometry"
import { getAtlasBasemap, type BasemapKey } from "../config/basemaps"

type MapPanelProps = {
  raw?: FeatureCollection
  analyzed?: FeatureCollection | null
  issues?: FeatureCollection
  cleaned?: FeatureCollection | null
  bounds?: [number, number, number, number]
  mapPadding?: [number, number]
  mapMaxZoom?: number
  mapMinZoom?: number
  mapCenter?: [number, number]
  mapZoom?: number
  showRaw: boolean
  showAnalyzed?: boolean
  showIssues: boolean
  showCleaned: boolean
  selectedIssueId?: string | null
  focusFeature?: Feature<Geometry> | null
  onIssueSelect?: (feature: Feature<Geometry>) => void
  renderKey?: string
  lowCostPointRendering?: boolean
  mapMode?: "dataset" | "runQa"
  basemapKey?: BasemapKey
}

const canvasRenderer = L.canvas({ padding: 0.35 })

function fitMaxZoom(bounds: [number, number, number, number], mapMode: "dataset" | "runQa", configuredMaxZoom?: number) {
  if (configuredMaxZoom !== undefined) return configuredMaxZoom
  if (mapMode !== "runQa") return isPointLikeBounds(bounds) ? 12 : 12
  const span = boundsSpan(bounds)
  if (isPointLikeBounds(bounds) || span < 0.001) return 18
  if (span < 0.005) return 17
  if (span < 0.02) return 16
  if (span < 0.08) return 15
  if (span < 0.2) return 14
  if (span < 0.5) return 13
  return 12
}

function FitBounds({
  bounds,
  mapMode,
  padding,
  maxZoom,
  minZoom,
  center,
  zoom,
}: {
  bounds?: [number, number, number, number]
  mapMode: "dataset" | "runQa"
  padding?: [number, number]
  maxZoom?: number
  minZoom?: number
  center?: [number, number]
  zoom?: number
}) {
  const map = useMap()
  useEffect(() => {
    if (center && zoom !== undefined) {
      const setConfiguredView = () => {
        map.invalidateSize()
        map.setView(center, zoom)
      }
      requestAnimationFrame(setConfiguredView)
      const timer = window.setTimeout(setConfiguredView, 250)
      return () => window.clearTimeout(timer)
    }
    if (!bounds) return
    const fitted = L.latLngBounds([bounds[1], bounds[0]], [bounds[3], bounds[2]])
    if (fitted.isValid()) {
      const fit = () => {
        map.invalidateSize()
        map.fitBounds(fitted, {
          padding: padding ?? [32, 32],
          maxZoom: fitMaxZoom(bounds, mapMode, maxZoom),
        })
        if (minZoom !== undefined && map.getZoom() < minZoom) {
          map.setZoom(minZoom)
        }
      }
      requestAnimationFrame(fit)
      const timer = window.setTimeout(fit, 250)
      return () => window.clearTimeout(timer)
    }
  }, [bounds, center, map, mapMode, maxZoom, minZoom, padding, zoom])
  return null
}

function FocusIssue({ feature, mapMode }: { feature?: Feature<Geometry> | null; mapMode: "dataset" | "runQa" }) {
  const map = useMap()
  useEffect(() => {
    if (!feature) return
    const bounds = featureBounds(feature)
    const endpointPair = feature.properties?.endpoint_pair === true
    if (bounds && (isPointLikeBounds(bounds) || boundsSpan(bounds) < 0.002)) {
      map.flyTo(boundsCenter(bounds), endpointPair ? 18 : mapMode === "runQa" ? 15 : 14, { duration: 0.8 })
      return
    }
    if (bounds) {
      const fitted = L.latLngBounds([bounds[1], bounds[0]], [bounds[3], bounds[2]])
      if (fitted.isValid()) {
        map.flyToBounds(fitted.pad(endpointPair ? 1.2 : 0.2), {
          maxZoom: endpointPair ? 19 : mapMode === "runQa" ? 15 : 14,
          animate: true,
          duration: 0.8,
        })
      }
    }
  }, [feature, map, mapMode])
  return null
}

function datasetLayerStyle(feature?: Feature<Geometry>) {
  const type = feature?.geometry?.type ?? ""
  if (type.includes("Line")) {
    return { color: "#67e8f9", weight: 2, opacity: 0.78 }
  }
  if (type.includes("Polygon")) {
    return { color: "#38bdf8", fillColor: "#0ea5e9", fillOpacity: 0.18, weight: 1.2, opacity: 0.78 }
  }
  return { color: "#67e8f9", weight: 2, opacity: 0.8 }
}

function runQaRawStyleFactory(basemapKey: BasemapKey) {
  return (feature?: Feature<Geometry>) => {
  const type = feature?.geometry?.type ?? ""
    const lineColor = basemapKey === "light" ? "#37576d" : "#b7d7e8"
    const fillColor = basemapKey === "light" ? "#527b93" : "#b7d7e8"
  if (type.includes("Line")) {
      return { color: lineColor, weight: 1.6, opacity: basemapKey === "light" ? 0.74 : 0.58 }
  }
  if (type.includes("Polygon")) {
      return {
        color: lineColor,
        fillColor,
        fillOpacity: basemapKey === "light" ? 0.08 : 0.045,
        weight: 1.3,
        opacity: basemapKey === "light" ? 0.72 : 0.56,
      }
  }
    return { color: lineColor, weight: 1.5, opacity: basemapKey === "light" ? 0.74 : 0.58 }
  }
}

function runQaAnalyzedStyleFactory(basemapKey: BasemapKey) {
  return (feature?: Feature<Geometry>) => {
  const type = feature?.geometry?.type ?? ""
    const color = basemapKey === "light" ? "#047c93" : "#28c7df"
    const fillColor = basemapKey === "light" ? "#0891b2" : "#22d3ee"
  if (type.includes("Line")) {
      return { color, weight: 2.3, opacity: 0.96 }
  }
  if (type.includes("Polygon")) {
      return { color, fillColor, fillOpacity: basemapKey === "light" ? 0.12 : 0.055, weight: 1.9, opacity: 0.95 }
  }
    return { color, weight: 2, opacity: 0.96 }
  }
}

function cleanedStyle(feature?: Feature<Geometry>) {
  const type = feature?.geometry?.type ?? ""
  if (type.includes("Line")) {
    return { color: "#34d399", weight: 2.5, opacity: 0.88, dashArray: "4 4" }
  }
  return { color: "#34d399", fillColor: "#34d399", fillOpacity: 0.14, weight: 1.5, opacity: 0.88, dashArray: "4 4" }
}

function issueStyle(selectedIssueId?: string | null, lowCostPointRendering = false, mapMode: "dataset" | "runQa" = "dataset") {
  return (feature?: Feature<Geometry>) => {
  const severity = String(feature?.properties?.severity ?? "").toLowerCase()
  const color =
    severity === "high" || severity === "critical"
      ? "#fb7185"
      : mapMode === "runQa" && (severity === "low" || severity === "info")
        ? "#7dd3fc"
        : mapMode === "runQa"
          ? "#ffd21f"
          : "#facc15"
    const selected = feature?.properties?.issue_id === selectedIssueId
    const endpointPair = feature?.properties?.endpoint_pair === true
    const lowCost = lowCostPointRendering && feature?.geometry?.type?.includes("Point")
    const pointIssue = feature?.geometry?.type?.includes("Point")
    if (mapMode === "dataset") {
      return {
        color,
        fillColor: color,
        fillOpacity: endpointPair ? 0.08 : selected ? 0.54 : 0.32,
        weight: endpointPair ? (selected ? 6 : 4) : selected ? 6 : 3,
        opacity: selected ? 1 : 0.94,
        dashArray: endpointPair ? "4 4" : undefined,
        className: endpointPair ? "endpoint-gap-geometry" : selected ? "selected-issue-geometry" : "issue-geometry",
      }
    }
    return {
      color,
      fillColor: color,
      fillOpacity: pointIssue ? 0.05 : lowCost ? 0.1 : selected ? 0.18 : 0.08,
      weight: pointIssue ? (selected ? 4 : 3) : lowCost ? 2.2 : selected ? 6 : 3.4,
      opacity: selected ? 1 : 0.94,
      renderer: lowCost ? canvasRenderer : undefined,
      className: lowCost ? "performance-point-geometry" : selected ? "selected-issue-geometry" : "issue-geometry",
    }
  }
}

function focusStyle(feature?: Feature<Geometry>) {
  const severity = String(feature?.properties?.severity ?? "").toLowerCase()
  const color = severity === "high" || severity === "critical" ? "#fb7185" : "#ffd21f"
  const type = feature?.geometry?.type ?? ""
  if (type.includes("Polygon")) {
    return { color, fillColor: color, fillOpacity: 0.12, weight: 5, opacity: 1, dashArray: "5 5" }
  }
  return { color, fillColor: color, fillOpacity: 0.16, weight: 5, opacity: 1, dashArray: type.includes("Line") ? "5 5" : undefined }
}

function pointLayer(
  selectedIssueId?: string | null,
  lowCostPointRendering = false,
  mapMode: "dataset" | "runQa" = "dataset",
  basemapKey: BasemapKey = "dark",
) {
  return (feature: Feature<Geometry>, latlng: L.LatLng) => {
  const severity = String(feature.properties?.severity ?? "").toLowerCase()
  const analyzed = feature.properties?._geoqa_analyzed === true
  const color = severity
    ? severity === "high"
      ? "#fb7185"
      : mapMode === "runQa" && severity === "low"
        ? "#7dd3fc"
        : mapMode === "runQa"
          ? "#ffd21f"
          : "#facc15"
    : mapMode === "runQa" && analyzed
      ? basemapKey === "light" ? "#047c93" : "#28c7df"
      : mapMode === "runQa"
        ? basemapKey === "light" ? "#37576d" : "#b7d7e8"
        : "#67e8f9"
    const selected = feature.properties?.issue_id === selectedIssueId
    const endpointPair = feature.properties?.endpoint_pair === true
    const lowCost = lowCostPointRendering && !selected
    if (mapMode === "dataset") {
      return L.circleMarker(latlng, {
        radius: endpointPair ? (selected ? 8 : 7) : selected ? 10 : severity ? 7 : 5,
        color,
        fillColor: color,
        fillOpacity: endpointPair ? 0.95 : selected ? 0.94 : severity ? 0.78 : 0.58,
        weight: endpointPair ? 2.5 : selected ? 3 : 1,
        className: endpointPair ? "endpoint-marker-geometry" : selected ? "selected-issue-geometry" : "issue-geometry",
      })
    }
  return L.circleMarker(latlng, {
      renderer: lowCost ? canvasRenderer : undefined,
      radius: lowCost ? (severity ? 8 : analyzed ? 6 : 4) : selected ? 11 : severity ? 9 : analyzed ? 6 : 4,
    color,
    fillColor: color,
      fillOpacity: severity ? 0.06 : analyzed ? 0.1 : basemapKey === "light" ? 0.08 : 0.04,
      weight: severity ? (selected ? 4 : 3) : analyzed ? 2 : 1.75,
      interactive: !lowCost || Boolean(severity),
      className: lowCost ? "performance-point-geometry" : selected ? "selected-issue-geometry" : "issue-geometry",
  })
}
}

function MapPanel({
  raw,
  analyzed,
  issues,
  cleaned,
  bounds,
  mapPadding,
  mapMaxZoom,
  mapMinZoom,
  mapCenter,
  mapZoom,
  showRaw,
  showAnalyzed = true,
  showIssues,
  showCleaned,
  selectedIssueId,
  focusFeature,
  onIssueSelect,
  renderKey = "map",
  lowCostPointRendering = false,
  mapMode = "dataset",
  basemapKey = "dark",
}: MapPanelProps) {
  const atlasBasemap = getAtlasBasemap(basemapKey)
  return (
    <div className="map-shell">
      <MapContainer className="map" center={[39.5, -98.35]} zoom={4} maxZoom={20} scrollWheelZoom preferCanvas>
        <TileLayer
          attribution={atlasBasemap.attribution}
          url={atlasBasemap.tileUrl}
          className="readable-basemap"
          maxZoom={20}
          maxNativeZoom={18}
        />
        <FitBounds
          bounds={bounds}
          mapMode={mapMode}
          padding={mapPadding}
          maxZoom={mapMaxZoom}
          minZoom={mapMinZoom}
          center={mapCenter}
          zoom={mapZoom}
        />
        <FocusIssue feature={focusFeature} mapMode={mapMode} />
        {atlasBasemap.labelTileUrl ? (
          <Pane name="map-labels" style={{ zIndex: 500, pointerEvents: "none" }}>
            <TileLayer
              attribution=""
              url={atlasBasemap.labelTileUrl}
              className="readable-map-labels"
              maxZoom={20}
              maxNativeZoom={18}
              opacity={1}
            />
          </Pane>
        ) : null}
        {raw && showRaw ? (
          <Pane name={`${mapMode}-raw-layer`} style={{ zIndex: mapMode === "runQa" ? 440 : 560 }}>
            <GeoJSON
              key={`raw-${renderKey}-${showRaw}`}
              data={raw as GeoJsonObject}
              style={mapMode === "runQa" ? runQaRawStyleFactory(atlasBasemap.key) : datasetLayerStyle}
              pointToLayer={pointLayer(undefined, lowCostPointRendering, mapMode, atlasBasemap.key)}
            />
          </Pane>
        ) : null}
        {cleaned && showCleaned ? (
          <Pane name={`${mapMode}-cleaned-layer`} style={{ zIndex: 610 }}>
            <GeoJSON
              key={`cleaned-${renderKey}-${showCleaned}`}
              data={cleaned as GeoJsonObject}
              style={cleanedStyle}
              pointToLayer={pointLayer(undefined, lowCostPointRendering, mapMode, atlasBasemap.key)}
            />
          </Pane>
        ) : null}
        {analyzed && showAnalyzed ? (
          <Pane name="runqa-analyzed-layer" style={{ zIndex: 640 }}>
            <GeoJSON
              key={`analyzed-${renderKey}-${analyzed.features.length}`}
              data={analyzed as GeoJsonObject}
              style={runQaAnalyzedStyleFactory(atlasBasemap.key)}
              pointToLayer={pointLayer(undefined, lowCostPointRendering, "runQa", atlasBasemap.key)}
            />
          </Pane>
        ) : null}
        {issues && showIssues ? (
          <Pane name={`${mapMode}-issue-layer`} style={{ zIndex: 760 }}>
            <GeoJSON
              key={`issues-${renderKey}-${showIssues}-${selectedIssueId ?? "none"}`}
              data={issues as GeoJsonObject}
              style={issueStyle(selectedIssueId, lowCostPointRendering, mapMode)}
              pointToLayer={pointLayer(selectedIssueId, lowCostPointRendering, mapMode, atlasBasemap.key)}
              onEachFeature={(feature, layer) => {
                layer.on("click", () => onIssueSelect?.(feature as Feature<Geometry>))
              }}
            />
          </Pane>
        ) : null}
        {focusFeature && showIssues ? (
          <Pane name={`${mapMode}-focus-layer`} style={{ zIndex: 820 }}>
            <GeoJSON
              key={`focus-${renderKey}-${selectedIssueId ?? "none"}-${String(focusFeature.properties?._focus_tick ?? "")}`}
              data={focusFeature as GeoJsonObject}
              style={focusStyle}
              pointToLayer={pointLayer(selectedIssueId, lowCostPointRendering, mapMode, atlasBasemap.key)}
            />
          </Pane>
        ) : null}
      </MapContainer>
    </div>
  )
}

export default memo(MapPanel)
