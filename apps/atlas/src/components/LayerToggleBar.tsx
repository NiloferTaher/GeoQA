type LayerToggleBarProps = {
  showRaw: boolean
  showIssues: boolean
  showCleaned: boolean
  cleanedAvailable: boolean
  cleanedLayerNote?: string
  selectedIssueProblem?: string
  cleanedSupportedIssueTypes?: string[]
  onRawChange: (value: boolean) => void
  onIssuesChange: (value: boolean) => void
  onCleanedChange: (value: boolean) => void
}

export default function LayerToggleBar({
  showRaw,
  showIssues,
  showCleaned,
  cleanedAvailable,
  cleanedLayerNote,
  selectedIssueProblem,
  cleanedSupportedIssueTypes = [],
  onRawChange,
  onIssuesChange,
  onCleanedChange,
}: LayerToggleBarProps) {
  const cleanedChecked = cleanedAvailable && showCleaned
  const selectedIssueSupported = selectedIssueProblem ? cleanedSupportedIssueTypes.includes(selectedIssueProblem) : false
  const selectedIssueHasNoPreview =
    selectedIssueProblem &&
    !selectedIssueSupported &&
    [
      "coordinate_precision_not_fit_for_use",
      "missing_or_stale_spatial_index",
      "crs_metadata_missing_or_ambiguous",
      "invalid_spatial_reference",
    ].includes(selectedIssueProblem)
  const note = cleanedStatusNote({
    cleanedAvailable,
    cleanedChecked,
    cleanedLayerNote,
    selectedIssueHasNoPreview: Boolean(selectedIssueHasNoPreview),
    selectedIssueSupported,
  })
  return (
    <div className="layer-toolbar" aria-label="Map layer toggles">
      <label>
        <input type="checkbox" checked={showRaw} onChange={(event) => onRawChange(event.target.checked)} />
        Raw layer
      </label>
      <label>
        <input type="checkbox" checked={showIssues} onChange={(event) => onIssuesChange(event.target.checked)} />
        Issue overlay
      </label>
      <label className={!cleanedAvailable ? "disabled-control" : ""}>
        <input
          type="checkbox"
          checked={cleanedChecked}
          disabled={!cleanedAvailable}
          onChange={(event) => onCleanedChange(event.target.checked)}
        />
        Cleaned layer
      </label>
      <span className={`layer-helper ${cleanedAvailable ? "available" : ""}`}>
        {note}
      </span>
    </div>
  )
}

function cleanedStatusNote({
  cleanedAvailable,
  cleanedChecked,
  cleanedLayerNote,
  selectedIssueHasNoPreview,
  selectedIssueSupported,
}: {
  cleanedAvailable: boolean
  cleanedChecked: boolean
  cleanedLayerNote?: string
  selectedIssueHasNoPreview: boolean
  selectedIssueSupported: boolean
}) {
  if (!cleanedAvailable) return cleanedLayerNote ?? "No cleaned preview is available for this demo."
  if (selectedIssueHasNoPreview) {
    return "This finding does not create a visible cleaned geometry preview. Review settings or metadata rather than expecting a changed shape."
  }
  if (selectedIssueSupported) return "Cleaned preview is available for this supported geometry fix."
  if (cleanedChecked) return "Cleaned preview is shown in green or teal. Raw and issue layers remain available for comparison."
  return cleanedLayerNote ?? "Cleaned preview applies only to supported geometry fixes."
}
