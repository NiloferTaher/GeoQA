import { ChevronDown, ChevronRight, Copy, FileJson, LocateFixed, PanelRightClose, PanelRightOpen } from "lucide-react"
import { useMemo, useState } from "react"
import type { Issue } from "../types"
import { displayIssueName, getIssueCopy } from "./issueCopy"
import { isOperationalIssue } from "../lib/issues"

type IssueDrawerProps = {
  issues: Issue[]
  command: string
  isOpen: boolean
  selectedIssueId?: string | null
  onToggle: () => void
  onShowIssue: (issue: Issue) => void
}

type IssueGroup = {
  name: string
  severity: string
  issues: Issue[]
}

export default function IssueDrawer({ issues, command, isOpen, selectedIssueId, onToggle, onShowIssue }: IssueDrawerProps) {
  const [expandedGroups, setExpandedGroups] = useState<Record<string, boolean>>({})
  const groups = useMemo(() => groupIssues(issues), [issues])

  async function copyCommand() {
    await navigator.clipboard.writeText(command)
  }

  if (!isOpen) {
    return (
      <button className="drawer-rail" type="button" onClick={onToggle} aria-label="Open issue drawer">
        <PanelRightOpen size={18} />
        Issues
      </button>
    )
  }

  return (
    <aside className="issue-drawer" aria-label="GeoQA issue drawer">
      <div className="drawer-header">
        <div>
          <p className="eyebrow">Map-first issue review</p>
          <h2>Problem drawer</h2>
        </div>
        <button className="icon-only" type="button" onClick={onToggle} aria-label="Close issue drawer">
          <PanelRightClose size={18} />
        </button>
      </div>
      <p className="drawer-intro">
        Issues are grouped first so repeated findings stay readable. Expand a group to inspect examples and locate them on
        the map.
      </p>
      <button className="mini-button drawer-copy" type="button" onClick={copyCommand}>
        <Copy size={16} />
        Copy command
      </button>
      <div className="issue-group-list">
        {groups.map((group) => {
          const expanded = expandedGroups[group.name] ?? group.name === groups[0]?.name
          const copy = getIssueCopy(group.name)
          return (
            <section className="issue-group" key={group.name}>
              <button
                className="issue-group-button"
                type="button"
                onClick={() => setExpandedGroups((current) => ({ ...current, [group.name]: !expanded }))}
                aria-expanded={expanded}
              >
                {expanded ? <ChevronDown size={17} /> : <ChevronRight size={17} />}
                <span>{displayIssueName(group.name)}</span>
                <strong>{group.issues.length}</strong>
              </button>
              <div className="issue-group-meta">
                <span className={`severity-pill ${group.severity.toLowerCase()}`}>{group.severity}</span>
                {isOperationalIssue({ problem_name: group.name }) ? <span className="operational-pill">Operational issue</span> : null}
                <span>Affected features {group.issues.length}</span>
                <span>{issueClassLabel(group.name)}</span>
              </div>
              {expanded ? (
                <div className="issue-group-body">
                  <InfoBlock title="What GeoQA found" value={copy.description} />
                  <InfoBlock title="Why it matters" value={copy.why} />
                  <InfoBlock title="How to fix" value={copy.recommendation} />
                  {copy.note ? <InfoBlock title="QA note" value={copy.note} /> : null}
                  <h3 className="examples-heading">Example affected features</h3>
                  <div className="issue-preview-list">
                    {group.issues.slice(0, 4).map((issue) => (
                      <IssueDetail
                        issue={issue}
                        selected={issue.issue_id === selectedIssueId}
                        key={issue.issue_id ?? `${issue.problem_name}-${issue.feature_id}`}
                        onShowIssue={onShowIssue}
                      />
                    ))}
                  </div>
                </div>
              ) : null}
            </section>
          )
        })}
      </div>
    </aside>
  )
}

function InfoBlock({ title, value }: { title: string; value: string }) {
  return (
    <div className="info-block">
      <h3>{title}</h3>
      <p>{value}</p>
    </div>
  )
}

function IssueDetail({
  issue,
  selected,
  onShowIssue,
}: {
  issue: Issue
  selected: boolean
  onShowIssue: (issue: Issue) => void
}) {
  const [showJson, setShowJson] = useState(false)
  const copy = getIssueCopy(issue.problem_name)
  const operational = isOperationalIssue(issue)
  return (
    <article className={`issue-detail-card ${selected ? "selected" : ""}`}>
      <div className="issue-detail-top">
        <div>
          <h4>{displayIssueName(issue.problem_name)}</h4>
          <span>Feature {issue.feature_id ?? "Layer"}</span>
        </div>
        <span className={`severity-pill ${issue.severity.toLowerCase()}`}>{issue.severity}</span>
      </div>
      {operational ? <span className="operational-pill inline">Operational issue</span> : null}
      <p>{copy.description}</p>
      <p className="why-copy">{copy.why}</p>
      <p className="recommendation">{copy.recommendation}</p>
      {copy.note ? <p className="qa-note">{copy.note}</p> : null}
      <div className="issue-detail-actions">
        <button className="mini-button" type="button" disabled={operational} onClick={() => onShowIssue(issue)}>
          <LocateFixed size={15} />
          {operational ? "Drawer only" : "Show on map"}
        </button>
        <button className="mini-button ghost" type="button" onClick={() => setShowJson((current) => !current)}>
          <FileJson size={15} />
          View raw JSON
        </button>
      </div>
      {showJson ? <pre className="raw-json">{JSON.stringify(issue, null, 2)}</pre> : null}
    </article>
  )
}

function groupIssues(issues: Issue[]): IssueGroup[] {
  const grouped = new Map<string, Issue[]>()
  for (const issue of issues) {
    const bucket = grouped.get(issue.problem_name) ?? []
    bucket.push(issue)
    grouped.set(issue.problem_name, bucket)
  }
  return Array.from(grouped.entries())
    .map(([name, groupIssues]) => ({
      name,
      severity: highestSeverity(groupIssues),
      issues: groupIssues,
    }))
    .sort((left, right) => right.issues.length - left.issues.length)
}

function highestSeverity(issues: Issue[]) {
  const rank: Record<string, number> = { critical: 4, high: 3, medium: 2, low: 1 }
  return issues
    .map((issue) => issue.severity)
    .sort((left, right) => (rank[right.toLowerCase()] ?? 0) - (rank[left.toLowerCase()] ?? 0))[0]
}

function issueClassLabel(problemName: string) {
  if (isOperationalIssue({ problem_name: problemName })) return "Operational review"
  if (problemName === "coordinate_precision_not_fit_for_use") return "QA finding"
  return "Fixable geometry review"
}
