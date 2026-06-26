import { lazy, Suspense, useEffect, useMemo, useRef, useState } from "react"
import { AlertTriangle, CheckCircle2, Download, FileJson, Layers3, MapPinned, PlayCircle, ShieldCheck, UploadCloud } from "lucide-react"
import type { Feature, FeatureCollection, Geometry } from "geojson"
import ErrorState from "../components/ErrorState"
import { getThermalStatus, previewUploadedLayer, runUploadedQa } from "../api"
import {
  getAnalysisHonestyText,
  getAnalysisPreRunText,
  getAnalysisSummaryText,
  publicDemoMode,
  selectFeaturesForGeoQAAnalysis,
  showThermalCard,
  type PublicDemoAnalysisMetadata,
} from "../config/publicDemoLimits"
import {
  getDefaultRunQaLayerVisibility,
  toggleRunQaLayerVisibility,
  type RunQaLayerKey,
} from "../config/mapLayerToggles"
import {
  buildIssueOverlayWithFallback,
  findFirstIssueForProblem,
  getIssueCountText,
  getIssueFocusFeature,
  getIssueFocusKind,
  getSampledExecutionStatus,
  sanitizeFeatureCollectionForGeoQA,
} from "../config/runQaIssueHelpers"
import {
  buildDuplicateComparison,
  getIssueInterpretation,
  getRunQaSuggestions,
  isDuplicateIssue,
} from "../config/runQaExplainability"
import type { Issue, PreviewUploadResponse, ShapefileLayerInfo, ThermalStatus, UploadQaResponse } from "../types"
import { groupIssueExamples, type IssueExample } from "../lib/issues"

const MapPanel = lazy(() => import("../components/MapPanel"))

const profiles = [
  "generic_quick",
  "geometry",
  "point_asset_quick",
  "line_network_quick",
  "water_network_quick",
  "land_use_quick",
  "boundaries_quick",
]

const workflow = [
  "Upload layer",
  "Choose profile",
  "Find issues",
  "Review issues on map",
  "Apply conservative fixes",
  "Download report / cleaned dataset",
]

const command =
  "geoqa validate your-data.geojson --profile generic_quick --output-format json --report-path reports/your-data"
const maxPreviewFeatures = 5000
const backendZipPreviewThreshold = 80 * 1024 * 1024

type ParsedShapefileLayer = FeatureCollection & {
  fileName?: string
}

type ParsedPreview = PreviewUploadResponse

function previewCacheKey(file: File, layerName?: string) {
  return `${file.name}|${file.size}|${file.lastModified}|${layerName ?? ""}|${maxPreviewFeatures}`
}

function sameThermalStatus(previous: ThermalStatus | null, next: ThermalStatus) {
  if (!previous) return false
  return (
    previous.status === next.status &&
    previous.can_run === next.can_run &&
    previous.source === next.source &&
    Math.round(previous.max_temp_c ?? -1) === Math.round(next.max_temp_c ?? -1)
  )
}

function inferBounds(collection: FeatureCollection): [number, number, number, number] | undefined {
  const positions: Array<[number, number]> = []
  const visit = (value: unknown) => {
    if (!Array.isArray(value)) return
    if (Number.isFinite(value[0]) && Number.isFinite(value[1])) {
      positions.push([value[0], value[1]])
      return
    }
    value.forEach(visit)
  }
  collection.features.forEach((feature) => {
    const geometry = feature.geometry
    if (!geometry) return
    if (geometry.type === "GeometryCollection") {
      geometry.geometries.forEach((child) => {
        if (child.type !== "GeometryCollection") visit(child.coordinates)
      })
      return
    }
    visit(geometry.coordinates)
  })
  if (!positions.length) return undefined
  const lngs = positions.map(([lng]) => lng)
  const lats = positions.map(([, lat]) => lat)
  return [Math.min(...lngs), Math.min(...lats), Math.max(...lngs), Math.max(...lats)]
}

function inferDominantGeometryType(collection: FeatureCollection): string {
  const counts = new Map<string, number>()
  collection.features.forEach((feature) => {
    const type = feature.geometry?.type
    if (type) counts.set(type, (counts.get(type) ?? 0) + 1)
  })
  return Array.from(counts.entries()).sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0]))[0]?.[0] ?? ""
}

