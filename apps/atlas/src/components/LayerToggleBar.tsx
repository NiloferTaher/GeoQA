type LayerToggleBarProps = {
  showRaw: boolean
  showIssues: boolean
  showCleaned: boolean
  cleanedAvailable: boolean
  onRawChange: (value: boolean) => void
  onIssuesChange: (value: boolean) => void
  onCleanedChange: (value: boolean) => void
}

export default function LayerToggleBar({
  showRaw,
  showIssues,
  showCleaned,
  cleanedAvailable,
  onRawChange,
  onIssuesChange,
  onCleanedChange,
}: LayerToggleBarProps) {
  const cleanedChecked = cleanedAvailable && showCleaned
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
      {!cleanedAvailable ? <span className="layer-helper">No cleaned layer is available for this demo.</span> : null}
    </div>
  )
}
