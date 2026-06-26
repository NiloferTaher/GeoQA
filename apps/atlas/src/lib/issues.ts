import type { Feature, Geometry } from "geojson"
import type { Issue } from "../types"

export const OPERATIONAL_ISSUE_TYPES = new Set([
  "validation_runtime_error",
  "runtime_limit_exceeded",
  "thermal_limit_exceeded",
  "budget_limited",
])

export const NON_VISUAL_CLEANED_ISSUE_TYPES = new Set([
  "coordinate_precision_not_fit_for_use",
  "missing_or_stale_spatial_index",
  "crs_metadata_missing_or_ambiguous",
  "invalid_spatial_reference",
  "validation_runtime_error",
  "runtime_limit_exceeded",
  "thermal_limit_exceeded",
  "budget_limited",
])

export type IssueExample = {
  representative: Issue
  issueCount: number
  counterpartFeatures: Array<string | number>
}

export function isOperationalIssue(issue?: Pick<Issue, "problem_name"> | null) {
  return OPERATIONAL_ISSUE_TYPES.has(String(issue?.problem_name ?? ""))
}

export function isNonVisualCleanedIssue(issue?: Pick<Issue, "problem_name"> | null) {
  const problemName = String(issue?.problem_name ?? "")
  return NON_VISUAL_CLEANED_ISSUE_TYPES.has(problemName) || problemName.includes("metadata")
}

export function isOperationalIssueFeature(feature?: Feature<Geometry> | null) {
  return OPERATIONAL_ISSUE_TYPES.has(String(feature?.properties?.problem_name ?? ""))
}

export function featureIssuesOnly(issues: Issue[]) {
  return issues.filter((issue) => !isOperationalIssue(issue))
}

export function featureIssueFeaturesOnly(features: Feature<Geometry>[]) {
  return features.filter((feature) => !isOperationalIssueFeature(feature))
}

export function groupIssueExamples(issues: Issue[]): IssueExample[] {
  const grouped = new Map<string, IssueExample>()
  for (const issue of issues) {
    const key = issueExampleKey(issue)
    const current = grouped.get(key)
    if (!current) {
      grouped.set(key, {
        representative: issue,
        issueCount: 1,
        counterpartFeatures: extractCounterpartFeatures(issue),
      })
      continue
    }
    current.issueCount += 1
    current.counterpartFeatures = uniqueValues([...current.counterpartFeatures, ...extractCounterpartFeatures(issue)])
  }
  return Array.from(grouped.values())
}

function issueExampleKey(issue: Issue) {
  const featureId = issue.feature_id ?? "layer"
  return `${issue.problem_name}|${featureId}`
}

function extractCounterpartFeatures(issue: Issue): Array<string | number> {
  const issueRecord = issue as Record<string, unknown>
  const provenance = issue.provenance ?? {}
  const candidates = [
    issueRecord.counterpart_feature_id,
    issueRecord.counterpart_feature_ids,
    issueRecord.duplicate_feature_id,
    issueRecord.duplicate_feature_ids,
    issueRecord.related_feature_id,
    issueRecord.related_feature_ids,
    provenance.counterpart_feature_id,
    provenance.counterpart_feature_ids,
    provenance.duplicate_feature_id,
    provenance.duplicate_feature_ids,
    provenance.related_feature_id,
    provenance.related_feature_ids,
  ]
  return uniqueValues(candidates.flatMap(normalizeFeatureIdValue))
}

function normalizeFeatureIdValue(value: unknown): Array<string | number> {
  if (Array.isArray(value)) return value.flatMap(normalizeFeatureIdValue)
  if (typeof value === "string" || typeof value === "number") return [value]
  return []
}

function uniqueValues(values: Array<string | number>) {
  return Array.from(new Set(values))
}