export default function RunQaPage() {
  const [profile, setProfile] = useState(profiles[0])
  const [preview, setPreview] = useState<FeatureCollection | null>(null)
  const [fileName, setFileName] = useState("")
  const [previewLabel, setPreviewLabel] = useState("")
  const [uploadNote, setUploadNote] = useState("")
  const [processing, setProcessing] = useState(false)
  const [uploadedFile, setUploadedFile] = useState<File | null>(null)
  const [running, setRunning] = useState(false)
  const [result, setResult] = useState<UploadQaResponse | null>(null)
  const [runError, setRunError] = useState("")
  const [layerVisibility, setLayerVisibility] = useState(getDefaultRunQaLayerVisibility(0))
  const [zipLayers, setZipLayers] = useState<ShapefileLayerInfo[]>([])
  const [selectedLayer, setSelectedLayer] = useState("")
  const [error, setError] = useState("")
  const [thermalStatus, setThermalStatus] = useState<ThermalStatus | null>(null)
  const [thermalError, setThermalError] = useState("")
  const [runAnalysisMetadata, setRunAnalysisMetadata] = useState<PublicDemoAnalysisMetadata | null>(null)
  const [focusedIssueFeature, setFocusedIssueFeature] = useState<Feature<Geometry> | null>(null)
  const [selectedIssueId, setSelectedIssueId] = useState<string | null>(null)
  const [mapFocusNote, setMapFocusNote] = useState("")
  const [expandedIssueGroup, setExpandedIssueGroup] = useState<string | null>(null)
  const previewCache = useRef(new Map<string, ParsedPreview>())
  const issueDetailsRef = useRef<HTMLElement | null>(null)

  const bounds = useMemo(() => (preview ? inferBounds(preview) : undefined), [preview])
  const selectedLayerInfo = useMemo(
    () => zipLayers.find((item) => item.name === selectedLayer || item.path === selectedLayer),
    [selectedLayer, zipLayers],
  )
  const activeGeometryType = selectedLayerInfo?.geometry_type ?? (preview ? inferDominantGeometryType(preview) : "")
  const availableProfiles = useMemo(() => profilesForGeometry(activeGeometryType), [activeGeometryType])
  const analysisPlan = useMemo(
    () => (preview ? selectFeaturesForGeoQAAnalysis(preview, activeGeometryType) : null),
    [preview, activeGeometryType],
  )
  const geoqaAnalyzedFeatureCollection = publicDemoMode ? analysisPlan?.collection ?? null : preview
  const analysisMetadata = analysisPlan?.metadata ?? null

  useEffect(() => {
    if (!availableProfiles.includes(profile)) {
      setProfile(availableProfiles[0] ?? profiles[0])
    }
  }, [availableProfiles, profile])

  useEffect(() => {
    if (!showThermalCard) return
    let active = true
    async function refresh() {
      try {
        const status = await getThermalStatus()
        if (!active) return
        setThermalStatus((previous) => (sameThermalStatus(previous, status) ? previous : status))
        setThermalError("")
      } catch {
        if (!active) return
        setThermalError("CPU temperature is not available from the local Atlas backend.")
      }
    }
    refresh()
    const intervalMs = running ? 5000 : uploadedFile ? 15000 : 30000
    const interval = window.setInterval(refresh, intervalMs)
    return () => {
      active = false
      window.clearInterval(interval)
    }
  }, [running, uploadedFile])

  function resetIssueFocus() {
    setFocusedIssueFeature(null)
    setSelectedIssueId(null)
    setMapFocusNote("")
    setExpandedIssueGroup(null)
  }

  async function handleUpload(file?: File) {
    setError("")
    setPreview(null)
    setPreviewLabel("")
    setUploadNote("")
    setUploadedFile(null)
    setResult(null)
    setRunError("")
    setRunAnalysisMetadata(null)
    setLayerVisibility(getDefaultRunQaLayerVisibility(0))
    resetIssueFocus()
    setZipLayers([])
    setSelectedLayer("")
    if (!file) return
    previewCache.current = new Map()
    setFileName(file.name)
    setUploadedFile(file)
    setProcessing(true)
    try {
      const parsed = await getCachedPreview(file)
      applyPreview(parsed)
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "GeoQA Atlas could not read this layer preview.")
    } finally {
      setProcessing(false)
    }
  }

  function applyPreview(parsed: ParsedPreview) {
    const needsLayerSelection = (parsed.layers?.length ?? 0) > 1 && !parsed.selected_layer
    setPreview(needsLayerSelection ? null : parsed.collection)
    setPreviewLabel(parsed.label)
    setUploadNote(parsed.note)
    setZipLayers(parsed.layers ?? [])
    setSelectedLayer(parsed.selected_layer ?? "")
    const recommendedProfile = profileForLayer(parsed.layers ?? [], parsed.selected_layer)
    const geometryProfile = profileForGeometry(parsed.layers ?? [], parsed.selected_layer, parsed.collection)
    if (shouldUseRecommendedProfile(recommendedProfile, geometryProfile)) setProfile(recommendedProfile)
    else if (geometryProfile) setProfile(geometryProfile)
  }

  function handleProfileChange(value: string) {
    setProfile(value)
    setResult(null)
    setRunError("")
    setRunAnalysisMetadata(null)
    setLayerVisibility(getDefaultRunQaLayerVisibility(0))
    resetIssueFocus()
  }

  async function handleRunQa() {
    if (!uploadedFile) {
      setRunError("Upload a GeoJSON layer or zipped Shapefile first.")
      return
    }
    setRunning(true)
    setRunError("")
    setResult(null)
    setRunAnalysisMetadata(null)
    setLayerVisibility(getDefaultRunQaLayerVisibility(0))
    resetIssueFocus()
    try {
      if (showThermalCard) {
        const status = await getThermalStatus()
        setThermalStatus(status)
        setThermalError("")
        if (!status.can_run) {
          setRunError(status.message)
          return
        }
      }
      const plan = publicDemoMode && analysisPlan ? analysisPlan : null
      const analysisFile = plan ? featureCollectionToFile(sanitizeFeatureCollectionForGeoQA(plan.collection), uploadedFile.name) : uploadedFile
      const payload = await runUploadedQa(analysisFile, profile, plan ? undefined : selectedLayer || undefined)
      setResult(plan ? withAnalysisMetadata(payload, plan.metadata) : payload)
      setRunAnalysisMetadata(plan?.metadata ?? null)
      if (showThermalCard && payload.thermal) setThermalStatus(thermalFromResult(payload.thermal))
      setLayerVisibility(getDefaultRunQaLayerVisibility(payload.issue_overlay.features.length))
    } catch (caught) {
      setRunError(caught instanceof Error ? caught.message : "GeoQA Atlas could not run QA on this layer.")
    } finally {
      setRunning(false)
    }
  }

  async function handleLayerChange(value: string) {
    if (value === selectedLayer) return
    setSelectedLayer(value)
    const recommendedProfile = profileForLayer(zipLayers, value)
    const geometryProfile = profileForGeometry(zipLayers, value)
    if (shouldUseRecommendedProfile(recommendedProfile, geometryProfile)) setProfile(recommendedProfile)
    else if (geometryProfile) setProfile(geometryProfile)
    setPreview(null)
    setPreviewLabel("")
    setUploadNote("")
    setError("")
    setResult(null)
    setRunError("")
    setRunAnalysisMetadata(null)
    setLayerVisibility(getDefaultRunQaLayerVisibility(0))
    resetIssueFocus()
    if (!uploadedFile) return
    setProcessing(true)
    try {
      const parsed = await getCachedPreview(uploadedFile, value)
      applyPreview(parsed)
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "GeoQA Atlas could not read this layer preview.")
    } finally {
      setProcessing(false)
    }
  }

  function downloadReport() {
    if (!result) return
    const blob = new Blob([JSON.stringify(result.report, null, 2)], { type: "application/json" })
    const url = URL.createObjectURL(blob)
    const anchor = document.createElement("a")
    anchor.href = url
    anchor.download = `${fileName || "uploaded-layer"}-${result.profile}-geoqa-report.json`
    document.body.appendChild(anchor)
    anchor.click()
    anchor.remove()
    URL.revokeObjectURL(url)
  }

  async function getCachedPreview(file: File, layerName?: string): Promise<ParsedPreview> {
    const key = previewCacheKey(file, layerName)
    const cached = previewCache.current.get(key)
    if (cached) return cached
    const parsed = await parsePreviewFile(file, layerName)
    previewCache.current.set(key, parsed)
    return parsed
  }

  const issueOverlay = useMemo(
    () => buildIssueOverlayWithFallback(result?.issue_overlay, result?.issues ?? [], geoqaAnalyzedFeatureCollection),
    [result?.issue_overlay, result?.issues, geoqaAnalyzedFeatureCollection],
  )
  const topIssues = result?.summary.top_issues ?? []
  const groupedRunIssues = useMemo(() => groupRunIssues(result?.issues ?? []), [result?.issues])
  const selectedIssue = useMemo(
    () => result?.issues.find((issue) => issue.issue_id === selectedIssueId) ?? null,
    [result?.issues, selectedIssueId],
  )
  const selectedIssueIndex = selectedIssue && result ? result.issues.findIndex((issue) => issue.issue_id === selectedIssue.issue_id) : -1
  const selectedFocusKind = selectedIssue ? getIssueFocusKind(selectedIssue, issueOverlay, geoqaAnalyzedFeatureCollection) : "none"
  const displayedAnalysisMetadata = runAnalysisMetadata ?? analysisMetadata
  const issueOverlayCount = issueOverlay?.features.length ?? 0
  const runSuggestions = useMemo(
    () =>
      getRunQaSuggestions({
        issues: result?.issues ?? [],
        selectedLayer,
        zipLayers,
        profile: result?.profile ?? profile,
        geometryType: displayedAnalysisMetadata?.geometryType ?? activeGeometryType,
        analysisFullLayer: displayedAnalysisMetadata?.fullLayerValidated,
      }),
    [activeGeometryType, displayedAnalysisMetadata, profile, result, selectedLayer, zipLayers],
  )

  function handleLegendToggle(layer: RunQaLayerKey) {
    setLayerVisibility((current) => toggleRunQaLayerVisibility(current, layer, { issueCount: issueOverlayCount }))
  }

  function focusIssue(issue: Issue) {
    const feature = getIssueFocusFeature(issue, issueOverlay, geoqaAnalyzedFeatureCollection)
    setSelectedIssueId(issue.issue_id ?? `${issue.problem_name}-${issue.feature_id ?? ""}`)
    setExpandedIssueGroup(issue.problem_name)
    if (!feature) {
      const contextFeature = boundsToFeature(inferBounds(geoqaAnalyzedFeatureCollection ?? preview ?? { type: "FeatureCollection", features: [] }))
      if (contextFeature && getIssueFocusKind(issue, issueOverlay, geoqaAnalyzedFeatureCollection) === "layer") {
        setFocusedIssueFeature({ ...contextFeature, properties: { _focus_tick: Date.now() } })
        setMapFocusNote("Layer-level finding. Atlas is showing the analyzed feature subset for context.")
        return
      }
      setMapFocusNote("No map location is available for this run-level notice.")
      return
    }
    setLayerVisibility((current) => ({ ...current, issues: true }))
    setFocusedIssueFeature({
      ...feature,
      properties: { ...(feature.properties ?? {}), _focus_tick: Date.now() },
    })
    setMapFocusNote("")
  }

  function focusTopIssue(problemName: string) {
    const issue = result ? findFirstIssueForProblem(result.issues, problemName, issueOverlay, geoqaAnalyzedFeatureCollection) : null
    setExpandedIssueGroup(problemName)
    issueDetailsRef.current?.scrollIntoView({ behavior: "smooth", block: "start" })
    if (issue) focusIssue(issue)
  }

  function focusRelativeIssue(direction: -1 | 1) {
    if (!result?.issues.length) return
    const currentIndex = selectedIssueIndex >= 0 ? selectedIssueIndex : 0
    const nextIndex = (currentIndex + direction + result.issues.length) % result.issues.length
    focusIssue(result.issues[nextIndex])
  }

  return (
    <div className="page narrow-page run-page">
      <section className="page-heading run-heading">
        <p className="eyebrow">Atlas workflow preview</p>
        <h1>Run QA on your own layer</h1>
        <p>
          Preview a browser-readable layer, choose a GeoQA profile, and see how the backend-connected validation flow
          will return findings, reports, and any conservative cleaned output.
        </p>
      </section>

      <section className="run-notice">
        <ShieldCheck size={20} />
        <p>
          Atlas preview supports GeoJSON and zipped Shapefile where browser parsing is available. Full GeoQA validation
          through the Python backend can support additional GeoPandas-readable formats such as Shapefile, GeoPackage,
          CSV, GeoJSON, and GeoParquet.
        </p>
      </section>

      <section className="workflow-strip" aria-label="GeoQA workflow steps">
        {workflow.map((step, index) => (
          <article className="workflow-step" key={step}>
            <span>{index + 1}</span>
            <strong>{step}</strong>
          </article>
        ))}
      </section>

      <section className="run-grid">
        <article className="run-panel">
          <div className="panel-title-row">
            <UploadCloud size={21} />
            <h2>Layer preview</h2>
          </div>
          <label className="upload-drop">
            <input
              type="file"
              accept=".geojson,.json,.zip,application/geo+json,application/json,application/zip"
              onChange={(event) => handleUpload(event.target.files?.[0])}
            />
            <FileJson size={28} />
            <span>{fileName || "Choose a GeoJSON FeatureCollection or zipped Shapefile"}</span>
          </label>
          {processing ? <p className="upload-note">Reading layer preview...</p> : null}
          {previewLabel ? <p className="upload-note">{previewLabel}</p> : null}
          {uploadNote ? <p className="upload-note muted">{uploadNote}</p> : null}
          {error ? <ErrorState message={error} /> : null}
          {zipLayers.length ? (
            <div className="layer-selector-panel">
              <div className="layer-selector-heading">
                <strong>Detected {zipLayers.length} Shapefile layers in this ZIP.</strong>
                <span>Atlas will validate only the selected layer for now.</span>
              </div>
              <label className="field-label" htmlFor="zip-layer-select">
                Shapefile layer
              </label>
              <select id="zip-layer-select" value={selectedLayer} onChange={(event) => handleLayerChange(event.target.value)}>
                {!selectedLayer ? (
                  <option value="" disabled>
                    Select one Shapefile layer
                  </option>
                ) : null}
                {zipLayers.map((layer) => (
                  <option key={layer.name} value={layer.name} disabled={!layer.is_valid}>
                    {formatLayerOption(layer)}
                  </option>
                ))}
              </select>
              <button className="mini-button run-all-placeholder" type="button" disabled>
                Run QA on all layers
              </button>
              <p className="upload-note muted">All-layer batch validation is planned for a future Atlas workflow.</p>
            </div>
          ) : null}
          <label className="field-label" htmlFor="profile-select">
            GeoQA profile
          </label>
          <select id="profile-select" value={profile} onChange={(event) => handleProfileChange(event.target.value)}>
            {availableProfiles.map((item) => (
              <option key={item} value={item}>
                {item}
              </option>
            ))}
          </select>
          <pre className="command-preview">
            <code>{command.replace("generic_quick", profile)}</code>
          </pre>
          {displayedAnalysisMetadata ? (
            <div className="analysis-plan-card">
              <strong>
                {result
                  ? getAnalysisSummaryText({
                      totalFeatures: displayedAnalysisMetadata.featuresLoaded,
                      analyzedFeatures: displayedAnalysisMetadata.featuresAnalyzed,
                      geometryType: displayedAnalysisMetadata.geometryType,
                    })
                  : getAnalysisPreRunText({
                      totalFeatures: displayedAnalysisMetadata.featuresLoaded,
                      analyzedFeatures: displayedAnalysisMetadata.featuresAnalyzed,
                      geometryType: displayedAnalysisMetadata.geometryType,
                    })}
              </strong>
              <span>{getAnalysisHonestyText(displayedAnalysisMetadata)}</span>
              {!displayedAnalysisMetadata.fullLayerValidated ? (
                <small>Public demo mode checks the first loaded features for this geometry type.</small>
              ) : null}
            </div>
          ) : null}
          {showThermalCard ? <ThermalCard status={thermalStatus} error={thermalError} running={running} /> : null}
          <button
            className="run-qa-button"
            type="button"
            onClick={handleRunQa}
            disabled={
              !preview ||
              processing ||
              running ||
              thermalStatus?.can_run === false ||
              (zipLayers.length > 1 && !selectedLayer)
            }
          >
            <PlayCircle size={19} />
            {running ? "Running GeoQA..." : "Run QA"}
          </button>
          {runError ? <ErrorState message={runError} /> : null}
          {result ? (
            <div className="run-status-card">
              <CheckCircle2 size={19} />
              <div>
                <strong>{getIssueCountText(result.issue_count)}</strong>
                <span>
                  {(displayedAnalysisMetadata?.featuresAnalyzed ?? result.feature_count).toLocaleString()} features checked with {result.profile}
                </span>
              </div>
            </div>
          ) : null}
        </article>

        <article className="run-panel map-preview-panel">
          <div className="panel-title-row">
            <MapPinned size={21} />
            <h2>Map preview</h2>
          </div>
          {preview ? (
              <Suspense fallback={<div className="empty-preview"><Layers3 size={34} /><p>Loading map preview.</p></div>}>
                <MapPanel
                  renderKey={`${fileName}-${selectedLayer}-${previewLabel}-${preview.features.length}-${issueOverlay?.features.length ?? 0}`}
                  raw={preview}
                  analyzed={geoqaAnalyzedFeatureCollection}
                  issues={issueOverlay}
                  bounds={bounds}
                  showRaw={layerVisibility.raw}
                  showAnalyzed={layerVisibility.analyzed}
                  showIssues={layerVisibility.issues}
                  showCleaned={false}
                  selectedIssueId={selectedIssueId}
                  focusFeature={focusedIssueFeature}
                  onIssueSelect={(feature) => {
                    const issueId = String(feature.properties?.issue_id ?? "")
                    const issue = result?.issues.find((item) => item.issue_id === issueId)
                    if (issue) focusIssue(issue)
                  }}
                  lowCostPointRendering
                  mapMode="runQa"
                />
              </Suspense>
          ) : (
            <div className="empty-preview">
              <Layers3 size={34} />
              <p>
                {zipLayers.length > 1
                  ? "Select one Shapefile layer to load it on the map."
                  : "Your uploaded GeoJSON layer will appear here before validation runs."}
              </p>
            </div>
          )}
          {displayedAnalysisMetadata ? (
            <div className="map-legend" aria-label="Map layer visibility">
              <button
                className="legend-toggle"
                type="button"
                aria-pressed={layerVisibility.raw}
                onClick={() => handleLegendToggle("raw")}
              >
                <span className="legend-swatch raw" aria-hidden="true" />
                Raw uploaded layer, {displayedAnalysisMetadata.featuresLoaded.toLocaleString()} features loaded
              </button>
              <button
                className="legend-toggle"
                type="button"
                aria-pressed={layerVisibility.analyzed}
                onClick={() => handleLegendToggle("analyzed")}
              >
                <span className="legend-swatch analyzed" aria-hidden="true" />
                GeoQA-analyzed features, {displayedAnalysisMetadata.featuresAnalyzed.toLocaleString()} checked
              </button>
              <button
                className="legend-toggle"
                type="button"
                aria-pressed={layerVisibility.issues}
                disabled={!issueOverlayCount}
                onClick={() => handleLegendToggle("issues")}
              >
                <span className="legend-swatch issue" aria-hidden="true" />
                {issueOverlayCount ? "Issue overlay, findings from checked features" : "Issue overlay, no findings from checked features"}
              </button>
            </div>
          ) : null}
          {selectedIssue ? (
            <SelectedIssuePanel
              issue={selectedIssue}
              issueIndex={selectedIssueIndex}
              totalIssues={result?.issues.length ?? 0}
              focusKind={selectedFocusKind}
              focusNote={mapFocusNote}
              analyzed={geoqaAnalyzedFeatureCollection}
              selectedLayer={selectedLayer}
              zipLayers={zipLayers}
              onPrevious={() => focusRelativeIssue(-1)}
              onNext={() => focusRelativeIssue(1)}
            />
          ) : null}
        </article>
      </section>

      {result ? (
        <section className="run-results-grid" aria-label="GeoQA upload results">
          <article className="run-result-panel">
            <div className="panel-title-row">
              <AlertTriangle size={21} />
              <h2>Validation summary</h2>
            </div>
            <div className="run-metrics">
              <div>
                <span>Features</span>
                <strong>{(displayedAnalysisMetadata?.featuresAnalyzed ?? result.feature_count).toLocaleString()}</strong>
              </div>
              <div>
                <span>Issues</span>
                <strong>{result.issue_count.toLocaleString()}</strong>
              </div>
              <div>
                <span>Status</span>
                <strong>{getSampledExecutionStatus(result.execution_status, displayedAnalysisMetadata?.fullLayerValidated)}</strong>
              </div>
            </div>
            <button className="secondary-cta report-download" type="button" onClick={downloadReport}>
              <Download size={18} />
              Download report
            </button>
          </article>

          <article className="run-result-panel">
            <div className="panel-title-row">
              <Layers3 size={21} />
              <h2>Top issue types</h2>
            </div>
            {topIssues.length ? (
              <div className="run-issue-bars">
                {topIssues.map((item) => (
                  <button className="run-issue-row" key={item.problem_name} type="button" onClick={() => focusTopIssue(item.problem_name)}>
                    <span>{item.problem_name.replaceAll("_", " ")}</span>
                    <strong>{item.count}</strong>
                  </button>
                ))}
              </div>
            ) : (
              <p className="muted">GeoQA did not return issue groups for this profile.</p>
            )}
          </article>

          <article className="run-result-panel run-issues-list" ref={issueDetailsRef}>
            <div className="panel-title-row">
              <FileJson size={21} />
              <h2>Issue details</h2>
            </div>
            {groupedRunIssues.length ? (
              <div className="run-issue-list">
                {groupedRunIssues.map((group) => {
                  const expanded = expandedIssueGroup === group.problemName || groupedRunIssues.length === 1
                  return (
                    <article className="run-issue-group" key={group.problemName}>
                      <button
                        className="run-issue-group-button"
                        type="button"
                        aria-expanded={expanded}
                        onClick={() => {
                          setExpandedIssueGroup(expanded ? null : group.problemName)
                          if (!expanded) focusTopIssue(group.problemName)
                        }}
                      >
                        <span>
                          <strong>{group.problemName.replaceAll("_", " ")}</strong>
                          <small>{group.issues.length.toLocaleString()} {group.issues.length === 1 ? "issue" : "issues"}</small>
                        </span>
                        <b>{group.severity}</b>
                      </button>
                      {expanded ? (
                        <div className="run-issue-examples">
                          {group.examples.slice(0, 8).map((example, index) => (
                            <button
                              className="run-issue-card"
                              key={example.representative.issue_id ?? `${example.representative.problem_name}-${index}`}
                              type="button"
                              aria-current={selectedIssueId === example.representative.issue_id}
                              onClick={() => focusIssue(example.representative)}
                            >
                              <div>
                                <strong>{example.representative.problem_name.replaceAll("_", " ")}</strong>
                                <span>{example.representative.severity}</span>
                              </div>
                              <small>
                                {example.representative.feature_id === null || example.representative.feature_id === undefined
                                  ? `Issue ${index + 1}`
                                  : `Affected feature ${example.representative.feature_id}`}
                              </small>
                              {example.issueCount > 1 ? <p>{runGroupedIssueCopy(example)}</p> : null}
                              <p>{example.representative.description}</p>
                              <p className="issue-interpretation">
                                {getIssueInterpretation(example.representative, {
                                  selectedLayer,
                                  zipLayers,
                                  profile,
                                  geometryType: activeGeometryType,
                                })}
                              </p>
                              {isDuplicateIssue(example.representative) ? <span className="compare-action">Compare rows</span> : null}
                              {example.representative.solution_hint ? <p className="recommendation">{example.representative.solution_hint}</p> : null}
                              <span className="show-map-action">Show on map</span>
                            </button>
                          ))}
                        </div>
                      ) : null}
                    </article>
                  )
                })}
              </div>
            ) : (
              <p className="muted">No issues were returned for this uploaded layer and profile.</p>
            )}
          </article>

          <article className="run-result-panel run-notes-panel">
            <div className="panel-title-row">
              <CheckCircle2 size={21} />
              <h2>Run notes</h2>
            </div>
            <ul className="run-notes-list">
              {selectedLayer && zipLayers.length ? (
                <li>
                  Selected layer {selectedLayer}. Atlas validated this layer from {zipLayers.length.toLocaleString()} detected Shapefile layers.
                </li>
              ) : null}
              {displayedAnalysisMetadata ? (
                <li>
                  Full uploaded layer: {displayedAnalysisMetadata.featuresLoaded.toLocaleString()} features. GeoQA-analyzed subset:{" "}
                  {displayedAnalysisMetadata.featuresAnalyzed.toLocaleString()} features.
                </li>
              ) : null}
              {displayedAnalysisMetadata ? <li>{getAnalysisHonestyText(displayedAnalysisMetadata)}</li> : null}
              {displayedAnalysisMetadata && !displayedAnalysisMetadata.fullLayerValidated ? (
                <li>Sample policy: first loaded features by source order.</li>
              ) : null}
              {result.messages.concat(result.operator_next_steps).map((message) => (
                <li key={message}>{message}</li>
              ))}
            </ul>
            <div className="run-suggestions">
              <h3>Suggestions and interpretation</h3>
              <ul>
                {runSuggestions.map((suggestion) => (
                  <li key={suggestion}>{suggestion}</li>
                ))}
              </ul>
            </div>
          </article>
        </section>
      ) : (
        <section className="run-outcome">
          <CheckCircle2 size={22} />
          <div>
            <h2>What happens after Run QA</h2>
            <p>
              Atlas sends the uploaded local layer to the Python backend, calls the GeoQA engine, and returns a
              structured report plus issue overlays for map review.
            </p>
          </div>
        </section>
      )}
    </div>
  )
}

