import type { FeatureCollection } from "geojson"
import type { Dataset, DatasetMapView } from "../types"
import { collectionBounds, mergeBounds, type BoundsTuple } from "./geometry"

type DatasetMapBoundsInput = {
  dataset: Pick<Dataset, "bounds" | "mapView" | "map_view">
  raw?: FeatureCollection | null
  issues?: FeatureCollection | null
  cleaned?: FeatureCollection | null
  showRaw?: boolean
  showIssues?: boolean
  showCleaned?: boolean
}

export type ResolvedDatasetMapView = {
  bounds?: BoundsTuple
  padding?: [number, number]
  maxZoom?: number
  minZoom?: number
  center?: [number, number]
  zoom?: number
}

function normalizeMapView(dataset: Pick<Dataset, "mapView" | "map_view">): DatasetMapView | undefined {
  return dataset.mapView ?? dataset.map_view
}

function mapViewFitTo(mapView?: DatasetMapView) {
  return mapView?.fitTo ?? mapView?.fit_to
}

export function resolveDatasetMapView({
  dataset,
  raw,
  issues,
  cleaned,
  showRaw = true,
  showIssues = true,
  showCleaned = false,
}: DatasetMapBoundsInput): ResolvedDatasetMapView {
  const mapView = normalizeMapView(dataset)
  const rawBounds = collectionBounds(raw, true)
  const issueBounds = collectionBounds(issues, true)
  const cleanedBounds = collectionBounds(cleaned, true)
  const combinedBounds = mergeBounds([showRaw ? rawBounds : null, showIssues ? issueBounds : null, showCleaned ? cleanedBounds : null])
  const fallbackBounds = rawBounds ?? issueBounds ?? cleanedBounds ?? dataset.bounds
  const fitTo = mapViewFitTo(mapView)
  const configuredBounds =
    fitTo === "raw"
      ? rawBounds
      : fitTo === "issues"
        ? issueBounds
        : fitTo === "cleaned"
          ? cleanedBounds
          : fitTo === "combined"
            ? combinedBounds
            : null

  return {
    bounds: configuredBounds ?? combinedBounds ?? fallbackBounds,
    padding: mapView?.padding,
    maxZoom: mapView?.maxZoom ?? mapView?.max_zoom,
    minZoom: mapView?.minZoom ?? mapView?.min_zoom,
    center: mapView?.center,
    zoom: mapView?.zoom,
  }
}
