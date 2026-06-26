import assert from "node:assert/strict"
import { mkdtempSync, mkdirSync, readFileSync, writeFileSync } from "node:fs"
import { tmpdir } from "node:os"
import { dirname, join, resolve } from "node:path"
import ts from "typescript"

async function loadTsModule(filePath, replacements = {}) {
  let patched = readFileSync(resolve(filePath), "utf8")
  for (const [needle, replacement] of Object.entries(replacements)) {
    patched = patched.replaceAll(needle, replacement)
  }
  const output = ts.transpileModule(patched, {
    compilerOptions: {
      module: ts.ModuleKind.ESNext,
      target: ts.ScriptTarget.ES2022,
      strict: true,
    },
  }).outputText
  return import(`data:text/javascript;base64,${Buffer.from(output).toString("base64")}`)
}

async function loadPublicDemoModule({ publicDemo = "true", showThermal } = {}) {
  return loadTsModule("src/config/publicDemoLimits.ts", {
    "import.meta.env.VITE_ATLAS_PUBLIC_DEMO": JSON.stringify(publicDemo),
    "import.meta.env.VITE_ATLAS_SHOW_THERMAL": showThermal === undefined ? "undefined" : JSON.stringify(showThermal),
  })
}

async function loadBasemapModule(overrides = {}) {
  return loadTsModule("src/config/basemaps.ts", {
    "import.meta.env.VITE_ATLAS_TILE_URL": JSON.stringify(overrides.tileUrl ?? ""),
    "import.meta.env.VITE_ATLAS_LABEL_TILE_URL": JSON.stringify(overrides.labelTileUrl ?? ""),
    "import.meta.env.VITE_ATLAS_TILE_ATTRIBUTION": JSON.stringify(overrides.attribution ?? ""),
    "import.meta.env.VITE_ATLAS_DARK_TILE_URL": JSON.stringify(overrides.darkTileUrl ?? ""),
    "import.meta.env.VITE_ATLAS_DARK_LABEL_TILE_URL": JSON.stringify(overrides.darkLabelTileUrl ?? ""),
    "import.meta.env.VITE_ATLAS_DARK_TILE_ATTRIBUTION": JSON.stringify(overrides.darkAttribution ?? ""),
    "import.meta.env.VITE_ATLAS_LIGHT_TILE_URL": JSON.stringify(overrides.lightTileUrl ?? ""),
    "import.meta.env.VITE_ATLAS_LIGHT_LABEL_TILE_URL": JSON.stringify(overrides.lightLabelTileUrl ?? ""),
    "import.meta.env.VITE_ATLAS_LIGHT_TILE_ATTRIBUTION": JSON.stringify(overrides.lightAttribution ?? ""),
    "import.meta.env.VITE_ATLAS_SATELLITE_TILE_URL": JSON.stringify(overrides.satelliteTileUrl ?? ""),
    "import.meta.env.VITE_ATLAS_SATELLITE_LABEL_TILE_URL": JSON.stringify(overrides.satelliteLabelTileUrl ?? ""),
    "import.meta.env.VITE_ATLAS_SATELLITE_TILE_ATTRIBUTION": JSON.stringify(overrides.satelliteAttribution ?? ""),
  })
}

async function loadToggleModule() {
  return loadTsModule("src/config/mapLayerToggles.ts")
}

async function loadRunQaIssueModule() {
  const tempRoot = mkdtempSync(join(tmpdir(), "geoqa-atlas-tests-"))
  const files = [
    ["src/lib/geometry.ts", "src/lib/geometry.js"],
    ["src/lib/issues.ts", "src/lib/issues.js"],
    ["src/config/runQaIssueHelpers.ts", "src/config/runQaIssueHelpers.js"],
  ]
  for (const [sourcePath, outputPath] of files) {
    let source = readFileSync(resolve(sourcePath), "utf8")
    source = source
      .replaceAll("../lib/geometry", "../lib/geometry.js")
      .replaceAll("../lib/issues", "../lib/issues.js")
      .replaceAll("../types", "../types.js")
    const output = ts.transpileModule(source, {
      compilerOptions: {
        module: ts.ModuleKind.ESNext,
        target: ts.ScriptTarget.ES2022,
        strict: true,
      },
    }).outputText
    const target = join(tempRoot, outputPath)
    mkdirSync(dirname(target), { recursive: true })
    writeFileSync(target, output)
  }
  writeFileSync(join(tempRoot, "src/types.js"), "export {}\n")
  return import(`file:///${join(tempRoot, "src/config/runQaIssueHelpers.js").replaceAll("\\", "/")}`)
}

