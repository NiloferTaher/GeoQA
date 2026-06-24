import type { FeatureCollection } from "geojson"

export type Dataset = {
  id: string
  name: string
  short_name: string
  description: string
  feature_count: number
  geometry_type: string
  profile: string
  issue_count: number
  has_cleaned_layer?: boolean
  cleaned_geojson?: string
  geojson?: string
  report?: string
  command: string
  github_url: string
  source_label: string
  source_url: string
  bounds: [number, number, number, number]
  summary?: ReportSummary
}

export type DatasetListResponse = {
  datasets: Dataset[]
  stats?: {
    datasets: number
    checks: number
    issues: number
  }
}

export type ReportSummary = {
  total_issues?: number
  issue_count?: number
  actionable?: number
  informational?: number
  actionable_ratio?: number
  top_issues?: Array<{ problem_name: string; count: number; percent: number }>
  severity_distribution?: Array<{ name: string; count: number; percent: number }>
  by_problem?: Record<string, number>
}

export type Report = {
  dataset_id?: string
  issue_count: number
  summary: ReportSummary
  issues: Issue[]
}

export type Issue = {
  issue_id?: string
  problem_name: string
  severity: string
  description: string
  solution_hint?: string
  feature_id?: string | number | null
  priority_score?: number
}

export type IssuesResponse = FeatureCollection & {
  issues: Issue[]
}
