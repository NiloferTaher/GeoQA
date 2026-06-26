export type RunQaLayerKey = "raw" | "analyzed" | "issues"

export type RunQaLayerVisibility = Record<RunQaLayerKey, boolean>

export function getDefaultRunQaLayerVisibility(issueCount: number): RunQaLayerVisibility {
  return {
    raw: true,
    analyzed: true,
    issues: issueCount > 0,
  }
}

export function toggleRunQaLayerVisibility(
  visibility: RunQaLayerVisibility,
  layer: RunQaLayerKey,
  options: { issueCount?: number } = {},
): RunQaLayerVisibility {
  if (layer === "issues" && options.issueCount === 0) return visibility
  return {
    ...visibility,
    [layer]: !visibility[layer],
  }
}
