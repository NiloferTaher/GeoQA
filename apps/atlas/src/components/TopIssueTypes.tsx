import type { ReportSummary } from "../types"

type TopIssueTypesProps = {
  summary?: ReportSummary
}

export default function TopIssueTypes({ summary }: TopIssueTypesProps) {
  const rows = summary?.top_issues ?? []
  if (!rows.length) {
    return <p className="muted">No issue categories were reported for this dataset.</p>
  }
  return (
    <div className="issue-bars" aria-label="Top issue types">
      {rows.map((row) => (
        <div className="issue-bar-row" key={row.problem_name}>
          <div className="issue-bar-label">
            <span>{formatProblem(row.problem_name)}</span>
            <strong>{row.count}</strong>
          </div>
          <div className="issue-bar-track">
            <span style={{ width: `${Math.max(row.percent, 4)}%` }} />
          </div>
        </div>
      ))}
    </div>
  )
}

export function formatProblem(value: string) {
  return value.replaceAll("_", " ")
}