async function loadIssueModule() {
  return loadTsModule("src/lib/issues.ts")
}

async function loadExplainabilityModule() {
  return loadTsModule("src/config/runQaExplainability.ts")
}

async function loadEndpointModule() {
  return loadTsModule("src/lib/endpointIssues.ts")
}

async function loadMapBoundsModule() {
  const tempRoot = mkdtempSync(join(tmpdir(), "geoqa-atlas-map-bounds-tests-"))
  const files = [
    ["src/lib/geometry.ts", "src/lib/geometry.js"],
    ["src/lib/mapBounds.ts", "src/lib/mapBounds.js"],
  ]
  for (const [sourcePath, outputPath] of files) {
    let source = readFileSync(resolve(sourcePath), "utf8")
    source = source
      .replaceAll("../types", "../types.js")
      .replaceAll("./geometry", "./geometry.js")
    const output = ts.transpileModule(source, {
      compilerOptions: {
        module: ts.ModuleKind.ESNext,
        target: ts.ScriptTarget.ES2022,
        strict: true,
      },
    }).outputText
    const target = join(tempRoot, outputPath)
    mkdirSync(dirname(target), { recursive: true })
    writeFileSync(target, output)
  }
  writeFileSync(join(tempRoot, "src/types.js"), "export {}\n")
  return import(`file:///${join(tempRoot, "src/lib/mapBounds.js").replaceAll("\\", "/")}`)
}

async function loadModule({ publicDemo = "true", showThermal } = {}) {
  const source = readFileSync(resolve("src/config/publicDemoLimits.ts"), "utf8")
  const patched = source
    .replaceAll("import.meta.env.VITE_ATLAS_PUBLIC_DEMO", JSON.stringify(publicDemo))
    .replaceAll("import.meta.env.VITE_ATLAS_SHOW_THERMAL", showThermal === undefined ? "undefined" : JSON.stringify(showThermal))
  const output = ts.transpileModule(patched, {
    compilerOptions: {
      module: ts.ModuleKind.ESNext,
      target: ts.ScriptTarget.ES2022,
      strict: true,
    },
  }).outputText
  return import(`data:text/javascript;base64,${Buffer.from(output).toString("base64")}`)
}

function makeCollection(count, geometryType = "Point") {
  return {
    type: "FeatureCollection",
    features: Array.from({ length: count }, (_, index) => ({
      type: "Feature",
      properties: { id: index + 1 },
      geometry: geometryType === "Point"
        ? { type: "Point", coordinates: [58 + index * 0.01, 23 + index * 0.01] }
        : geometryType === "LineString"
          ? { type: "LineString", coordinates: [[58, 23], [58 + index * 0.01, 23 + index * 0.01]] }
          : { type: "Polygon", coordinates: [[[58, 23], [58.01, 23], [58.01, 23.01], [58, 23.01], [58, 23]]] },
    })),
  }
}

const defaults = await loadPublicDemoModule()

assert.equal(defaults.getPublicDemoAnalysisLimit("Point"), 20)
assert.equal(defaults.getPublicDemoAnalysisLimit("MultiPoint"), 20)
assert.equal(defaults.getPublicDemoAnalysisLimit("LineString"), 5)
assert.equal(defaults.getPublicDemoAnalysisLimit("MultiLineString"), 5)
assert.equal(defaults.getPublicDemoAnalysisLimit("Polygon"), 5)
assert.equal(defaults.getPublicDemoAnalysisLimit("MultiPolygon"), 5)
assert.equal(defaults.getPublicDemoAnalysisLimit("Unknown"), 5)

const eightyPoints = defaults.selectFeaturesForGeoQAAnalysis(makeCollection(80, "Point"), "Point")
assert.equal(eightyPoints.collection.features.length, 20)
assert.equal(eightyPoints.metadata.featuresLoaded, 80)
assert.equal(eightyPoints.metadata.featuresAnalyzed, 20)
assert.equal(eightyPoints.metadata.fullLayerValidated, false)
assert.equal(eightyPoints.collection.features[0].properties._geoqa_analyzed, true)
assert.equal(eightyPoints.collection.features[0].properties._geoqa_original_index, 0)

