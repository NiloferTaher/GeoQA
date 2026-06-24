import { useEffect, useMemo, useState } from "react"
import { Download, ExternalLink } from "lucide-react"
import { Link, useParams } from "react-router-dom"
import type { Feature, FeatureCollection, Geometry } from "geojson"
import { getCleanedGeojson, getDataset, getDatasetGeojson, getIssues, getReport, reportDownloadUrl } from "../api"
import type { Dataset, Issue, IssuesResponse, Report } from "../types"
import CommandPanel from "../components/CommandPanel"
import ErrorState from "../components/ErrorState"
import IssueDrawer from "../components/IssueDrawer"
import LayerToggleBar from "../components/LayerToggleBar"
import LoadingState from "../components/LoadingState"
import MapPanel from "../components/MapPanel"
import SummaryCards from "../components/SummaryCards"

export default function DatasetWorkspace() {
  const { datasetId } = useParams()
  const [dataset, setDataset] = useState<Dataset | null>(null)
  const [raw, setRaw] = useState<FeatureCollection | undefined>()
  const [cleaned, setCleaned] = useState<FeatureCollection | null>(null)
  const [issues, setIssues] = useState<IssuesResponse | null>(null)
  const [report, setReport] = useState<Report | null>(null)
  const [error, setError] = useState("")
  const [loading, setLoading] = useState(true)
  const [showRaw, setShowRaw] = useState(true)
  const [showIssues, setShowIssues] = useState(true)
  const [showCleaned, setShowCleaned] = useState(false)
  const [drawerOpen, setDrawerOpen] = useState(true)
  const [selectedIssueId, setSelectedIssueId] = useState<string | null>(null)
  const [focusFeature, setFocusFeature] = useState<Feature<Geometry> | null>(null)

  useEffect(() => {
    if (!datasetId) return
    setLoading(true)
    setError("")
    Promise.all([getDataset(datasetId), getDatasetGeojson(datasetId), getIssues(datasetId), getReport(datasetId)])
      .then(async ([datasetPayload, rawPayload, issuePayload, reportPayload]) => {
        setDataset(datasetPayload)
        setRaw(rawPayload)
        setIssues(issuePayload)
        setReport(reportPayload)
        if (datasetPayload.has_cleaned_layer) {
          const cleanedPayload = await getCleanedGeojson(datasetId)
          setCleaned(cleanedPayload)
        } else {
          setCleaned(null)
        }
      })
      .catch((caught: Error) => setError(caught.message))
      .finally(() => setLoading(false))
  }, [datasetId])

  const issueFeatures = useMemo(() => {
    if (!issues) return undefined
    return { type: "FeatureCollection", features: issues.features } as FeatureCollection
  }, [issues])

  const issueRows = report?.issues ?? issues?.issues ?? []

  function showIssueOnMap(issue: Issue) {
    const issueId = issue.issue_id ?? null
    setSelectedIssueId(issueId)
    const feature = issues?.features.find((item) => item.properties?.issue_id === issueId) as Feature<Geometry> | undefined
    if (feature) {
      setFocusFeature({ ...feature })
    }
  }

  function selectIssueFeature(feature: Feature<Geometry>) {
    const issueId = String(feature.properties?.issue_id ?? "")
    setSelectedIssueId(issueId)
    setFocusFeature({ ...feature })
    setDrawerOpen(true)
  }

  if (loading) {
    return (
      <div className="page">
        <LoadingState label="Loading dataset workspace" />
      </div>
    )
  }

  if (error || !dataset) {
    return (
      <div className="page narrow-page">
        <ErrorState message={error || "Dataset was not found."} />
        <Link className="text-link" to="/datasets">
          Back to datasets
        </Link>
      </div>
    )
  }

  return (
    <div className="workspace-page">
      <section className="workspace-header">
        <div>
          <Link className="text-link" to="/datasets">
            Demo datasets
          </Link>
          <h1>{dataset.name}</h1>
          <p>{dataset.description}</p>
        </div>
        <div className="workspace-actions">
          <a className="icon-button" href={reportDownloadUrl(dataset.id)} download>
            <Download size={17} />
            Download report
          </a>
          <a className="icon-button" href={dataset.github_url} target="_blank" rel="noreferrer">
            <ExternalLink size={17} />
            GitHub
          </a>
        </div>
      </section>

      <SummaryCards dataset={dataset} summary={report?.summary ?? dataset.summary} />

      <section className="workspace-grid">
        <div className="map-column">
          <LayerToggleBar
            showRaw={showRaw}
            showIssues={showIssues}
            showCleaned={showCleaned}
            cleanedAvailable={Boolean(cleaned)}
            onRawChange={setShowRaw}
            onIssuesChange={setShowIssues}
            onCleanedChange={setShowCleaned}
          />
          <MapPanel
            raw={raw}
            issues={issueFeatures}
            cleaned={cleaned}
            bounds={dataset.bounds}
            showRaw={showRaw}
            showIssues={showIssues}
            showCleaned={showCleaned}
            selectedIssueId={selectedIssueId}
            focusFeature={focusFeature}
            onIssueSelect={selectIssueFeature}
          />
        </div>

        <IssueDrawer
          issues={issueRows}
          command={dataset.command}
          isOpen={drawerOpen}
          selectedIssueId={selectedIssueId}
          onToggle={() => setDrawerOpen((current) => !current)}
          onShowIssue={showIssueOnMap}
        />
      </section>

      <section className="workspace-lower">
        <CommandPanel command={dataset.command} />
        <article className="panel-section">
          <h2>Dataset source</h2>
          <dl className="compact-list">
            <div>
              <dt>Profile</dt>
              <dd>{dataset.profile}</dd>
            </div>
            <div>
              <dt>Source</dt>
              <dd>
                <a href={dataset.source_url} target="_blank" rel="noreferrer">
                  {dataset.source_label}
                  <ExternalLink size={13} />
                </a>
              </dd>
            </div>
            <div>
              <dt>Geometry</dt>
              <dd>{dataset.geometry_type}</dd>
            </div>
          </dl>
        </article>
      </section>
    </div>
  )
}
