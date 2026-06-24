import type { Feature, Geometry, Position } from "geojson"

export type BoundsTuple = [number, number, number, number]

type Accumulator = {
  minLng: number
  minLat: number
  maxLng: number
  maxLat: number
  found: boolean
}

function visitPosition(position: Position, bounds: Accumulator) {
  const [lng, lat] = position
  if (typeof lng !== "number" || typeof lat !== "number") return
  bounds.minLng = Math.min(bounds.minLng, lng)
  bounds.minLat = Math.min(bounds.minLat, lat)
  bounds.maxLng = Math.max(bounds.maxLng, lng)
  bounds.maxLat = Math.max(bounds.maxLat, lat)
  bounds.found = true
}

function visitPositions(value: unknown, bounds: Accumulator) {
  if (!Array.isArray(value)) return
  const maybePosition = value as unknown[]
  if (typeof maybePosition[0] === "number" && typeof maybePosition[1] === "number") {
    visitPosition(maybePosition as Position, bounds)
    return
  }
  for (const child of value) {
    visitPositions(child, bounds)
  }
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

export function boundsCenter(bounds: BoundsTuple): [number, number] {
  return [(bounds[1] + bounds[3]) / 2, (bounds[0] + bounds[2]) / 2]
}

export function isPointLikeBounds(bounds: BoundsTuple) {
  return Math.abs(bounds[0] - bounds[2]) < 0.000001 && Math.abs(bounds[1] - bounds[3]) < 0.000001
}

export function boundsSpan(bounds: BoundsTuple) {
  return Math.max(Math.abs(bounds[0] - bounds[2]), Math.abs(bounds[1] - bounds[3]))
}