async function parsePreviewFile(file: File, layerName?: string): Promise<ParsedPreview> {
  const lowerName = file.name.toLowerCase()
  if (lowerName.endsWith(".zip")) {
    try {
      return await previewUploadedLayer(file, layerName)
    } catch {
      if (file.size >= backendZipPreviewThreshold) {
        throw new Error(
          "This large zipped Shapefile needs the local GeoQA Atlas backend preview. Smaller zipped Shapefiles can still be parsed in the browser.",
        )
      }
    }
    const buffer = await file.arrayBuffer()
    const { default: shp } = await import("shpjs")
    const parsed = await shp(buffer)
    const layers = (Array.isArray(parsed) ? parsed : [parsed]) as ParsedShapefileLayer[]
    const layerInfos = layers
      .filter((layer) => layer?.type === "FeatureCollection" && Array.isArray(layer.features))
      .map((layer, index) => layerInfoFromParsed(layer, index))
    if (!layerName && layerInfos.length > 1) {
      return {
        collection: { type: "FeatureCollection", features: [] },
        label: "Choose a Shapefile layer to preview.",
        note: `Detected ${layerInfos.length} Shapefile layers in this ZIP. Select one layer before Atlas loads it on the map.`,
        layers: layerInfos,
        detected_layer_count: layerInfos.length,
        selected_layer: "",
        can_run_all_layers: false,
      }
    }
    const selectedName = layerName && layerInfos.some((layer) => layer.name === layerName) ? layerName : chooseDefaultLayer(layerInfos)
    const usable = layers.find((layer, index) => (layerInfoFromParsed(layer, index).name === selectedName))
    if (!usable) {
      throw new Error("This zip did not include a readable Shapefile layer for browser preview.")
    }
    const collection = capPreviewFeatures(usable)
    const trimmed = usable.features.length - collection.features.length
    const layerNote = `Detected ${layerInfos.length} Shapefile layers in this ZIP. Atlas is previewing selected layer ${selectedName}.`
    const trimNote = trimmed > 0 ? ` Preview limited to ${collection.features.length.toLocaleString()} features for map speed.` : ""
    return {
      collection,
      label: `${collection.features.length.toLocaleString()} features loaded from selected Shapefile layer.`,
      note: `${layerNote}${trimNote}`,
      layers: layerInfos,
      detected_layer_count: layerInfos.length,
      selected_layer: selectedName,
      can_run_all_layers: false,
    }
  }

  const text = await file.text()
  let parsed: unknown
  try {
    parsed = JSON.parse(text)
  } catch {
    throw new Error("Upload a GeoJSON FeatureCollection or a zipped Shapefile.")
  }
  if (!isFeatureCollection(parsed)) {
    throw new Error("Upload a GeoJSON FeatureCollection or a zipped Shapefile.")
  }
  const collection = capPreviewFeatures(parsed)
  const trimmed = parsed.features.length - collection.features.length
  return {
    collection,
    label: `${collection.features.length.toLocaleString()} features loaded from GeoJSON.`,
    note: trimmed > 0 ? `Preview limited to ${collection.features.length.toLocaleString()} features for map speed.` : "",
  }
}

