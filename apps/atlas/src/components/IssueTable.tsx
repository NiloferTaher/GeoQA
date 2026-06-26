import type { Issue } from "../types"
import { formatProblem } from "./TopIssueTypes"

type IssueTableProps = {
  issues: Issue[]
}

export default function IssueTable({ issues }: IssueTableProps) {
  if (!issues.length) {
    return <p className="muted">No issues were returned for this dataset.</p>
  }
  return (
    <div className="table-wrap">
      <table className="issue-table">
        <thead>
          <tr>
            <th>Severity</th>
            <th>Issue</th>
            <th>Feature</th>
            <th>Recommendation</th>
          </tr>
        </thead>
        <tbody>
          {issues.slice(0, 30).map((issue, index) => (
            <tr key={issue.issue_id ?? `${issue.problem_name}-${index}`}>
              <td>
                <span className={`severity-pill ${issue.severity.toLowerCase()}`}>{issue.severity}</span>
              </td>
              <td>
                <strong>{formatProblem(issue.problem_name)}</strong>
                <span>{issue.description}</span>
              </td>
              <td>{issue.feature_id ?? "Layer"}</td>
              <td>{issue.solution_hint ?? "Review this feature before downstream analysis."}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
