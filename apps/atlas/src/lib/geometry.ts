import type { Feature, FeatureCollection, Geometry, Position } from "geojson"

export type BoundsTuple = [number, number, number, number]

type Accumulator = {
  minLng: number
  minLat: number
  maxLng: number
  maxLat: number
  found: boolean
}

type PositionAccumulator = {
  lngs: number[]
  lats: number[]
}

function isValidLngLat(lng: number, lat: number) {
  return Number.isFinite(lng) && Number.isFinite(lat) && lng >= -180 && lng <= 180 && lat >= -90 && lat <= 90
}

function visitPosition(position: Position, bounds: Accumulator) {
  const [lng, lat] = position
  if (!isValidLngLat(lng, lat)) return
  bounds.minLng = Math.min(bounds.minLng, lng)
  bounds.minLat = Math.min(bounds.minLat, lat)
  bounds.maxLng = Math.max(bounds.maxLng, lng)
  bounds.maxLat = Math.max(bounds.maxLat, lat)
  bounds.found = true
}

function collectPosition(position: Position, bounds: PositionAccumulator) {
  const [lng, lat] = position
  if (!isValidLngLat(lng, lat)) return
  bounds.lngs.push(lng)
  bounds.lats.push(lat)
}

function visitPositions(value: unknown, bounds: Accumulator) {
  if (!Array.isArray(value)) return
  const maybePosition = value as unknown[]
  if (Number.isFinite(maybePosition[0]) && Number.isFinite(maybePosition[1])) {
    visitPosition(maybePosition as Position, bounds)
    return
  }
  for (const child of value) {
    visitPositions(child, bounds)
  }
}

function collectPositions(value: unknown, bounds: PositionAccumulator) {
  if (!Array.isArray(value)) return
  const maybePosition = value as unknown[]
  if (Number.isFinite(maybePosition[0]) && Number.isFinite(maybePosition[1])) {
    collectPosition(maybePosition as Position, bounds)
    return
  }
  for (const child of value) {
    collectPositions(child, bounds)
  }
}

function percentile(values: number[], quantile: number) {
  if (!values.length) return null
  const sorted = [...values].sort((left, right) => left - right)
  const index = Math.min(sorted.length - 1, Math.max(0, Math.round((sorted.length - 1) * quantile)))
  return sorted[index]
}

export function geometryBounds(geometry?: Geometry | null): BoundsTuple | null {
  if (!geometry) return null
  const bounds: Accumulator = {
    minLng: Number.POSITIVE_INFINITY,
    minLat: Number.POSITIVE_INFINITY,
    maxLng: Number.NEGATIVE_INFINITY,
    maxLat: Number.NEGATIVE_INFINITY,
    found: false,
  }

  if (geometry.type === "GeometryCollection") {
    for (const child of geometry.geometries) {
      const childBounds = geometryBounds(child)
      if (!childBounds) continue
      visitPosition([childBounds[0], childBounds[1]], bounds)
      visitPosition([childBounds[2], childBounds[3]], bounds)
    }
  } else {
    visitPositions(geometry.coordinates, bounds)
  }

  if (!bounds.found) return null
  return [bounds.minLng, bounds.minLat, bounds.maxLng, bounds.maxLat]
}

export function featureBounds(feature?: Feature<Geometry> | null): BoundsTuple | null {
  return geometryBounds(feature?.geometry)
}

export function collectionBounds(collection?: FeatureCollection | null, robust = false): BoundsTuple | null {
  if (!collection?.features?.length) return null
  if (robust) {
    const positions: PositionAccumulator = { lngs: [], lats: [] }
    for (const feature of collection.features) {
      const geometry = feature.geometry as Geometry | null | undefined
      if (!geometry) continue
      if (geometry.type === "GeometryCollection") {
        for (const child of geometry.geometries) {
          const childBounds = collectionBounds({ type: "FeatureCollection", features: [{ type: "Feature", properties: {}, geometry: child }] }, true)
          if (!childBounds) continue
          positions.lngs.push(childBounds[0], childBounds[2])
          positions.lats.push(childBounds[1], childBounds[3])
        }
      } else {
        collectPositions(geometry.coordinates, positions)
      }
    }
    if (!positions.lngs.length || !positions.lats.length) return null
    if (positions.lngs.length >= 30) {
      const minLng = percentile(positions.lngs, 0.02)
      const minLat = percentile(positions.lats, 0.02)
      const maxLng = percentile(positions.lngs, 0.98)
      const maxLat = percentile(positions.lats, 0.98)
      if (minLng !== null && minLat !== null && maxLng !== null && maxLat !== null && minLng <= maxLng && minLat <= maxLat) {
        return [minLng, minLat, maxLng, maxLat]
      }
    }
    return [
      Math.min(...positions.lngs),
      Math.min(...positions.lats),
      Math.max(...positions.lngs),
      Math.max(...positions.lats),
    ]
  }

  const bounds: BoundsTuple[] = []
  for (const feature of collection.features) {
    const current = featureBounds(feature as Feature<Geometry>)
    if (current) bounds.push(current)
  }
  return mergeBounds(bounds)
}

export function mergeBounds(boundsList: Array<BoundsTuple | null | undefined>): BoundsTuple | null {
  const valid = boundsList.filter(Boolean) as BoundsTuple[]
  if (!valid.length) return null
  return [
    Math.min(...valid.map((bounds) => bounds[0])),
    Math.min(...valid.map((bounds) => bounds[1])),
    Math.max(...valid.map((bounds) => bounds[2])),
    Math.max(...valid.map((bounds) => bounds[3])),
  ]
}

export function boundsCenter(bounds: BoundsTuple): [number, number] {
  return [(bounds[1] + bounds[3]) / 2, (bounds[0] + bounds[2]) / 2]
}

export function isPointLikeBounds(bounds: BoundsTuple) {
  return Math.abs(bounds[0] - bounds[2]) < 0.000001 && Math.abs(bounds[1] - bounds[3]) < 0.000001
}

export function boundsSpan(bounds: BoundsTuple) {
  return Math.max(Math.abs(bounds[0] - bounds[2]), Math.abs(bounds[1] - bounds[3]))
}
