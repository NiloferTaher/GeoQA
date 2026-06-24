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
          checked={showCleaned}
          disabled={!cleanedAvailable}
          onChange={(event) => onCleanedChange(event.target.checked)}
        />
        Cleaned layer
      </label>
    </div>
  )
}
