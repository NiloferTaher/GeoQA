import type { Feature, FeatureCollection, Geometry } from "geojson"
import type { Issue, ShapefileLayerInfo } from "../types"

export type DuplicateComparisonRow = {
  field: string
  left: string
  right: string
  differs: boolean
}

export type DuplicateComparison = {
  leftId: string
  rightId: string
  geometryType: string
  coordinateSummary: string
  exactGeometryEqual: boolean
  rows: DuplicateComparisonRow[]
}

export type RunQaSuggestionContext = {
  issues?: Issue[]
  selectedLayer?: string
  zipLayers?: ShapefileLayerInfo[]
  profile?: string
  geometryType?: string
  analysisFullLayer?: boolean
}

const duplicatePattern = /duplicate|same[_\s-]*geometry|same[_\s-]*location/i
const networkIssuePattern = /endpoint|node|network|connect|spatial_index|stale_spatial_index|isolated/i
const serviceLayerPattern = /service|lateral|meter|fitting|facility|customer|connection|hydrant|valve/i
const companionLayerPattern = /main|pipe|network|hps|dma|aio|boundary|asset/i

export function isDuplicateIssue(issue: Pick<Issue, "problem_name" | "description">): boolean {
  return duplicatePattern.test(`${issue.problem_name} ${issue.description ?? ""}`)
}

export function buildDuplicateComparison(
  issue: Issue,
  analyzed: FeatureCollection | null | undefined,
): DuplicateComparison | null {
  if (!isDuplicateIssue(issue) || !analyzed?.features.length) return null
  const leftFeature = findFeatureByIssueId(issue, analyzed) ?? findFeatureByGeometry(issue.geometry, analyzed)
  if (!leftFeature) return null
  const relatedIds = relatedFeatureIds(issue)
  const rightFeature =
    relatedIds.map((id) => findFeatureByValue(analyzed, id)).find(Boolean) ??
    findDuplicateGeometryFeature(analyzed, leftFeature) ??
    findFeatureByGeometry(issue.geometry, analyzed, leftFeature)
  if (!rightFeature) return null
  const leftProps = leftFeature.properties ?? {}
  const rightProps = rightFeature.properties ?? {}
  const fields = Array.from(new Set([...Object.keys(leftProps), ...Object.keys(rightProps)]))
    .filter((field) => !field.startsWith("_geoqa_"))
    .sort((left, right) => left.localeCompare(right))
    .slice(0, 12)
  const rows = fields.map((field) => {
    const left = displayValue(leftProps[field])
    const right = displayValue(rightProps[field])
    return { field, left, right, differs: left !== right }
  })
  return {
    leftId: featureLabel(leftFeature, analyzed.features.indexOf(leftFeature)),
    rightId: featureLabel(rightFeature, analyzed.features.indexOf(rightFeature)),
    geometryType: leftFeature.geometry?.type ?? rightFeature.geometry?.type ?? "Unknown",
    coordinateSummary: summarizeGeometry(leftFeature.geometry),
    exactGeometryEqual: geometryKey(leftFeature.geometry) === geometryKey(rightFeature.geometry),
    rows,
  }
}

export function getIssueInterpretation(issue: Issue, context: RunQaSuggestionContext = {}): string {
  const problem = issue.problem_name.toLowerCase()
  if (isDuplicateIssue(issue)) {
    return "Possible interpretation. GeoQA found matching coordinates. Compare row attributes before deleting anything."
  }
  if (problem.includes("missing_or_stale_spatial_index")) {
    return "Possible interpretation. This is a performance and delivery readiness finding, not proof that map coordinates are wrong."
  }
  if (problem.includes("gap") || problem.includes("overlap")) {
    return "Possible interpretation. Boundary features may not form a continuous coverage. Confirm against an authoritative source."
  }
  if (problem.includes("precision")) {
    return "Possible interpretation. Coordinates may be over precise or rounded for the intended delivery format."
  }
  if (networkIssuePattern.test(problem) && serviceLayerPattern.test(context.selectedLayer ?? "")) {
    return "Possible interpretation. Service or point asset layers may need the related mains or network layer for full context."
  }
  return "Possible interpretation. Review the selected layer and source attributes before changing production data."
}