function ThermalCard({ status, error, running }: { status: ThermalStatus | null; error: string; running: boolean }) {
  if (error) {
    return (
      <div className="thermal-card unavailable">
        <AlertTriangle size={18} />
        <div>
          <strong>CPU temperature unavailable</strong>
          <span>{error}</span>
        </div>
      </div>
    )
  }
  if (!status) {
    return (
      <div className="thermal-card unavailable">
        <ShieldCheck size={18} />
        <div>
          <strong>Checking CPU temperature</strong>
          <span>Atlas is asking the local backend for a live reading.</span>
        </div>
      </div>
    )
  }
  const maxTemp = status.max_temp_c === null ? "Unavailable" : `${Math.round(status.max_temp_c)} C`
  const label = status.status === "hot" ? "CPU hot" : status.status === "warm" ? "CPU warm" : "CPU clear"
  const detail = running ? `${status.message} Live check refreshes while GeoQA runs.` : status.message
  return (
    <div className={`thermal-card ${status.status}`}>
      {status.status === "hot" ? <AlertTriangle size={18} /> : <ShieldCheck size={18} />}
      <div>
        <strong>{label}</strong>
        <span>{maxTemp}</span>
        <p>{detail}</p>
      </div>
    </div>
  )
}

function SelectedIssuePanel({
  issue,
  issueIndex,
  totalIssues,
  focusKind,
  focusNote,
  analyzed,
  selectedLayer,
  zipLayers,
  onPrevious,
  onNext,
}: {
  issue: Issue
  issueIndex: number
  totalIssues: number
  focusKind: string
  focusNote: string
  analyzed: FeatureCollection | null | undefined
  selectedLayer: string
  zipLayers: ShapefileLayerInfo[]
  onPrevious: () => void
  onNext: () => void
}) {
  const [showJson, setShowJson] = useState(false)
  const title = issue.problem_name.replaceAll("_", " ")
  const duplicateComparison = buildDuplicateComparison(issue, analyzed)
  const interpretation = getIssueInterpretation(issue, { selectedLayer, zipLayers })
  const statusCopy =
    focusKind === "layer"
      ? "Layer-level finding. This applies to the selected layer rather than one specific feature."
      : focusKind === "operational"
        ? "No map location is available for this run-level notice."
        : focusKind === "feature"
          ? "Map is focused on the issue or its analyzed feature."
          : focusNote || "No map location is available for this run-level notice."
  return (
    <aside className="selected-issue-panel" aria-label="Selected Run QA issue">
      <div className="selected-issue-header">
        <div>
          <span>Issue {Math.max(issueIndex + 1, 1)} of {Math.max(totalIssues, 1)}</span>
          <h3>{title}</h3>
        </div>
        <span className={`severity-pill ${String(issue.severity ?? "").toLowerCase()}`}>{issue.severity}</span>
      </div>
      <p>{issue.description}</p>
      <p className="issue-interpretation">{interpretation}</p>
      {duplicateComparison ? <DuplicateComparisonPanel comparison={duplicateComparison} /> : null}
      <p className="map-focus-status">{focusNote || statusCopy}</p>
      <div className="selected-issue-actions">
        <button className="mini-button" type="button" onClick={onPrevious}>
          Previous issue
        </button>
        <button className="mini-button" type="button" onClick={onNext}>
          Next issue
        </button>
        <button className="mini-button ghost" type="button" onClick={() => setShowJson((current) => !current)}>
          <FileJson size={15} />
          View raw JSON
        </button>
      </div>
      {showJson ? <pre className="raw-json">{JSON.stringify(issue, null, 2)}</pre> : null}
    </aside>
  )
}