const sevenHundredThirtySixPoints = defaults.selectFeaturesForGeoQAAnalysis(makeCollection(736, "Point"), "Point")
assert.equal(sevenHundredThirtySixPoints.collection.features.length, 20)
assert.equal(sevenHundredThirtySixPoints.metadata.featuresLoaded, 736)
assert.equal(sevenHundredThirtySixPoints.metadata.featuresAnalyzed, 20)
assert.equal(sevenHundredThirtySixPoints.metadata.fullLayerValidated, false)

const oneHundredTwentyThreePolygons = defaults.selectFeaturesForGeoQAAnalysis(makeCollection(123, "Polygon"), "Polygon")
assert.equal(oneHundredTwentyThreePolygons.collection.features.length, 5)
assert.equal(oneHundredTwentyThreePolygons.metadata.featuresLoaded, 123)
assert.equal(oneHundredTwentyThreePolygons.metadata.featuresAnalyzed, 5)
assert.equal(oneHundredTwentyThreePolygons.metadata.fullLayerValidated, false)

const fiveThousandLines = defaults.selectFeaturesForGeoQAAnalysis(makeCollection(5000, "LineString"), "LineString")
assert.equal(fiveThousandLines.collection.features.length, 5)
assert.equal(fiveThousandLines.metadata.featuresLoaded, 5000)
assert.equal(fiveThousandLines.metadata.featuresAnalyzed, 5)
assert.equal(fiveThousandLines.metadata.fullLayerValidated, false)

const twelvePoints = defaults.selectFeaturesForGeoQAAnalysis(makeCollection(12, "Point"), "Point")
assert.equal(twelvePoints.collection.features.length, 12)
assert.equal(twelvePoints.metadata.fullLayerValidated, true)

assert.equal(
  defaults.getAnalysisSummaryText({ totalFeatures: 80, analyzedFeatures: 20, geometryType: "Point" }),
  "20 of 80 features analyzed by GeoQA in public demo mode.",
)
assert.equal(
  defaults.getNoIssueText(eightyPoints.metadata),
  "No issues found in the 20 GeoQA-analyzed features.",
)
assert.equal(defaults.showThermalCard, false)

const thermalVisible = await loadPublicDemoModule({ showThermal: "true" })
assert.equal(thermalVisible.showThermalCard, true)

const basemaps = await loadBasemapModule()
const defaultBasemap = basemaps.getAtlasBasemap()
assert.equal(defaultBasemap.name, "Atlas dark")
assert.ok(defaultBasemap.tileUrl.includes("cartocdn.com"))
assert.ok(defaultBasemap.labelTileUrl.includes("cartocdn.com"))
assert.ok(defaultBasemap.attribution.includes("OpenStreetMap"))
assert.equal(basemaps.getAtlasBasemaps().light.name, "Atlas light")
assert.equal(basemaps.getAtlasBasemaps().satellite.configured, false)

const overriddenBasemap = await loadBasemapModule({
  tileUrl: "https://tiles.example.test/{z}/{x}/{y}.png",
  labelTileUrl: "https://labels.example.test/{z}/{x}/{y}.png",
  attribution: "Example attribution",
  satelliteTileUrl: "https://satellite.example.test/{z}/{x}/{y}.jpg",
  satelliteAttribution: "Satellite attribution",
})
assert.equal(overriddenBasemap.getAtlasBasemap().tileUrl, "https://tiles.example.test/{z}/{x}/{y}.png")
assert.equal(overriddenBasemap.getAtlasBasemap().labelTileUrl, "https://labels.example.test/{z}/{x}/{y}.png")
assert.equal(overriddenBasemap.getAtlasBasemap().attribution, "Example attribution")
assert.equal(overriddenBasemap.getAtlasBasemap("satellite").tileUrl, "https://satellite.example.test/{z}/{x}/{y}.jpg")
assert.equal(overriddenBasemap.getAtlasBasemaps().satellite.configured, true)

