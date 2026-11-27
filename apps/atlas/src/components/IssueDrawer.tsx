import { ChevronDown, ChevronRight, Copy, FileJson, LocateFixed, PanelRightClose, PanelRightOpen } from "lucide-react"
import { useMemo, useState } from "react"
import type { Feature, Geometry } from "geojson"
import type { Issue } from "../types"
import { displayIssueName, getIssueCopy } from "./issueCopy"
import { endpointIssueDetails } from "../lib/endpointIssues"
import { groupIssueExamples, isOperationalIssue, type IssueExample } from "../lib/issues"

type IssueDrawerProps = {
  issues: Issue[]
  command: string
  isOpen: boolean
  selectedIssueId?: string | null
  rawFeatures?: Feature<Geometry>[]
  onToggle: () => void
  onShowIssue: (issue: Issue) => void
}

type IssueGroup = {
  name: string
  severity: string
  issues: Issue[]
}

export default function IssueDrawer({ issues, command, isOpen, selectedIssueId, rawFeatures, onToggle, onShowIssue }: IssueDrawerProps) {
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
                <span>Affected examples {groupIssueExamples(group.issues).length}</span>
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
                    {groupIssueExamples(group.issues).slice(0, 4).map((example) => (
                      <IssueDetail
                        example={example}
                        selected={example.representative.issue_id === selectedIssueId}
                        rawFeatures={rawFeatures}
                        key={example.representative.issue_id ?? `${example.representative.problem_name}-${example.representative.feature_id}`}
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
  example,
  selected,
  rawFeatures,
  onShowIssue,
}: {
  example: IssueExample
  selected: boolean
  rawFeatures?: Feature<Geometry>[]
  onShowIssue: (issue: Issue) => void
}) {
  const [showJson, setShowJson] = useState(false)
  const issue = example.representative
  const copy = getIssueCopy(issue.problem_name)
  const operational = isOperationalIssue(issue)
  const featureLabel = issue.feature_id ?? "Layer"
  const rawFeature = useMemo(() => {
    if (!rawFeatures || issue.feature_id === undefined || issue.feature_id === null) return null
    const wanted = String(issue.feature_id)
    return rawFeatures.find((feature) => {
      const props = feature.properties ?? {}
      return [props.id, props.ID, props["@id"], props.osm_id, props.fid, props.FID, props.objectid, props.OBJECTID].some(
        (candidate) => candidate !== undefined && candidate !== null && String(candidate) === wanted,
      )
    }) ?? null
  }, [rawFeatures, issue.feature_id])
  const groupedCopy = groupedIssueCopy(example, featureLabel)
  const endpointDetails = endpointIssueDetails(issue)
  return (
    <article className={`issue-detail-card ${selected ? "selected" : ""}`}>
      <div className="issue-detail-top">
        <div>
          <h4>{displayIssueName(issue.problem_name)}</h4>
          <span>Feature {featureLabel}</span>
        </div>
        <span className={`severity-pill ${issue.severity.toLowerCase()}`}>{issue.severity}</span>
      </div>
      {operational ? <span className="operational-pill inline">Operational issue</span> : null}
      {groupedCopy ? <p className="grouped-copy">{groupedCopy}</p> : null}
      {endpointDetails.length ? (
        <ul className="endpoint-detail-list">
          {endpointDetails.map((detail) => (
            <li key={detail}>{detail}</li>
          ))}
        </ul>
      ) : null}
      <p>{copy.description}</p>
      <p className="why-copy">{copy.why}</p>
      {copy.ruleChecks || copy.doesNotEstablish || copy.investigate ? (
        <div className="finding-explanation">
          <h5>Notice → Investigate → Judge</h5>
          {copy.ruleChecks ? (
            <p><strong>Rule checks:</strong> {copy.ruleChecks}</p>
          ) : null}
          {copy.doesNotEstablish ? (
            <p><strong>Does not establish:</strong> {copy.doesNotEstablish}</p>
          ) : null}
          {copy.investigate?.length ? (
            <ul>
              {copy.investigate.map((q) => (
                <li key={q}>{q}</li>
              ))}
            </ul>
          ) : null}
        </div>
      ) : null}
      <p className="recommendation">{copy.recommendation}</p>
      {copy.hint ? <p className="hint-copy">{copy.hint}</p> : null}
      {copy.note ? <p className="qa-note">{copy.note}</p> : null}
      {rawFeature?.properties ? (
        <details className="feature-attributes">
          <summary>Feature attributes</summary>
          <table>
            <tbody>
              {Object.entries(rawFeature.properties)
                .filter(([key]) => !String(key).startsWith("_"))
                .map(([key, value]) => (
                  <tr key={key}>
                    <th>{key}</th>
                    <td>{String(value ?? "")}</td>
                  </tr>
                ))}
            </tbody>
          </table>
        </details>
      ) : null}
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

function groupedIssueCopy(example: IssueExample, featureLabel: string | number) {
  if (example.issueCount <= 1) return ""
  if (example.counterpartFeatures.length) {
    return `Feature ${featureLabel} has ${example.issueCount} related findings with features ${example.counterpartFeatures.join(", ")}.`
  }
  return `Feature ${featureLabel} has ${example.issueCount} related findings. Multiple duplicate relationships were reported for this feature.`
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
