import assert from "node:assert/strict"
import { readFileSync } from "node:fs"
import { resolve } from "node:path"

function source(path) {
  return readFileSync(resolve(path), "utf8")
}

const appSource = source("src/App.tsx")
const mainSource = source("src/main.tsx")
const datasetSource = source("src/pages/DatasetWorkspace.tsx")
const gallerySource = source("src/pages/DatasetGallery.tsx")
const landingSource = source("src/pages/LandingPage.tsx")
const runQaSource = source("src/pages/RunQaPage.tsx")
const mapSource = source("src/components/MapPanel.tsx")

assert.equal(mainSource.includes("leaflet/dist/leaflet.css"), false, "Leaflet CSS must not be imported by the startup entry.")
assert.ok(appSource.includes("lazy(() => import(\"./pages/DatasetWorkspace\"))"), "Dataset workspace route must be lazy loaded.")
assert.ok(appSource.includes("lazy(() => import(\"./pages/RunQaPage\"))"), "Run QA route must be lazy loaded.")
assert.ok(datasetSource.includes("lazy(() => import(\"../components/MapPanel\"))"), "Dataset maps must be lazy loaded.")
assert.ok(runQaSource.includes("lazy(() => import(\"../components/MapPanel\"))"), "Run QA maps must be lazy loaded.")
assert.equal(runQaSource.includes("import shp from \"shpjs\""), false, "Shapefile parser must not be imported on Run QA page open.")
assert.ok(runQaSource.includes("await import(\"shpjs\")"), "Shapefile parser fallback must be user action driven.")
assert.equal(landingSource.includes("getDatasetGeojson"), false, "Landing page must not fetch demo GeoJSON.")
assert.equal(gallerySource.includes("getDatasetGeojson"), false, "Gallery page must not fetch demo GeoJSON.")
assert.equal(gallerySource.includes("MapPanel"), false, "Gallery page must not mount maps.")
assert.ok(datasetSource.includes("Promise.all([getDataset(datasetId), getDatasetGeojson(datasetId), getIssues(datasetId), getReport(datasetId)]"), "Dataset route should fetch only the selected dataset files.")
assert.equal(datasetSource.includes("getCleanedGeojson(datasetId)]"), false, "Cleaned GeoJSON must not be part of initial dataset loading.")
assert.ok(datasetSource.includes("if (!datasetId || !showCleaned || cleaned) return"), "Cleaned GeoJSON must be gated by the cleaned layer toggle.")
assert.ok(mapSource.includes("raw && showRaw"), "Raw map layer must render only when visible.")
assert.ok(mapSource.includes("issues && showIssues"), "Issue map layer must render only when visible.")
assert.ok(mapSource.includes("cleaned && showCleaned"), "Cleaned map layer must render only when visible.")

console.log("idle safety checks passed")