const toggles = await loadToggleModule()
const noIssueVisibility = toggles.getDefaultRunQaLayerVisibility(0)
assert.deepEqual(noIssueVisibility, { raw: true, analyzed: true, issues: false })
const issueVisibility = toggles.getDefaultRunQaLayerVisibility(2)
assert.deepEqual(issueVisibility, { raw: true, analyzed: true, issues: true })
assert.equal(toggles.toggleRunQaLayerVisibility(issueVisibility, "raw", { issueCount: 2 }).raw, false)
assert.equal(toggles.toggleRunQaLayerVisibility(issueVisibility, "analyzed", { issueCount: 2 }).analyzed, false)
assert.equal(toggles.toggleRunQaLayerVisibility(issueVisibility, "issues", { issueCount: 2 }).issues, false)
assert.equal(toggles.toggleRunQaLayerVisibility(noIssueVisibility, "issues", { issueCount: 0 }).issues, false)

const issueHelpers = await loadRunQaIssueModule()
const issueLib = await loadIssueModule()
const explainability = await loadExplainabilityModule()
const endpointIssues = await loadEndpointModule()
const mapBounds = await loadMapBoundsModule()
assert.equal(issueHelpers.getIssueCountText(0), "No issues found in the GeoQA-analyzed features.")
assert.equal(issueHelpers.getIssueCountText(1), "1 issue found in the GeoQA-analyzed features.")
assert.equal(issueHelpers.getIssueCountText(4), "4 issues found in the GeoQA-analyzed features.")
assert.equal(issueHelpers.getSampledExecutionStatus("full", false), "demo sample")
assert.equal(issueHelpers.getSampledExecutionStatus("full", true), "full")
assert.equal(issueHelpers.isLayerLevelIssue({ problem_name: "missing_or_stale_spatial_index", feature_id: undefined }), true)

const datasetWorkspaceSource = readFileSync(resolve("src/pages/DatasetWorkspace.tsx"), "utf8")
const runQaSource = readFileSync(resolve("src/pages/RunQaPage.tsx"), "utf8")
const mapPanelSource = readFileSync(resolve("src/components/MapPanel.tsx"), "utf8")
const cssSource = readFileSync(resolve("src/index.css"), "utf8")
assert.equal(datasetWorkspaceSource.includes("selectFeaturesForGeoQAAnalysis"), false)
assert.equal(datasetWorkspaceSource.includes("mapMode=\"runQa\""), false)
assert.equal(runQaSource.includes("selectFeaturesForGeoQAAnalysis"), true)
assert.equal(runQaSource.includes("mapMode=\"runQa\""), true)
assert.equal(mapPanelSource.includes('mapMode = "dataset"'), true)
assert.equal(mapPanelSource.includes("runQaRawStyleFactory"), true)
assert.equal(mapPanelSource.includes("basemapKey"), true)

const malformedLine = {
  type: "FeatureCollection",
  features: [
    {
      type: "Feature",
      properties: { id: 1 },
      geometry: { type: "LineString", coordinates: [[58, 23], [null, 24]] },
    },
  ],
}
const sanitized = issueHelpers.sanitizeFeatureCollectionForGeoQA(malformedLine)
assert.equal(sanitized.features[0].geometry, null)

const nullGeometry = issueHelpers.sanitizeFeatureCollectionForGeoQA({
  type: "FeatureCollection",
  features: [{ type: "Feature", properties: { id: 1 }, geometry: null }],
})
assert.equal(nullGeometry.features[0].geometry, null)

const malformedMultiLine = issueHelpers.sanitizeFeatureCollectionForGeoQA({
  type: "FeatureCollection",
  features: [
    {
      type: "Feature",
      properties: { id: 1 },
      geometry: { type: "MultiLineString", coordinates: [[[58, 23], [59, 24]], [[60, null], [61, 25]]] },
    },
  ],
})
assert.equal(malformedMultiLine.features[0].geometry, null)

const analyzedSubset = {
  type: "FeatureCollection",
  features: [
    {
      type: "Feature",
      properties: { _geoqa_sample_index: 1, _geoqa_original_index: 0 },
      geometry: { type: "Point", coordinates: [58, 23] },
    },
  ],
}
const issue = {
  issue_id: "issue-1",
  problem_name: "null_geometry",
  severity: "medium",
  description: "Geometry is missing.",
  feature_id: 0,
}
assert.equal(issueHelpers.getIssueFocusKind({ ...issue, problem_name: "validation_runtime_error" }, { type: "FeatureCollection", features: [] }, analyzedSubset), "operational")
assert.equal(issueHelpers.getIssueFocusKind({ ...issue, problem_name: "missing_or_stale_spatial_index", feature_id: null }, { type: "FeatureCollection", features: [] }, analyzedSubset), "layer")
const fallbackOverlay = issueHelpers.buildIssueOverlayWithFallback({ type: "FeatureCollection", features: [] }, [issue], analyzedSubset)
assert.equal(fallbackOverlay.features.length, 1)
assert.equal(fallbackOverlay.features[0].geometry.type, "Point")
assert.equal(issueHelpers.getIssueFocusFeature(issue, fallbackOverlay, analyzedSubset).geometry.type, "Point")

