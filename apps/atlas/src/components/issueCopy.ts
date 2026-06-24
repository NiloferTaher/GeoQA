export const issueCopy: Record<string, { description: string; recommendation: string; why: string }> = {
  coordinate_precision_not_fit_for_use: {
    description:
      "Coordinate precision is stored at an inappropriate level for the intended analysis or delivery format, either bloating output or truncating meaningful detail.",
    recommendation:
      "Review driver precision settings and align export precision with use-case tolerances. Snap coordinates to an appropriate grid before delivery when required.",
    why: "Precision drift can make files heavier, create inconsistent delivery outputs, or hide meaningful tolerances.",
  },
  missing_or_stale_spatial_index: {
    description:
      "A feature class lacks an effective spatial index or its index may be stale after heavy edits.",
    recommendation: "Rebuild or recreate the spatial index after bulk edits or loads.",
    why: "Spatial queries, overlays, and validation runs can become slower or less reliable.",
  },
  self_intersection: {
    description: "A line crosses itself, which can make network tracing and length calculations unreliable.",
    recommendation: "Split or reshape the affected segment so each pipe or road section follows one valid path.",
    why: "Self-crossing linework can create false junctions and confusing route behavior in downstream GIS tools.",
  },
  suspicious_near_miss_endpoints: {
    description: "Two endpoint coordinates stop very close to each other but do not touch.",
    recommendation: "Review the nearby endpoints and snap them together when they represent the same connection.",
    why: "Near misses often look connected on the map while network analysis treats them as disconnected.",
  },
  unsnapped_endpoints_within_tolerance: {
    description: "Endpoint pairs fall within the configured snapping tolerance but remain separate.",
    recommendation: "Apply conservative snapping after confirming the endpoints describe the same junction.",
    why: "Unsnapped endpoints can fragment a utility or road network and hide service gaps.",
  },
  validation_runtime_error: {
    description: "Validation was interrupted or limited by runtime, thermal, or budget constraints.",
    recommendation: "Rerun with low-resource mode, chunking, cache reuse, or a longer runtime budget.",
    why: "The report may contain useful partial findings, but it should not be treated as a full clean validation.",
  },
}

export function displayIssueName(value: string) {
  return value
    .split("_")
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ")
}

export function getIssueCopy(problemName: string) {
  return (
    issueCopy[problemName] ?? {
      description: "GeoQA found a quality signal that should be reviewed before delivery or analysis.",
      recommendation: "Inspect the affected feature and correct the source data or export settings before reuse.",
      why: "Small spatial data issues can become costly once they move into analysis, operations, or publishing.",
    }
  )
}
