import { AlertCircle, CheckCircle2, Layers3, ShieldCheck } from "lucide-react"
import type { Dataset, ReportSummary } from "../types"

type SummaryCardsProps = {
  dataset: Dataset
  summary?: ReportSummary
}

export default function SummaryCards({ dataset, summary }: SummaryCardsProps) {
  const totalIssues = summary?.total_issues ?? summary?.issue_count ?? dataset.issue_count
  const actionable = summary?.actionable ?? 0
  const ratio = Math.round(((summary?.actionable_ratio ?? 0) as number) * 100)
  return (
    <section className="summary-grid" aria-label="QA summary">
      <article className="metric-card">
        <Layers3 size={20} />
        <span>Features</span>
        <strong>{dataset.feature_count.toLocaleString()}</strong>
      </article>
      <article className="metric-card">
        <AlertCircle size={20} />
        <span>Issues</span>
        <strong>{totalIssues.toLocaleString()}</strong>
      </article>
      <article className="metric-card">
        <ShieldCheck size={20} />
        <span>Actionable</span>
        <strong>{actionable.toLocaleString()}</strong>
      </article>
      <article className="metric-card">
        <CheckCircle2 size={20} />
        <span>Actionable signal</span>
        <strong>{ratio}%</strong>
      </article>
    </section>
  )
}