const issueWithGeometry = {
  issue_id: "issue-direct",
  problem_name: "polygon_gap_same_layer",
  severity: "medium",
  description: "Gap detected.",
  feature_id: 0,
  geometry: { type: "LineString", coordinates: [[58, 23], [58.2, 23.2]] },
}
const directFocus = issueHelpers.getIssueFocusFeature(issueWithGeometry, { type: "FeatureCollection", features: [] }, analyzedSubset)
assert.equal(directFocus.geometry.type, "LineString")

const nonSpatialIssue = {
  issue_id: "issue-non-spatial",
  problem_name: "polygon_gap_same_layer",
  severity: "medium",
  description: "Operational note.",
  feature_id: "missing",
}
const firstSpatialIssue = issueHelpers.findFirstIssueForProblem(
  [nonSpatialIssue, issueWithGeometry],
  "polygon_gap_same_layer",
  { type: "FeatureCollection", features: [] },
  analyzedSubset,
)
assert.equal(firstSpatialIssue.issue_id, "issue-direct")

assert.equal(issueLib.isOperationalIssue({ problem_name: "validation_runtime_error" }), true)
assert.equal(issueLib.isOperationalIssue({ problem_name: "runtime_limit_exceeded" }), true)
assert.equal(issueLib.isOperationalIssue({ problem_name: "polygon_gap_same_layer" }), false)
assert.equal(issueLib.isNonVisualCleanedIssue({ problem_name: "coordinate_precision_not_fit_for_use" }), true)
assert.equal(issueLib.isNonVisualCleanedIssue({ problem_name: "missing_or_stale_spatial_index" }), true)
assert.equal(issueLib.isNonVisualCleanedIssue({ problem_name: "self_intersection" }), false)
const duplicateAnalyzed = {
  type: "FeatureCollection",
  features: [
    {
      type: "Feature",
      properties: { id: 3, asset_name: "Meter A", owner: "utility" },
      geometry: { type: "Point", coordinates: [58.1, 23.2] },
    },
    {
      type: "Feature",
      properties: { id: 8, asset_name: "Meter B", owner: "utility" },
      geometry: { type: "Point", coordinates: [58.1, 23.2] },
    },
  ],
}
const duplicateComparison = explainability.buildDuplicateComparison(
  {
    issue_id: "duplicate-1",
    problem_name: "duplicate_geometry_same_layer",
    severity: "medium",
    description: "Duplicate geometry.",
    feature_id: 3,
    provenance: { duplicate_feature_id: 8 },
  },
  duplicateAnalyzed,
)
assert.equal(explainability.isDuplicateIssue({ problem_name: "duplicate_geometry_same_layer", description: "" }), true)
assert.equal(duplicateComparison.exactGeometryEqual, true)
assert.equal(duplicateComparison.rows.some((row) => row.field === "asset_name" && row.differs), true)
const utilitySuggestions = explainability.getRunQaSuggestions({
  issues: [{ problem_name: "isolated_endpoint", description: "Endpoint", severity: "medium" }],
  selectedLayer: "Small_Network_Assets/Flow_Meter",
  zipLayers: [{ name: "AIO_Repetitive", path: "AIO_Repetitive", feature_count: 100, geometry_type: "LineString" }],
  analysisFullLayer: true,
})
assert.equal(utilitySuggestions.some((text) => text.includes("companion layer")), false)
const utilitySuggestionsWithoutCompanion = explainability.getRunQaSuggestions({
  issues: [{ problem_name: "isolated_endpoint", description: "Endpoint", severity: "medium" }],
  selectedLayer: "Small_Network_Assets/Flow_Meter",
  zipLayers: [{ name: "Other_Layer", path: "Other_Layer", feature_count: 100, geometry_type: "LineString" }],
  analysisFullLayer: true,
})
assert.equal(utilitySuggestionsWithoutCompanion.some((text) => text.includes("load related mains")), true)
const endpointIssue = {
  issue_id: "endpoint-1",
  problem_name: "suspicious_near_miss_endpoints",
  severity: "medium",
  description: "Near miss.",
  feature_id: "way/a",
  related_feature_id: "way/b",
  endpoint_a: [58.1, 23.2],
  endpoint_b: [58.1002, 23.2001],
  distance: 0.7,
  tolerance: 1,
  distance_units: "meters",
}
const endpointOverlay = endpointIssues.buildEndpointIssueOverlay(
  {
    type: "FeatureCollection",
    features: [
      {
        type: "Feature",
        properties: { issue_id: "endpoint-1", problem_name: "suspicious_near_miss_endpoints" },
        geometry: { type: "LineString", coordinates: [[58, 23], [59, 24]] },
      },
    ],
  },
  [endpointIssue],
)
assert.equal(endpointOverlay.features.length, 3)
assert.equal(endpointOverlay.features.filter((feature) => feature.geometry.type === "Point").length, 2)
assert.equal(endpointOverlay.features.filter((feature) => feature.properties.endpoint_pair === true).length, 3)
assert.deepEqual(endpointIssues.endpointIssueFocusFeature(endpointIssue).geometry.coordinates, [[58.1, 23.2], [58.1002, 23.2001]])
assert.equal(endpointIssues.endpointIssueDetails(endpointIssue).some((text) => text.includes("Gap distance")), true)
const duplicateExamples = issueLib.groupIssueExamples([
  {
    issue_id: "duplicate-1",
    problem_name: "duplicate_geometry_same_layer",
    severity: "medium",
    description: "Duplicate geometry.",
    feature_id: 3,
    provenance: { duplicate_feature_id: 8 },
  },
  {
    issue_id: "duplicate-2",
    problem_name: "duplicate_geometry_same_layer",
    severity: "medium",
    description: "Duplicate geometry.",
    feature_id: 3,
    provenance: { duplicate_feature_id: 12 },
  },
  {
    issue_id: "duplicate-3",
    problem_name: "duplicate_geometry_same_layer",
    severity: "medium",
    description: "Duplicate geometry.",
    feature_id: 4,
    provenance: { duplicate_feature_id: 3 },
  },
])
assert.equal(duplicateExamples.length, 2)
assert.equal(duplicateExamples[0].issueCount, 2)
assert.deepEqual(duplicateExamples[0].counterpartFeatures, [8, 12])
assert.equal(issueLib.featureIssuesOnly([{ problem_name: "validation_runtime_error" }, issueWithGeometry]).length, 1)

