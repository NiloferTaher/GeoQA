export const issueCopy: Record<string, { description: string; recommendation: string; why: string; note?: string; ruleChecks?: string; doesNotEstablish?: string; investigate?: string[]; hint?: string }> = {
  coordinate_precision_not_fit_for_use: {
    description:
      "The coordinates have too many or too few decimal places for the intended use.",
    recommendation:
      "Check your export settings. Too many decimals make files huge; too few can shift features.",
    why: "Precision affects file size and accuracy. Match it to your project's needs.",
    note: "Atlas does not change this automatically.",
  },
  missing_or_stale_spatial_index: {
    description:
      "This layer has no quick-lookup index, so large searches or overlays may run slowly. (The map still displays fine.)",
    recommendation:
      "In QGIS or ArcGIS, right-click the layer and choose 'Create spatial index' or 'Rebuild index'. Think of it like adding an index to a book so you can find pages faster.",
    why: "Without an index, the computer checks every feature one by one. With one, it jumps straight to the right area. This is a performance tip, not a data error.",
    note: "Atlas does not change this automatically. It is a readiness finding for large datasets.",
    ruleChecks: "Whether the dataset has a usable spatial index (R-tree or equivalent) for efficient spatial queries.",
    doesNotEstablish: "Whether the spatial data itself is correct or complete. The index only affects speed, not accuracy.",
    investigate: [
      "How many features does this layer have?",
      "Are you running large spatial queries or overlays on it?",
      "Does your GIS software show a spatial index for this layer?",
    ],
  },
  polygon_gap_same_layer: {
    description: "Two neighboring areas (like parcels or zones) don't touch, leaving a small gap between them.",
    recommendation: "Check the shared edge. If the gap is a real alley or road, leave it. If not, snap the edges together in your GIS tool.",
    why: "Gaps can cause area totals to be wrong and make boundaries look broken on a map.",
    note: "Atlas focuses the affected polygon. Use 'Show on map' to see where the gap is near the edge.",
    ruleChecks: "Whether adjacent polygons in the same layer leave an uncovered space where coverage is expected.",
    doesNotEstablish: "Whether the space should be covered by the polygon layer. The gap may be intentional (e.g., a road or river).",
    investigate: [
      "What is the intended coverage of this layer?",
      "Is the gap a real geographical exclusion or an unintended omission?",
      "Do the adjacent polygons share a common edge that should be snapped?",
    ],
  },
  polygon_overlap_same_layer: {
    description: "Two areas overlap where there should be only one owner (like two parcels claiming the same land).",
    recommendation: "Decide which boundary is correct, then split or reshape the overlap. Check your zoning or ownership rules first.",
    why: "Overlaps can double-count area and cause conflicting assignments in analysis.",
  },
  crs_metadata_missing_or_ambiguous: {
    description: "The layer doesn't clearly state what coordinate system it uses (like latitude/longitude vs. meters).",
    recommendation: "Check the source data and set the correct CRS (coordinate reference system) in your GIS tool.",
    why: "Wrong or missing CRS can shift the layer to the wrong location on Earth.",
  },
  self_intersection: {
    description: "A line (like a road or pipe) crosses over itself, creating a loop.",
    recommendation: "Split the line at the crossing point or reshape it so it follows one clean path.",
    why: "Self-crossing lines can create false junctions and make length calculations wrong.",
  },
  suspicious_near_miss_endpoints: {
    description: "Two line ends are very close but don't actually touch (like two pipes almost meeting).",
    recommendation: "Check if they should connect. If yes, snap them together. If not, leave them as is.",
    why: "They look connected on the map, but network analysis treats them as separate, which can break routing.",
  },
  unsnapped_endpoints_within_tolerance: {
    description: "Two line ends are within snapping distance but still separate.",
    recommendation: "Confirm they are the same junction, then snap them together carefully.",
    why: "Unsnapped endpoints can split a network into disconnected pieces.",
  },
  isolated_network_segment: {
    description: "A line (road or pipe) is completely disconnected from the rest of the network at both ends.",
    recommendation: "Check if it should connect to nearby lines. If it's a standalone feature (like a dead-end), that's fine.",
    why: "Disconnected segments can break routing and service-area calculations.",
    note: "Atlas highlights the affected feature on the map.",
  },
  line_dangle: {
    description: "A line ends without connecting to anything (a 'dangling' end).",
    recommendation: "Check if it should connect to a nearby line. If it's a dead-end road or capped pipe, it's fine.",
    why: "Dangling ends can create false dead ends in routing and network analysis.",
  },
  duplicate_feature_geometry: {
    description: "Two or more features have exactly the same shape and location.",
    recommendation: "Check if these are true duplicates. If so, keep one and remove the others. If they are different features that happen to overlap, verify both are needed.",
    why: "Duplicate features can inflate counts and cause double-counting in analysis.",
    ruleChecks: "Whether two or more features share identical geometry.",
    doesNotEstablish: "Whether the duplicates are errors or intentional (e.g., overlapping service areas).",
    investigate: [
      "Are these the same real-world feature recorded twice?",
      "Do they have different attributes that justify both?",
      "Which one is the authoritative record?",
    ],
    hint: "HINT: These features share the same location. Plausible reasons: (1) the same real-world object was recorded twice by mistake, (2) two different features happen to be at the same spot (e.g., a bank and an ATM in the same building), or (3) one is an older version that was not removed. Compare the attribute rows to decide.",
  },
  contains_null_geometry_parts: {
    description: "A feature has missing or empty geometry parts.",
    recommendation: "Check the source data. Remove or repair features with null geometries before analysis.",
    why: "Features without geometry can't be displayed on a map or used in spatial analysis.",
    ruleChecks: "Whether any geometry part is null or empty.",
    doesNotEstablish: "Whether the feature should exist at all. It may be a valid attribute-only record.",
    investigate: [
      "Is this feature supposed to have geometry?",
      "Was the geometry lost during export or conversion?",
      "Should this be removed or repaired?",
    ],
  },
  below_minimum_feature_length: {
    description: "A line feature is shorter than the minimum expected length.",
    recommendation: "Check if the short segment is a real feature (like a stub) or a digitizing error.",
    why: "Very short lines can be data entry mistakes or unnecessary detail.",
    ruleChecks: "Whether a line's length falls below a configured minimum threshold.",
    doesNotEstablish: "Whether the short line is invalid. It may be a legitimate connector or stub.",
    investigate: [
      "What is this short line supposed to represent?",
      "Is it a real feature or a digitizing artifact?",
      "Should the minimum length threshold be adjusted for this dataset?",
    ],
  },
  attribute_value_missing_from_reference_table: {
    description: "A feature references a value that doesn't exist in a lookup table.",
    recommendation: "Check the attribute value against the reference list. Correct typos or add missing entries.",
    why: "Missing references can break joins and cause features to be excluded from analysis.",
    ruleChecks: "Whether attribute values exist in the configured reference table.",
    doesNotEstablish: "Whether the value is wrong or the reference table is incomplete.",
    investigate: [
      "Is the value a typo or a valid new entry?",
      "Should the reference table be updated?",
      "Does this affect any downstream joins or reports?",
    ],
  },
  domain_violation: {
    description: "An attribute value falls outside the allowed set of values for that field.",
    recommendation: "Review the domain rules and correct values that don't belong.",
    why: "Invalid domain values can cause analysis errors and reporting inconsistencies.",
    ruleChecks: "Whether attribute values conform to the configured domain (allowed values).",
    doesNotEstablish: "Whether the value is wrong or the domain is too restrictive.",
    investigate: [
      "Is this value a data entry error?",
      "Should the domain be expanded to include this value?",
      "Does this affect any downstream analysis?",
    ],
  },
  validation_runtime_error: {
    description:
      "Validation was stopped early due to time or resource limits.",
    recommendation: "Try running on a smaller area or fewer features.",
    why: "Partial checks may miss some issues, but the ones found are still real.",
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
