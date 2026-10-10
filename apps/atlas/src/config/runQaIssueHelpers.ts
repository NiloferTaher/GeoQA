import type { Feature, FeatureCollection, Geometry } from "geojson"
import type { Issue } from "../types"
import { featureBounds } from "../lib/geometry"
import { isOperationalIssue } from "../lib/issues"

export const LAYER_LEVEL_ISSUE_TYPES = new Set([
  "missing_or_stale_spatial_index",
  "crs_metadata_missing_or_ambiguous",
  "invalid_spatial_reference",
])

export function getIssueCountText(issueCount: number): string {
  if (issueCount === 0) return "No issues found in the GeoQA-analyzed features."
  const noun = issueCount === 1 ? "issue" : "issues"
  return `${issueCount.toLocaleString()} ${noun} found in the GeoQA-analyzed features.`
}

export function getSampledExecutionStatus(executionStatus: string, fullLayerValidated?: boolean): string {
  if (fullLayerValidated === false) return "demo sample"
  return executionStatus
}

export function hasUsableGeometry(feature?: Feature | null): feature is Feature<Geometry> {
  return Boolean(feature?.geometry && featureBounds(feature as Feature<Geometry>))
}

export function buildIssueOverlayWithFallback(
  overlay: FeatureCollection | null | undefined,
  issues: Issue[],
  analyzed: FeatureCollection | null | undefined,
): FeatureCollection {
  const overlayFeatures = overlay?.features ?? []
  const output: Feature[] = []
  const used = new Set<string>()

  overlayFeatures.forEach((feature, index) => {
    if (!hasUsableGeometry(feature)) return
    const issueId = String(feature.properties?.issue_id ?? `overlay-${index}`)
    used.add(issueId)
    output.push(feature)
  })

  issues.forEach((issue, index) => {
    const issueId = String(issue.issue_id ?? `issue-${index}`)
    if (used.has(issueId)) return
    const directFeature = issue.geometry
      ? ({
          type: "Feature",
          properties: issueProperties(issue),
          geometry: issue.geometry,
        } satisfies Feature)
      : null
    if (hasUsableGeometry(directFeature)) {
      output.push(directFeature)
      return
    }
    const analyzedFeature = findAnalyzedFeatureForIssue(issue, analyzed)
    if (!hasUsableGeometry(analyzedFeature)) return
    output.push({
      type: "Feature",
      properties: issueProperties(issue),
      geometry: analyzedFeature.geometry,
    })
  })

  return {
    type: "FeatureCollection",
    features: output,
  }
}

export function getIssueFocusFeature(
  issue: Issue,
  overlay: FeatureCollection | null | undefined,
  analyzed: FeatureCollection | null | undefined,
): Feature<Geometry> | null {
  const overlayFeature = overlay?.features.find((feature) => feature.properties?.issue_id === issue.issue_id)
  if (hasUsableGeometry(overlayFeature)) return cloneFeature(overlayFeature)
  if (issue.geometry) {
    const directFeature = {
      type: "Feature",
      properties: issueProperties(issue),
      geometry: issue.geometry,
    } satisfies Feature
    if (hasUsableGeometry(directFeature)) return cloneFeature(directFeature)
  }
  const analyzedFeature = findAnalyzedFeatureForIssue(issue, analyzed)
  return hasUsableGeometry(analyzedFeature) ? cloneFeature(analyzedFeature) : null
}

export function isLayerLevelIssue(issue?: Pick<Issue, "problem_name" | "feature_id"> | null) {
  if (!issue) return false
  const problemName = String(issue.problem_name ?? "")
  return LAYER_LEVEL_ISSUE_TYPES.has(problemName) || problemName.includes("metadata") || issue.feature_id === null || issue.feature_id === undefined
}

export function getIssueFocusKind(issue: Issue, overlay: FeatureCollection | null | undefined, analyzed: FeatureCollection | null | undefined) {
  if (isOperationalIssue(issue)) return "operational"
  if (getIssueFocusFeature(issue, overlay, analyzed)) return "feature"
  if (isLayerLevelIssue(issue) && analyzed?.features.length) return "layer"
  return "none"
}

export function findFirstIssueForProblem(issues: Issue[], problemName: string, overlay: FeatureCollection, analyzed: FeatureCollection | null | undefined) {
  return (
    issues.find((issue) => issue.problem_name === problemName && getIssueFocusFeature(issue, overlay, analyzed)) ??
    issues.find((issue) => issue.problem_name === problemName) ??
    null
  )
}

export function sanitizeFeatureCollectionForGeoQA(collection: FeatureCollection): FeatureCollection {
  return {
    ...collection,
    features: collection.features.map((feature) => ({
      ...feature,
      properties: { ...(feature.properties ?? {}) },
      geometry: isValidGeoJsonGeometry(feature.geometry) ? cloneGeometry(feature.geometry) : null,
    })) as Feature<Geometry | null>[],
  } as FeatureCollection
}

export function isValidGeoJsonGeometry(geometry: Geometry | null): geometry is Geometry {
  if (!geometry) return false
  if (geometry.type === "GeometryCollection") {
    return geometry.geometries.length > 0 && geometry.geometries.every((child) => isValidGeoJsonGeometry(child))
  }
  return hasValidCoordinatePair((geometry as Geometry & { coordinates?: unknown }).coordinates) &&
    hasOnlyValidCoordinateValues((geometry as Geometry & { coordinates?: unknown }).coordinates)
}

function hasValidCoordinatePair(value: unknown): boolean {
  if (!Array.isArray(value)) return false
  if (Number.isFinite(value[0]) && Number.isFinite(value[1])) return true
  return value.some((child) => hasValidCoordinatePair(child))
}

function hasOnlyValidCoordinateValues(value: unknown): boolean {
  if (!Array.isArray(value)) return false
  if (value.length >= 2 && !Array.isArray(value[0])) {
    return Number.isFinite(value[0]) && Number.isFinite(value[1])
  }
  return value.every((child) => hasOnlyValidCoordinateValues(child))
}

function findAnalyzedFeatureForIssue(issue: Issue, analyzed: FeatureCollection | null | undefined): Feature | null {
  if (!analyzed) return null
  return analyzed.features.find((feature, index) => issueMatchesFeature(issue, feature, index)) ?? null
}

function issueMatchesFeature(issue: Issue, feature: Feature, index: number): boolean {
  const props = feature.properties ?? {}
  const candidates = [
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
  ].filter((value) => value !== undefined && value !== null)
  return candidates.some((value) => String(value) === String(issue.feature_id))
}

function issueProperties(issue: Issue) {
  return {
    issue_id: issue.issue_id,
    problem_name: issue.problem_name,
    severity: issue.severity,
    feature_id: issue.feature_id,
    description: issue.description,
    solution_hint: issue.solution_hint,
    issue_class: issue.issue_class,
  }
}

function cloneFeature(feature: Feature): Feature<Geometry> {
  return {
    ...feature,
    properties: { ...(feature.properties ?? {}) },
    geometry: cloneGeometry(feature.geometry) as Geometry,
  }
}

function cloneGeometry(geometry: Geometry | null): Geometry | null {
  return geometry ? JSON.parse(JSON.stringify(geometry)) : null
}