const demoConfig = JSON.parse(readFileSync(resolve("public/demo-data/datasets.json"), "utf8"))
const expectedDemoCounts = {
  "roads-line-network": [700, 88],
  "zoning-polygons": [420, 36],
  "administrative-boundaries-area-polygons": [4, 4],
  "flood-zones-risk-polygons": [4, 4],
  "water-network-utility-lines": [60, 162],
  "places-facilities": [243, 13],
}
for (const dataset of demoConfig.datasets) {
  const expected = expectedDemoCounts[dataset.id]
  assert.ok(expected, `Unexpected demo dataset ${dataset.id}`)
  assert.equal(dataset.feature_count, expected[0])
  assert.equal(dataset.issue_count, expected[1])
  const geojson = JSON.parse(readFileSync(resolve("public/demo-data", dataset.geojson), "utf8"))
  assert.equal(geojson.features.length, expected[0])
  const issueOverlay = JSON.parse(readFileSync(resolve("public/demo-data/issues", `${dataset.id}.json`), "utf8"))
  assert.ok(issueOverlay.features.length >= Math.min(expected[1], 5))
  assert.ok(dataset.cleaned_preview)
  assert.deepEqual(dataset.cleaned_preview.supportedIssueTypes, [])
  if (dataset.id === "roads-line-network" || dataset.id === "zoning-polygons") {
    assert.equal(dataset.has_cleaned_layer, false)
    assert.equal(dataset.cleaned_preview.available, false)
    assert.equal(dataset.cleaned_preview.meaningful, false)
    assert.ok(dataset.cleaned_layer_note.includes("no visible cleaned geometry preview"))
  }
  if (dataset.id === "water-network-utility-lines") {
    assert.equal(dataset.name, "OSM water / drainage lines")
    assert.ok(dataset.source_label.includes("OpenStreetMap contributors"))
    assert.equal(dataset.description.includes("synthetic"), false)
    assert.equal(dataset.mapView.fitTo, "issues")
    assert.deepEqual(dataset.mapView.padding, [28, 28])
    const report = JSON.parse(readFileSync(resolve("public/demo-data", dataset.report), "utf8"))
    const nearMiss = report.issues.find((issue) => issue.problem_name === "suspicious_near_miss_endpoints")
    assert.ok(Array.isArray(nearMiss.endpoint_a))
    assert.ok(Array.isArray(nearMiss.endpoint_b))
    assert.equal(nearMiss.geometry.type, "LineString")
    const geojson = JSON.parse(readFileSync(resolve("public/demo-data", dataset.geojson), "utf8"))
    const issueOverlay = JSON.parse(readFileSync(resolve("public/demo-data/issues", `${dataset.id}.json`), "utf8"))
    const resolvedMapView = mapBounds.resolveDatasetMapView({ dataset, raw: geojson, issues: issueOverlay, showRaw: true, showIssues: true })
    assert.ok(resolvedMapView.bounds[0] > dataset.bounds[0])
    assert.ok(resolvedMapView.bounds[2] < dataset.bounds[2])
    assert.equal(resolvedMapView.maxZoom, 12)
  }
}

