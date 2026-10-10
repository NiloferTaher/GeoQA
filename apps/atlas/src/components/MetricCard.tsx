import type { ReactNode } from "react"

type MetricCardProps = {
  icon?: ReactNode
  label: string
  value: string | number
}

export default function MetricCard({ icon, label, value }: MetricCardProps) {
  return (
    <article className="metric-card">
      {icon}
      <span>{label}</span>
      <strong>{value}</strong>
    </article>
  )
}
