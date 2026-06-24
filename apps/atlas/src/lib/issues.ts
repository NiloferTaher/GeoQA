import type { Feature, Geometry } from "geojson"
import type { Issue } from "../types"

export const OPERATIONAL_ISSUE_TYPES = new Set(["validation_runtime_error"])

export function isOperationalIssue(issue?: Pick<Issue, "problem_name"> | null) {
  return OPERATIONAL_ISSUE_TYPES.has(String(issue?.problem_name ?? ""))
}

export function isOperationalIssueFeature(feature?: Feature<Geometry> | null) {
  return OPERATIONAL_ISSUE_TYPES.has(String(feature?.properties?.problem_name ?? ""))
}