const outlierCollection = {
  type: "FeatureCollection",
  features: [
    ...Array.from({ length: 40 }, (_, index) => ({
      type: "Feature",
      properties: { id: index },
      geometry: { type: "Point", coordinates: [58 + index * 0.001, 23 + index * 0.001] },
    })),
    {
      type: "Feature",
      properties: { id: "outlier" },
      geometry: { type: "Point", coordinates: [120, 60] },
    },
  ],
}
const robustOutlierView = mapBounds.resolveDatasetMapView({
  dataset: { bounds: [58, 23, 120, 60] },
  raw: outlierCollection,
})
assert.ok(robustOutlierView.bounds[2] < 120)

const roadsReport = JSON.parse(readFileSync(resolve("public/demo-data/reports/roads-line-network.json"), "utf8"))
assert.equal(roadsReport.issues.length, 88)
assert.equal(issueLib.featureIssuesOnly(roadsReport.issues).length, 87)

assert.equal(datasetWorkspaceSource.includes("featureIssuesOnly"), true)
assert.equal(datasetWorkspaceSource.includes("featureIssueFeaturesOnly"), true)
assert.equal(datasetWorkspaceSource.includes("getCleanedGeojson(datasetId)]"), false)
assert.equal(datasetWorkspaceSource.includes("if (!datasetId || !showCleaned || cleaned) return"), true)
assert.equal(runQaSource.includes("import shp from \"shpjs\""), false)
assert.equal(runQaSource.includes("await import(\"shpjs\")"), true)
assert.equal(mapPanelSource.includes("import \"leaflet/dist/leaflet.css\""), true)
assert.equal(mapPanelSource.includes('name={`${mapMode}-issue-layer`}'), true)
assert.equal(mapPanelSource.includes("zIndex: 760"), true)
assert.equal(mapPanelSource.includes("zIndex: 500"), true)
assert.equal(mapPanelSource.includes("filter: blur"), false)
assert.match(cssSource, /\.readable-map-labels\s*\{\s*filter: none;/)
assert.match(cssSource, /\.readable-basemap\s*\{\s*filter: none;/)
assert.equal(runQaSource.includes("SelectedIssuePanel"), true)
assert.equal(runQaSource.includes("Layer-level finding"), true)
assert.equal(runQaSource.includes("No map location is available for this issue."), false)
assert.equal(datasetWorkspaceSource.includes("buildEndpointIssueOverlay"), true)
assert.equal(datasetWorkspaceSource.includes("findRawFeatureForIssue"), true)
assert.equal(mapPanelSource.includes("endpoint_pair"), true)
assert.equal(mapPanelSource.includes('name={`${mapMode}-focus-layer`}'), true)
assert.equal(mapPanelSource.includes("function fitMaxZoom"), true)
assert.equal(mapPanelSource.includes("map.invalidateSize()"), true)
assert.equal(cssSource.includes(".endpoint-detail-list"), true)

console.log("public demo helper tests passed")