function DuplicateComparisonPanel({ comparison }: { comparison: NonNullable<ReturnType<typeof buildDuplicateComparison>> }) {
  const changedRows = comparison.rows.filter((row) => row.differs)
  return (
    <div className="duplicate-comparison">
      <div className="comparison-summary">
        <strong>Duplicate feature comparison</strong>
        <span>
          Feature {comparison.leftId} compared with feature {comparison.rightId}
        </span>
        <small>
          {comparison.geometryType}. {comparison.coordinateSummary}
        </small>
        <small>{comparison.exactGeometryEqual ? "Geometries match exactly." : "Geometry differs from the matched row."}</small>
      </div>
      {comparison.rows.length ? (
        <div className="comparison-table-wrap">
          <table className="comparison-table">
            <thead>
              <tr>
                <th>Field</th>
                <th>Feature {comparison.leftId}</th>
                <th>Feature {comparison.rightId}</th>
              </tr>
            </thead>
            <tbody>
              {comparison.rows.map((row) => (
                <tr key={row.field} className={row.differs ? "differs" : ""}>
                  <th>{row.field}</th>
                  <td>{row.left}</td>
                  <td>{row.right}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <p>No comparable row attributes were available for the matched features.</p>
      )}
      {changedRows.length ? (
        <p className="comparison-note">
          {changedRows.length.toLocaleString()} attribute {changedRows.length === 1 ? "field differs" : "fields differ"} across the duplicated coordinates.
        </p>
      ) : (
        <p className="comparison-note">The compared attributes also match in the loaded preview.</p>
      )}
    </div>
  )
}

function featureCollectionToFile(collection: FeatureCollection, sourceName: string): File {
  const baseName = sourceName.replace(/\.[^.]+$/, "") || "uploaded-layer"
  const blob = new Blob([JSON.stringify(collection)], { type: "application/geo+json" })
  return new File([blob], `${baseName}-geoqa-analyzed.geojson`, { type: "application/geo+json" })
}

function fallbackAnalysisMetadata(featureCount: number, geometryType: string): PublicDemoAnalysisMetadata {
  return {
    analysisMode: "full_loaded_layer",
    featuresLoaded: featureCount,
    featuresAnalyzed: featureCount,
    analysisLimit: featureCount,
    fullLayerValidated: true,
    geometryType: geometryType || "Unknown",
    samplePolicy: "first_n_source_order",
  }
}

function boundsToFeature(boundsValue?: [number, number, number, number]): Feature<Geometry> | null {
  if (!boundsValue) return null
  const [minLng, minLat, maxLng, maxLat] = boundsValue
  if (![minLng, minLat, maxLng, maxLat].every(Number.isFinite)) return null
  return {
    type: "Feature",
    properties: {},
    geometry: {
      type: "Polygon",
      coordinates: [
        [
          [minLng, minLat],
          [maxLng, minLat],
          [maxLng, maxLat],
          [minLng, maxLat],
          [minLng, minLat],
        ],
      ],
    },
  }
}

function withAnalysisMetadata(payload: UploadQaResponse, metadata: PublicDemoAnalysisMetadata): UploadQaResponse {
  return {
    ...payload,
    analysisMode: metadata.analysisMode,
    featuresLoaded: metadata.featuresLoaded,
    featuresAnalyzed: metadata.featuresAnalyzed,
    analysisLimit: metadata.analysisLimit,
    fullLayerValidated: metadata.fullLayerValidated,
    geometryType: metadata.geometryType,
    samplePolicy: metadata.samplePolicy,
  }
}

function thermalFromResult(status: Partial<ThermalStatus>): ThermalStatus {
  const maxTemp = typeof status.max_temp_c === "number" ? status.max_temp_c : null
  const warnTemp = typeof status.warn_temp_c === "number" ? status.warn_temp_c : 78
  const hardTemp = typeof status.hard_temp_c === "number" ? status.hard_temp_c : 88
  const derivedStatus =
    maxTemp === null ? "unavailable" : maxTemp >= hardTemp ? "hot" : maxTemp >= warnTemp ? "warm" : "ok"
  const canRun = derivedStatus !== "hot"
  const message =
    typeof status.message === "string"
      ? status.message
      : maxTemp === null
        ? "CPU temperature is unavailable. Atlas can run QA but cannot show live heat."
        : `CPU temperature ended at ${Math.round(maxTemp)} C.`
  return {
    source: status.source ?? "unavailable",
    max_temp_c: maxTemp,
    avg_temp_c: typeof status.avg_temp_c === "number" ? status.avg_temp_c : null,
    sensor_count: typeof status.sensor_count === "number" ? status.sensor_count : 0,
    warn_temp_c: warnTemp,
    hard_temp_c: hardTemp,
    status: derivedStatus,
    can_run: canRun,
    message,
    runtime_seconds: status.runtime_seconds,
  }
}

function layerInfoFromParsed(layer: ParsedShapefileLayer, index: number): ShapefileLayerInfo {
  const geometryTypes = new Map<string, number>()
  layer.features.forEach((feature) => {
    const type = feature.geometry?.type ?? "Unknown"
    geometryTypes.set(type, (geometryTypes.get(type) ?? 0) + 1)
  })
  const rankedTypes = Array.from(geometryTypes.entries()).sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0]))
  const name = layer.fileName ? layer.fileName.replace(/\.[^.]+$/, "") : `Layer ${index + 1}`
  return {
    name,
    path: layer.fileName ?? name,
    feature_count: layer.features.length,
    geometry_type: rankedTypes[0]?.[0] ?? null,
    is_valid: true,
  }
}

