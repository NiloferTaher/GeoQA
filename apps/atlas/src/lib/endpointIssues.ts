import type { Feature, FeatureCollection, Geometry, LineString, Point } from "geojson"
import type { Issue } from "../types"

const endpointProblemPattern = /near_miss_endpoint|unsnapped_endpoint|line_dangle|isolated_network_segment|endpoint/i

export function isEndpointIssue(issue?: Pick<Issue, "problem_name"> | null): boolean {
  return endpointProblemPattern.test(String(issue?.problem_name ?? ""))
}

export function hasEndpointPair(issue?: Issue | null): issue is Issue & {
  endpoint_a: [number, number]
  endpoint_b: [number, number]
} {
  return Boolean(isValidPosition(issue?.endpoint_a) && isValidPosition(issue?.endpoint_b))
}

export function buildEndpointIssueOverlay(baseOverlay: FeatureCollection | undefined, issues: Issue[]): FeatureCollection | undefined {
  if (!baseOverlay) return undefined
  const endpointIssueIds = new Set(issues.filter(hasEndpointPair).map((issue) => issue.issue_id).filter(Boolean))
  const baseFeatures = (baseOverlay.features as Feature<Geometry>[]).filter(
    (feature) => !endpointIssueIds.has(String(feature.properties?.issue_id ?? "")),
  )
  const endpointFeatures = issues.flatMap(endpointIssueFeatures)
  return {
    type: "FeatureCollection",
    features: [...baseFeatures, ...endpointFeatures],
  }
}

export function endpointIssueFocusFeature(issue: Issue): Feature<LineString> | null {
  if (!hasEndpointPair(issue)) return null
  return {
    type: "Feature",
    properties: endpointProperties(issue, "gap"),
    geometry: {
      type: "LineString",
      coordinates: [issue.endpoint_a, issue.endpoint_b],
    },
  }
}

export function endpointIssueFeatures(issue: Issue): Feature<Geometry>[] {
  if (!hasEndpointPair(issue)) return []
  const features: Feature<Geometry>[] = [
    {
      type: "Feature",
      properties: endpointProperties(issue, "a"),
      geometry: { type: "Point", coordinates: issue.endpoint_a } satisfies Point,
    },
    {
      type: "Feature",
      properties: endpointProperties(issue, "b"),
      geometry: { type: "Point", coordinates: issue.endpoint_b } satisfies Point,
    },
  ]
  const focusFeature = endpointIssueFocusFeature(issue)
  if (focusFeature) features.push(focusFeature)
  return features
}

export function endpointIssueDetails(issue: Issue): string[] {
  if (!isEndpointIssue(issue)) return []
  const rows: string[] = []
  const related = issue.related_feature_id ?? issue.provenance?.related_feature_id
  if (related !== undefined && related !== null) rows.push(`Feature ${issue.feature_id ?? "unknown"} near feature ${related}`)
  if (typeof issue.distance === "number") rows.push(`Gap distance ${formatDistance(issue.distance, issue.distance_units)}`)
  if (typeof issue.tolerance === "number") rows.push(`Tolerance ${formatDistance(issue.tolerance, issue.distance_units)}`)
  if (!hasEndpointPair(issue)) rows.push("Endpoint coordinates were not available in this report.")
  return rows
}

function endpointProperties(issue: Issue, role: "a" | "b" | "gap") {
  return {
    issue_id: issue.issue_id,
    problem_name: issue.problem_name,
    severity: issue.severity,
    feature_id: issue.feature_id,
    related_feature_id: issue.related_feature_id,
    distance: issue.distance,
    tolerance: issue.tolerance,
    label: "Near-miss endpoint gap",
    endpoint_role: role,
    endpoint_pair: true,
  }
}

function isValidPosition(value: unknown): value is [number, number] {
  return Array.isArray(value) && Number.isFinite(value[0]) && Number.isFinite(value[1])
}

function formatDistance(value: number, units?: string | null): string {
  if (units === "meters") {
    if (value >= 1) return `${value.toFixed(2)} m`
    return `${value.toFixed(3)} m`
  }
  if (value >= 1) return `${value.toFixed(2)} source units`
  return `${value.toFixed(3)} source units`
}
