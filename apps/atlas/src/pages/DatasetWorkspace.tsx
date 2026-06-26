import { lazy, Suspense, useEffect, useMemo, useState } from "react"
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
import SummaryCards from "../components/SummaryCards"
import { buildEndpointIssueOverlay, endpointIssueFocusFeature } from "../lib/endpointIssues"
import { featureIssueFeaturesOnly, featureIssuesOnly, isNonVisualCleanedIssue, isOperationalIssue, isOperationalIssueFeature } from "../lib/issues"
import { resolveDatasetMapView } from "../lib/mapBounds"

const MapPanel = lazy(() => import("../components/MapPanel"))

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
    setSelectedIssueId(null)
    setFocusFeature(null)
    setShowCleaned(false)
    setCleaned(null)
    Promise.all([getDataset(datasetId), getDatasetGeojson(datasetId), getIssues(datasetId), getReport(datasetId)])
      .then(([datasetPayload, rawPayload, issuePayload, reportPayload]) => {
        setDataset(datasetPayload)
        setRaw(rawPayload)
        setIssues(issuePayload)
        setReport(reportPayload)
      })
      .catch((caught: Error) => setError(caught.message))
      .finally(() => setLoading(false))
  }, [datasetId])

  useEffect(() => {
    if (!datasetId || !showCleaned || cleaned) return
    if (!dataset?.cleaned_preview?.available || !dataset.cleaned_preview.meaningful) return
    let active = true
    getCleanedGeojson(datasetId)
      .then((cleanedPayload) => {
        if (active) setCleaned(cleanedPayload)
      })
      .catch((caught: Error) => {
        if (active) setError(caught.message)
      })
    return () => {
      active = false
    }
  }, [cleaned, dataset, datasetId, showCleaned])

  const issueRows = useMemo(() => featureIssuesOnly(report?.issues ?? issues?.issues ?? []), [report?.issues, issues?.issues])
  const issueFeatures = useMemo(() => {
    if (!issues) return undefined
    const baseOverlay = {
      type: "FeatureCollection",
      features: featureIssueFeaturesOnly(issues.features as Feature<Geometry>[]),
    } as FeatureCollection
    const endpointOverlay = buildEndpointIssueOverlay(baseOverlay, issueRows)
    if (endpointOverlay) return endpointOverlay
    return {
      type: "FeatureCollection",
      features: featureIssueFeaturesOnly(issues.features as Feature<Geometry>[]),
    } as FeatureCollection
  }, [issueRows, issues])

  const selectedIssue = issueRows.find((issue) => issue.issue_id === selectedIssueId)
  const selectedIssueIsOperational = isOperationalIssue(selectedIssue)
  const cleanedAvailable = Boolean(dataset?.cleaned_preview?.available && dataset.cleaned_preview.meaningful)
  const selectedIssueHasNoCleanedPreview = isNonVisualCleanedIssue(selectedIssue)
  const cleanedSupportedIssueTypes = dataset?.cleaned_preview?.supportedIssueTypes ?? []
  const cleanedVisible = Boolean(cleaned) && cleanedAvailable && showCleaned && !selectedIssueIsOperational
  const datasetMapView = useMemo(() => {
    if (!dataset) return {}
    return resolveDatasetMapView({
      dataset,
      raw,
      issues: issueFeatures,
      cleaned,
      showRaw,
      showIssues,
      showCleaned: cleanedVisible,
    })
  }, [cleaned, cleanedVisible, dataset, issueFeatures, raw, showCleaned, showIssues, showRaw])

  function showIssueOnMap(issue: Issue) {
    const issueId = issue.issue_id ?? null
    setSelectedIssueId(issueId)
    if (isOperationalIssue(issue)) {
      setFocusFeature(null)
      return
    }
    const endpointFeature = endpointIssueFocusFeature(issue)
    if (endpointFeature) {
      setFocusFeature(endpointFeature)
      return
    }
    const feature = issues?.features.find((item) => item.properties?.issue_id === issueId) as Feature<Geometry> | undefined
    if (feature) {
      setFocusFeature({ ...feature })
      return
    }
    const rawFeature = findRawFeatureForIssue(raw, issue)
    if (rawFeature) {
      setFocusFeature({
        ...rawFeature,
        properties: {
          ...(rawFeature.properties ?? {}),
          issue_id: issueId,
          problem_name: issue.problem_name,
          severity: issue.severity,
          _focus_only: true,
        },
      })
    }
  }

  function selectIssueFeature(feature: Feature<Geometry>) {
    const issueId = String(feature.properties?.issue_id ?? "")
    setSelectedIssueId(issueId)
    if (isOperationalIssueFeature(feature)) {
      setFocusFeature(null)
      setDrawerOpen(true)
      return
    }
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
            showCleaned={cleanedVisible}
            cleanedAvailable={cleanedAvailable}
            cleanedLayerNote={dataset.cleaned_layer_note}
            selectedIssueProblem={selectedIssue?.problem_name}
            cleanedSupportedIssueTypes={cleanedSupportedIssueTypes}
            onRawChange={setShowRaw}
            onIssuesChange={setShowIssues}
            onCleanedChange={setShowCleaned}
          />
          {raw ? (
            <Suspense fallback={<LoadingState label="Loading map" />}>
              <MapPanel
                raw={raw}
                issues={issueFeatures}
                cleaned={cleaned}
                bounds={datasetMapView.bounds}
                mapPadding={datasetMapView.padding}
                mapMaxZoom={datasetMapView.maxZoom}
                mapMinZoom={datasetMapView.minZoom}
                mapCenter={datasetMapView.center}
                mapZoom={datasetMapView.zoom}
                showRaw={showRaw}
                showIssues={showIssues}
                showCleaned={cleanedVisible && !selectedIssueHasNoCleanedPreview}
                selectedIssueId={selectedIssueId}
                focusFeature={focusFeature}
                onIssueSelect={selectIssueFeature}
              />
            </Suspense>
          ) : (
            <LoadingState label="Loading selected dataset layer" />
          )}
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

function findRawFeatureForIssue(collection: FeatureCollection | undefined, issue: Issue): Feature<Geometry> | null {
  if (!collection || issue.feature_id === undefined || issue.feature_id === null) return null
  const wanted = String(issue.feature_id)
  const match = collection.features.find((feature, index) => {
    const props = feature.properties ?? {}
    return [
      props.id,
      props.ID,
      props["@id"],
      props.osm_id,
      props.fid,
      props.FID,
      props.objectid,
      props.OBJECTID,
      index,
      index + 1,
    ].some((candidate) => candidate !== undefined && candidate !== null && String(candidate) === wanted)
  })
  return match?.geometry ? (match as Feature<Geometry>) : null
}
