import type { FeatureCollection, Geometry } from "geojson"

export type Dataset = {
  id: string
  name: string
  short_name: string
  description: string
  feature_count: number
  geometry_type: string
  profile: string
  issue_count: number
  hasCleanedLayer?: boolean
  cleanedLayerNote?: string
  cleanedGeoJsonPath?: string
  cleanedPreview?: CleanedPreview
  cleaned_preview?: CleanedPreview
  has_cleaned_layer?: boolean
  cleaned_layer_note?: string
  cleaned_geojson?: string
  geojson?: string
  report?: string
  command: string
  github_url: string
  source_label: string
  source_url: string
  bounds: [number, number, number, number]
  mapView?: DatasetMapView
  map_view?: DatasetMapView
  summary?: ReportSummary
}

export type DatasetMapView = {
  fitTo?: "raw" | "issues" | "combined" | "cleaned"
  fit_to?: "raw" | "issues" | "combined" | "cleaned"
  padding?: [number, number]
  maxZoom?: number
  max_zoom?: number
  minZoom?: number
  min_zoom?: number
  center?: [number, number]
  zoom?: number
}

export type CleanedPreview = {
  available: boolean
  meaningful: boolean
  path?: string
  supportedIssueTypes: string[]
  supported_issue_types?: string[]
  note: string
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
  related_feature_id?: string | number | null
  endpoint_a?: [number, number] | null
  endpoint_b?: [number, number] | null
  distance?: number | null
  tolerance?: number | null
  distance_units?: string | null
  label?: string
  geometry?: Geometry | null
  issue_class?: string
  provenance?: Record<string, unknown> | null
  priority_score?: number
}

export type IssuesResponse = FeatureCollection & {
  issues: Issue[]
}

export type PreviewUploadResponse = {
  collection: FeatureCollection
  label: string
  note: string
  layers?: ShapefileLayerInfo[]
  detected_layer_count?: number
  selected_layer?: string
  can_run_all_layers?: boolean
}

export type UploadQaResponse = {
  profile: string
  feature_count: number
  issue_count: number
  analysisMode?: "public_demo_sample" | "full_loaded_layer"
  featuresLoaded?: number
  featuresAnalyzed?: number
  analysisLimit?: number
  fullLayerValidated?: boolean
  geometryType?: string
  samplePolicy?: string
  summary: ReportSummary
  thermal?: ThermalStatus
  issues: Issue[]
  issue_overlay: FeatureCollection
  report: Report
  messages: string[]
  completed: boolean
  execution_status: string
  operator_next_steps: string[]
}

export type ThermalStatus = {
  source: string
  max_temp_c: number | null
  avg_temp_c: number | null
  sensor_count: number
  warn_temp_c: number
  hard_temp_c: number
  status: "ok" | "warm" | "hot" | "unavailable"
  can_run: boolean
  message: string
  runtime_seconds?: number
}

export type ShapefileLayerInfo = {
  name: string
  path: string
  feature_count?: number | null
  geometry_type?: string | null
  is_valid?: boolean
  recommended_profile?: string | null
  profile_reason?: string | null
}
