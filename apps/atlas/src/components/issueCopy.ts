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
  polygon_gap_same_layer: {
    description: "Adjacent polygon features leave a gap where the layer should form a continuous coverage.",
    recommendation: "Review the shared edge, confirm the authoritative boundary, and close the gap before publication.",
    why: "Gaps can cause missed area totals, failed overlays, and confusing public boundary outputs.",
  },
  polygon_overlap_same_layer: {
    description: "Polygon features overlap where the layer should have one clear area assignment.",
    recommendation: "Confirm precedence rules, then split, dissolve, or reshape the overlap conservatively.",
    why: "Overlaps can double count area and create conflicting risk or administrative assignments.",
  },
  crs_metadata_missing_or_ambiguous: {
    description: "The layer lacks clear coordinate reference system metadata or carries ambiguous CRS information.",
    recommendation: "Confirm the authoritative CRS and write explicit CRS metadata before delivery or analysis.",
    why: "Ambiguous CRS metadata can shift layers, break overlays, and make reports harder to defend.",
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
    description:
      "Operational issue. Validation was interrupted or limited by runtime, thermal, or budget constraints.",
    recommendation: "Rerun with low-resource mode, chunking, cache reuse, or a longer runtime budget.",
    why: "This does not mean the selected geometry itself is invalid or cleaned. It means validation did not complete fully.",
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
