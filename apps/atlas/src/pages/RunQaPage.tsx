import { useMemo, useState } from "react"
import { CheckCircle2, FileJson, Layers3, MapPinned, ShieldCheck, UploadCloud } from "lucide-react"
import type { FeatureCollection } from "geojson"
import MapPanel from "../components/MapPanel"
import ErrorState from "../components/ErrorState"

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
  const [error, setError] = useState("")

  const bounds = useMemo(() => (preview ? inferBounds(preview) : undefined), [preview])

  function handleUpload(file?: File) {
    setError("")
    setPreview(null)
    if (!file) return
    setFileName(file.name)
    const reader = new FileReader()
    reader.onload = () => {
      try {
        const parsed = JSON.parse(String(reader.result))
        if (parsed?.type !== "FeatureCollection" || !Array.isArray(parsed.features)) {
          throw new Error("Upload a GeoJSON FeatureCollection for this workflow preview.")
        }
        setPreview(parsed as FeatureCollection)
      } catch (caught) {
        setError(caught instanceof Error ? caught.message : "GeoQA Atlas could not read this GeoJSON file.")
      }
    }
    reader.readAsText(file)
  }

  return (
    <div className="page narrow-page run-page">
      <section className="page-heading run-heading">
        <p className="eyebrow">Atlas workflow preview</p>
        <h1>Run QA on your own layer</h1>
        <p>
          Upload a dataset, choose a GeoQA profile, review findings on the map, apply conservative fixes, and download
          the report or cleaned layer.
        </p>
      </section>

      <section className="run-notice">
        <ShieldCheck size={20} />
        <p>Full validation requires the GeoQA Python backend. This page is the Atlas upload workflow preview.</p>
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
              accept=".geojson,.json,application/geo+json,application/json"
              onChange={(event) => handleUpload(event.target.files?.[0])}
            />
            <FileJson size={28} />
            <span>{fileName || "Choose a GeoJSON FeatureCollection"}</span>
          </label>
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
            overlays, and expose any conservative cleaned output for download.
          </p>
        </div>
      </section>
    </div>
  )
}