function chooseDefaultLayer(layers: ShapefileLayerInfo[]) {
  const preferredTerms = ["pipes", "network", "assets", "hps", "dma", "aio", "boundaries", "parcels"]
  const scored = layers
    .filter((layer) => layer.is_valid !== false)
    .map((layer) => {
      const featureCount = layer.feature_count ?? 0
      const text = `${layer.name} ${layer.path}`.toLowerCase()
      const nameScore = preferredTerms.some((term) => text.includes(term)) ? 1 : 0
      return { layer, score: [featureCount > 0 ? 1 : 0, featureCount, nameScore] }
    })
  scored.sort((a, b) => b.score[0] - a.score[0] || b.score[1] - a.score[1] || b.score[2] - a.score[2])
  return scored[0]?.layer.name ?? ""
}

function formatLayerOption(layer: ShapefileLayerInfo) {
  const featureCount = typeof layer.feature_count === "number" ? `${layer.feature_count.toLocaleString()} features` : "feature count unknown"
  const geometryType = layer.geometry_type ?? "geometry unknown"
  const readable = layer.is_valid === false ? "not readable" : `${featureCount}, ${geometryType}`
  return `${layer.name} (${readable})`
}

function profileForLayer(layers: ShapefileLayerInfo[], layerName?: string | null) {
  if (!layerName) return ""
  const layer = layers.find((item) => item.name === layerName || item.path === layerName)
  const recommended = layer?.recommended_profile
  return recommended && profiles.includes(recommended) ? recommended : ""
}

