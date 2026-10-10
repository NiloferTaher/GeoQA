import { useEffect, useState } from "react"
import { ArrowRight, Braces, Layers3, MapPinned, ShieldAlert } from "lucide-react"
import { Link } from "react-router-dom"
import { listDatasets } from "../api"
import type { Dataset } from "../types"
import ErrorState from "../components/ErrorState"
import LoadingState from "../components/LoadingState"

export default function DatasetGallery() {
  const [datasets, setDatasets] = useState<Dataset[]>([])
  const [error, setError] = useState("")
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    listDatasets()
      .then((payload) => setDatasets(payload.datasets))
      .catch((caught: Error) => setError(caught.message))
      .finally(() => setLoading(false))
  }, [])

  return (
    <div className="page narrow-page">
      <section className="page-heading">
        <p className="eyebrow">Demo dataset gallery</p>
        <h1>Pick a layer. See what GeoQA found.</h1>
        <p>
          Each dataset is a curated public preview with a precomputed GeoQA report, issue overlay, and reproducible
          command.
        </p>
      </section>
      {loading ? <LoadingState /> : null}
      {error ? <ErrorState message={error} /> : null}
      <section className="dataset-grid" aria-label="Demo datasets">
        {datasets.map((dataset) => (
          <article className="dataset-card" key={dataset.id}>
            <div className="dataset-card-top">
              <span className="dataset-icon">
                <MapPinned size={22} />
              </span>
              <span className="profile-badge">{dataset.profile}</span>
            </div>
            <h2>{dataset.name}</h2>
            <p>{dataset.description}</p>
            <dl className="dataset-facts">
              <div>
                <dt>
                  <Layers3 size={15} />
                  Features
                </dt>
                <dd>{dataset.feature_count.toLocaleString()}</dd>
              </div>
              <div>
                <dt>
                  <Braces size={15} />
                  Geometry
                </dt>
                <dd>{dataset.geometry_type}</dd>
              </div>
              <div>
                <dt>
                  <ShieldAlert size={15} />
                  Issues
                </dt>
                <dd>{dataset.issue_count.toLocaleString()}</dd>
              </div>
            </dl>
            <Link to={`/datasets/${dataset.id}`} className="secondary-cta">
              Explore
              <ArrowRight size={17} />
            </Link>
          </article>
        ))}
      </section>
    </div>
  )
}
