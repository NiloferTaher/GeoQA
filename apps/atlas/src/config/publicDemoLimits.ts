import type { Feature, FeatureCollection, GeoJsonProperties, Geometry } from "geojson"

export type AnalysisMode = "public_demo_sample" | "full_loaded_layer"

export type AnalysisSummaryInput = {
  totalFeatures: number
  analyzedFeatures: number
  geometryType?: string | null
}

export type PublicDemoAnalysisMetadata = {
  analysisMode: AnalysisMode
  featuresLoaded: number
  featuresAnalyzed: number
  analysisLimit: number
  fullLayerValidated: boolean
  geometryType: string
  samplePolicy: "first_n_source_order"
}

export const publicDemoMode = import.meta.env.VITE_ATLAS_PUBLIC_DEMO !== "false"
export const showThermalCard = import.meta.env.VITE_ATLAS_SHOW_THERMAL === "true"

export function getPublicDemoAnalysisLimit(geometryType?: string | null): number {
  const normalized = String(geometryType ?? "").toLowerCase()
  if (normalized.includes("point")) return 20
  if (normalized.includes("line")) return 5
  if (normalized.includes("polygon")) return 5
  return 5
}

export function selectFeaturesForGeoQAAnalysis(
  featureCollection: FeatureCollection,
  geometryType?: string | null,
): { collection: FeatureCollection; metadata: PublicDemoAnalysisMetadata } {
  const totalFeatures = featureCollection.features.length
  const analysisLimit = getPublicDemoAnalysisLimit(geometryType)
  const featuresAnalyzed = Math.min(totalFeatures, analysisLimit)
  const analyzedFeatures = featureCollection.features.slice(0, featuresAnalyzed).map((feature, index) =>
    cloneAnalyzedFeature(feature, index, featuresAnalyzed),
  )
  return {
    collection: {
      ...featureCollection,
      features: analyzedFeatures,
    },
    metadata: {
      analysisMode: featuresAnalyzed === totalFeatures ? "full_loaded_layer" : "public_demo_sample",
      featuresLoaded: totalFeatures,
      featuresAnalyzed,
      analysisLimit,
      fullLayerValidated: featuresAnalyzed === totalFeatures,
      geometryType: geometryType || "Unknown",
      samplePolicy: "first_n_source_order",
    },
  }
}

export function getAnalysisSummaryText(input: AnalysisSummaryInput): string {
  if (input.totalFeatures === input.analyzedFeatures) {
    return `${input.analyzedFeatures.toLocaleString()} features analyzed by GeoQA.`
  }
  return `${input.analyzedFeatures.toLocaleString()} of ${input.totalFeatures.toLocaleString()} features analyzed by GeoQA in public demo mode.`
}

export function getAnalysisPreRunText(input: AnalysisSummaryInput): string {
  if (input.totalFeatures === input.analyzedFeatures) {
    return `GeoQA will analyze ${input.analyzedFeatures.toLocaleString()} loaded features.`
  }
  return `GeoQA will analyze ${input.analyzedFeatures.toLocaleString()} of ${input.totalFeatures.toLocaleString()} loaded features in public demo mode.`
}

export function getAnalysisHonestyText(metadata: PublicDemoAnalysisMetadata): string {
  if (metadata.fullLayerValidated) {
    return "All loaded features were checked in this public demo run."
  }
  return "Highlighted features were checked. Run GeoQA locally for full-layer validation."
}

export function getNoIssueText(metadata: PublicDemoAnalysisMetadata): string {
  return `No issues found in the ${metadata.featuresAnalyzed.toLocaleString()} GeoQA-analyzed features.`
}

export function getIssueText(metadata: PublicDemoAnalysisMetadata): string {
  if (metadata.featuresLoaded === metadata.featuresAnalyzed) {
    return "Issues found in the GeoQA-analyzed features."
  }
  return "Issues found in the GeoQA-analyzed features."
}

function cloneAnalyzedFeature(feature: Feature, index: number, total: number): Feature {
  const properties: GeoJsonProperties = {
    ...(feature.properties ?? {}),
    _geoqa_analyzed: true,
    _geoqa_sample_index: index + 1,
    _geoqa_original_index: index,
    _geoqa_sample_total: total,
  }
  return {
    ...feature,
    properties,
    geometry: cloneGeometry(feature.geometry) as Geometry,
  }
}

function cloneGeometry(geometry: Geometry | null): Geometry | null {
  return geometry ? JSON.parse(JSON.stringify(geometry)) : null
}
