import { useEffect, useState } from "react"
import { ArrowRight, Database, Gauge, Layers3, MapPinned, ShieldAlert, Workflow } from "lucide-react"
import { Link } from "react-router-dom"
import { listDatasets } from "../api"
import type { DatasetListResponse } from "../types"
import ErrorState from "../components/ErrorState"
import HeroGlobe from "../components/HeroGlobe"
import LoadingState from "../components/LoadingState"

export default function LandingPage() {
  const [data, setData] = useState<DatasetListResponse | null>(null)
  const [error, setError] = useState("")

  useEffect(() => {
    listDatasets().then(setData).catch((caught: Error) => setError(caught.message))
  }, [])

  return (
    <div className="page">
      <section className="hero">
        <div className="hero-grid" aria-hidden="true" />
        <div className="hero-orbit" aria-hidden="true" />
        <div className="hero-content">
          <p className="eyebrow">Powered by GeoQA</p>
          <h1>Trust your geospatial data before analysis.</h1>
          <p className="hero-subtitle">
            GeoQA Atlas turns GeoQA reports into map-first QA review workflows for layers, attributes, and delivery
            risk.
          </p>
          <div className="hero-actions">
            <Link to="/datasets" className="primary-cta">
              Explore demo datasets
              <ArrowRight size={18} />
            </Link>
            <a className="secondary-cta" href="https://github.com/NiloferTaher/GeoQA" target="_blank" rel="noreferrer">
              View GitHub
            </a>
          </div>
        </div>
        <div className="hero-visual" aria-label="GeoQA Atlas visual summary">
          <HeroGlobe />
          {error ? <ErrorState message={error} /> : null}
          {!data && !error ? <LoadingState label="Loading demo stats" /> : null}
          {data ? (
            <div className="stat-grid">
              <article className="stat-card">
                <Database size={22} />
                <span>Datasets</span>
                <strong>{data.stats?.datasets}</strong>
              </article>
              <article className="stat-card">
                <Gauge size={22} />
                <span>Checks</span>
                <strong>{data.stats?.checks}</strong>
              </article>
              <article className="stat-card">
                <ShieldAlert size={22} />
                <span>Issues</span>
                <strong>{data.stats?.issues}</strong>
              </article>
            </div>
          ) : null}
        </div>
      </section>
      <section className="platform-section" aria-label="GeoQA Atlas platform shell">
        <div className="section-heading">
          <p className="eyebrow">Interactive QA workspace</p>
          <h2>One workspace, many spatial QA modules.</h2>
          <p>
            GeoQA Atlas keeps the interface shared while each dataset plugs in its own profile, report, source, and map
            layers.
          </p>
        </div>
        <div className="platform-grid">
          <article className="platform-card">
            <Workflow size={22} />
            <h3>Core workflow</h3>
            <p>Landing, gallery, workspace, report inspector, and download flow stay consistent across datasets.</p>
          </article>
          <article className="platform-card">
            <Layers3 size={22} />
            <h3>Dataset modules</h3>
            <p>Roads, zoning, water networks, and places use the same viewer with metadata driven cards and overlays.</p>
          </article>
          <article className="platform-card">
            <MapPinned size={22} />
            <h3>Map first review</h3>
            <p>QA signals are shown as map layers and simple summaries before users inspect the issue table.</p>
          </article>
        </div>
      </section>
      <section className="engine-section" aria-label="Open source GeoQA engine">
        <div className="engine-copy">
          <p className="eyebrow">Open-source engine positioning</p>
          <h2>Powered by the open-source GeoQA engine</h2>
          <p>
            Atlas is the visual report explorer. GeoQA remains the deterministic CLI and Python engine underneath,
            producing structured JSON and CSV reports without LLM geometry guessing.
          </p>
          <ul className="engine-list">
            <li>CLI-first workflows</li>
            <li>Python API</li>
            <li>Deterministic validation rules</li>
            <li>Structured JSON and CSV reports</li>
          </ul>
        </div>
        <pre className="engine-code">
          <code>{`import geoqa

report = geoqa.validate("data.geojson", profile="generic_quick")
print(report.summary)

cleaned = report.clean()
cleaned.export("cleaned.geojson")`}</code>
        </pre>
      </section>
    </div>
  )
}
