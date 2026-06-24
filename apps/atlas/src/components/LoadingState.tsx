type LoadingStateProps = {
  label?: string
}

export default function LoadingState({ label = "Loading GeoQA data" }: LoadingStateProps) {
  return (
    <div className="loading-state" role="status" aria-live="polite">
      <span className="loading-ring" />
      <span>{label}</span>
    </div>
  )
}