export function getRunQaSuggestions(context: RunQaSuggestionContext): string[] {
  const suggestions = new Set<string>()
  const selectedLayer = context.selectedLayer ?? ""
  const zipLayerCount = context.zipLayers?.length ?? 0
  if (zipLayerCount > 1 && selectedLayer) {
    suggestions.add(`Validated selected layer ${selectedLayer} from ${zipLayerCount.toLocaleString()} detected Shapefile layers.`)
  }
  if (context.analysisFullLayer === false) {
    suggestions.add("Public demo mode checked a limited subset. Re-run locally for full layer coverage.")
  }
  if (
    serviceLayerPattern.test(selectedLayer) &&
    !context.zipLayers?.some((layer) => companionLayerPattern.test(`${layer.name} ${layer.path}`))
  ) {
    suggestions.add("For utility QA, load related mains, pipes, boundaries, or asset layers when judging connectivity findings.")
  }
  const issues = context.issues ?? []
  if (issues.some(isDuplicateIssue)) {
    suggestions.add("Duplicate geometry findings are row comparison work. Matching coordinates can still represent different assets.")
  }
  if (issues.some((issue) => issue.problem_name.toLowerCase().includes("missing_or_stale_spatial_index"))) {
    suggestions.add("Spatial index findings are operational. Build or refresh the index before large overlays or joins.")
  }
  if (issues.some((issue) => /gap|overlap/i.test(issue.problem_name))) {
    suggestions.add("Polygon gap and overlap findings need source authority review before edits.")
  }
  if (!suggestions.size) {
    suggestions.add("Review issue groups first, then inspect representative features on the map.")
  }
  return Array.from(suggestions)
}

function relatedFeatureIds(issue: Issue): string[] {
  const values: unknown[] = []
  const direct = issue as unknown as Record<string, unknown>
  const provenance = issue.provenance ?? {}
  ;[
    "duplicate_feature_id",
    "duplicate_feature_ids",
    "related_feature_id",
    "related_feature_ids",
    "counterpart_feature_id",
    "counterpart_feature_ids",
  ].forEach((key) => {
    values.push(direct[key])
    values.push(provenance[key])
  })
  return values.flatMap((value) => (Array.isArray(value) ? value : [value])).filter((value): value is string | number =>
    value !== undefined && value !== null && value !== "",
  ).map(String)
}

function findFeatureByIssueId(issue: Issue, collection: FeatureCollection): Feature<Geometry> | null {
  if (issue.feature_id === undefined || issue.feature_id === null) return null
  return findFeatureByValue(collection, issue.feature_id)
}

function findFeatureByValue(collection: FeatureCollection, value: unknown): Feature<Geometry> | null {
  const wanted = String(value)
  const match = collection.features.find((feature, index) => {
    const props = feature.properties ?? {}
    return [
      props._geoqa_sample_index,
      props._geoqa_original_index,
      props.id,
      props.ID,
      props.fid,
      props.FID,
      props.objectid,
      props.OBJECTID,
      index,
      index + 1,
    ].some((candidate) => candidate !== undefined && candidate !== null && String(candidate) === wanted)
  })
  return match?.geometry ? (match as Feature<Geometry>) : null
}

function findFeatureByGeometry(
  geometry: Geometry | null | undefined,
  collection: FeatureCollection,
  exclude?: Feature,
): Feature<Geometry> | null {
  if (!geometry) return null
  const key = geometryKey(geometry)
  const match = collection.features.find((feature) => feature !== exclude && feature.geometry && geometryKey(feature.geometry) === key)
  return match?.geometry ? (match as Feature<Geometry>) : null
}

function findDuplicateGeometryFeature(collection: FeatureCollection, source: Feature): Feature<Geometry> | null {
  if (!source.geometry) return null
  return findFeatureByGeometry(source.geometry, collection, source)
}

function featureLabel(feature: Feature, index: number): string {
  const props = feature.properties ?? {}
  const value =
    props._geoqa_original_index ?? props._geoqa_sample_index ?? props.id ?? props.ID ?? props.fid ?? props.FID ?? props.objectid ?? props.OBJECTID
  if (value !== undefined && value !== null) return String(value)
  return index >= 0 ? String(index) : "unknown"
}

function summarizeGeometry(geometry: Geometry | null | undefined): string {
  if (!geometry) return "No geometry attached."
  const coordinates = flattenPositions((geometry as Geometry & { coordinates?: unknown }).coordinates)
  if (!coordinates.length) return `${geometry.type} geometry. Coordinates are nested or unavailable.`
  if (geometry.type === "Point") return `Point at ${formatCoord(coordinates[0])}.`
  const lngs = coordinates.map(([lng]) => lng)
  const lats = coordinates.map(([, lat]) => lat)
  return `${geometry.type} with ${coordinates.length.toLocaleString()} coordinate positions. Bounds ${formatCoord([Math.min(...lngs), Math.min(...lats)])} to ${formatCoord([Math.max(...lngs), Math.max(...lats)])}.`
}

function flattenPositions(value: unknown): Array<[number, number]> {
  if (!Array.isArray(value)) return []
  if (Number.isFinite(value[0]) && Number.isFinite(value[1])) return [[Number(value[0]), Number(value[1])]]
  return value.flatMap(flattenPositions)
}

function formatCoord(position: [number, number]): string {
  return `${position[0].toFixed(6)}, ${position[1].toFixed(6)}`
}

function displayValue(value: unknown): string {
  if (value === undefined || value === null || value === "") return "blank"
  const text = typeof value === "object" ? JSON.stringify(value) : String(value)
  return text.length > 96 ? `${text.slice(0, 93)}...` : text
}

function geometryKey(geometry: Geometry | null | undefined): string {
  return geometry ? JSON.stringify(geometry) : ""
}
