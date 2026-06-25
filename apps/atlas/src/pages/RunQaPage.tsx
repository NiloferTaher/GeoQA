import { useMemo, useState } from "react"
import { CheckCircle2, FileJson, Layers3, MapPinned, ShieldCheck, UploadCloud } from "lucide-react"
import type { FeatureCollection } from "geojson"
import shp from "shpjs"
import MapPanel from "../components/MapPanel"
import ErrorState from "../components/ErrorState"
import { previewUploadedLayer } from "../api"

const profiles = ["generic_quick", "geometry", "water_network_quick", "land_use_quick", "boundaries_quick"]

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

function inferBounds(collection: FeatureCollection): [number, number, number, number] | undefined {
  const positions: Array<[number, number]> = []
  const visit = (value: unknown) => {
    if (!Array.isArray(value)) return
    if (typeof value[0] === "number" && typeof value[1] === "number") {
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

export default function RunQaPage() {
  const [profile, setProfile] = useState(profiles[0])
  const [preview, setPreview] = useState<FeatureCollection | null>(null)
  const [fileName, setFileName] = useState("")
  const [previewLabel, setPreviewLabel] = useState("")
  const [uploadNote, setUploadNote] = useState("")
  const [processing, setProcessing] = useState(false)
  const [error, setError] = useState("")

  const bounds = useMemo(() => (preview ? inferBounds(preview) : undefined), [preview])

  async function handleUpload(file?: File) {
    setError("")
    setPreview(null)
    setPreviewLabel("")
    setUploadNote("")
    if (!file) return
    setFileName(file.name)
    setProcessing(true)
    try {
      const parsed = await parsePreviewFile(file)
      setPreview(parsed.collection)
      setPreviewLabel(parsed.label)
      setUploadNote(parsed.note)
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "GeoQA Atlas could not read this layer preview.")
    } finally {
      setProcessing(false)
    }
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
          <label className="field-label" htmlFor="profile-select">
            GeoQA profile
          </label>
          <select id="profile-select" value={profile} onChange={(event) => setProfile(event.target.value)}>
            {profiles.map((item) => (
              <option key={item} value={item}>
                {item}
              </option>
            ))}
          </select>
          <pre className="command-preview">
            <code>{command.replace("generic_quick", profile)}</code>
          </pre>
        </article>

        <article className="run-panel map-preview-panel">
          <div className="panel-title-row">
            <MapPinned size={21} />
            <h2>Map preview</h2>
          </div>
          {preview ? (
            <MapPanel
              raw={preview}
              bounds={bounds}
              showRaw
              showIssues={false}
              showCleaned={false}
            />
          ) : (
            <div className="empty-preview">
              <Layers3 size={34} />
              <p>Your uploaded GeoJSON layer will appear here before validation runs.</p>
            </div>
          )}
        </article>
      </section>

      <section className="run-outcome">
        <CheckCircle2 size={22} />
        <div>
          <h2>What the backend will add</h2>
          <p>
            The connected backend will call the GeoQA Python engine, write a structured JSON report, return issue
            overlays, and expose any conservative cleaned output for supported geometry fixes.
          </p>
        </div>
      </section>
    </div>
  )
}

async function parsePreviewFile(file: File) {
  const lowerName = file.name.toLowerCase()
  if (lowerName.endsWith(".zip")) {
    if (file.size >= backendZipPreviewThreshold) {
      try {
        return await previewUploadedLayer(file)
      } catch {
        throw new Error(
          "This large zipped Shapefile needs the local GeoQA Atlas backend preview. Smaller zipped Shapefiles can still be parsed in the browser.",
        )
      }
    }
    const buffer = await file.arrayBuffer()
    const parsed = await shp(buffer)
    const layers = (Array.isArray(parsed) ? parsed : [parsed]) as ParsedShapefileLayer[]
    const usable = layers.find((layer) => layer?.type === "FeatureCollection" && Array.isArray(layer.features))
    if (!usable) {
      throw new Error("This zip did not include a readable Shapefile layer for browser preview.")
    }
    const layerName = usable.fileName ? usable.fileName.split(/[\\/]/).pop() : file.name
    const collection = capPreviewFeatures(usable)
    const trimmed = usable.features.length - collection.features.length
    const layerNote =
      layers.length > 1
        ? `This zip contains ${layers.length} shapefile layers. Atlas is previewing ${layerName}.`
        : `Atlas is previewing ${layerName}.`
    const trimNote = trimmed > 0 ? ` Preview limited to ${collection.features.length.toLocaleString()} features for map speed.` : ""
    return {
      collection,
      label: `${collection.features.length.toLocaleString()} features loaded from zipped Shapefile.`,
      note: `${layerNote}${trimNote}`,
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