function profileForGeometry(layers: ShapefileLayerInfo[], layerName?: string | null, collection?: FeatureCollection) {
  const layer = layerName ? layers.find((item) => item.name === layerName || item.path === layerName) : undefined
  return profilesForGeometry(layer?.geometry_type ?? (collection ? inferDominantGeometryType(collection) : ""))[0] ?? ""
}

function profilesForGeometry(geometryType?: string | null) {
  const normalized = String(geometryType ?? "").toLowerCase()
  if (normalized.includes("point")) {
    return ["point_asset_quick", "geometry"]
  }
  if (normalized.includes("line")) {
    return ["line_network_quick", "water_network_quick", "geometry"]
  }
  if (normalized.includes("polygon")) {
    return ["land_use_quick", "boundaries_quick", "geometry"]
  }
  return profiles
}

function shouldUseRecommendedProfile(recommendedProfile: string, geometryProfile: string) {
  return Boolean(recommendedProfile && recommendedProfile !== "generic_quick" && recommendedProfile !== geometryProfile)
}

function groupRunIssues(issues: Issue[]) {
  const grouped = new Map<string, Issue[]>()
  issues.forEach((issue) => {
    const key = issue.problem_name || "unknown_issue"
    grouped.set(key, [...(grouped.get(key) ?? []), issue])
  })
  return Array.from(grouped.entries()).map(([problemName, groupIssues]) => ({
    problemName,
    issues: groupIssues,
    examples: groupIssueExamples(groupIssues),
    severity: highestIssueSeverity(groupIssues),
  }))
}

function runGroupedIssueCopy(example: IssueExample) {
  const featureLabel = example.representative.feature_id ?? "Layer"
  if (example.counterpartFeatures.length) {
    return `Feature ${featureLabel} has ${example.issueCount} related findings with features ${example.counterpartFeatures.join(", ")}.`
  }
  return `Feature ${featureLabel} has ${example.issueCount} related findings.`
}

function highestIssueSeverity(issues: Issue[]) {
  const order = ["critical", "high", "medium", "low", "info"]
  const ranked = issues
    .map((issue) => String(issue.severity ?? "").toLowerCase())
    .filter((severity) => order.includes(severity))
    .sort((left, right) => order.indexOf(left) - order.indexOf(right))
  return ranked[0] || "review"
}

function isFeatureCollection(value: unknown): value is FeatureCollection {
  return Boolean(
    value &&
      typeof value === "object" &&
      (value as FeatureCollection).type === "FeatureCollection" &&
      Array.isArray((value as FeatureCollection).features),
  )
}

function capPreviewFeatures(collection: FeatureCollection): FeatureCollection {
  if (collection.features.length <= maxPreviewFeatures) return collection
  return {
    ...collection,
    features: collection.features.slice(0, maxPreviewFeatures),
  }
}
