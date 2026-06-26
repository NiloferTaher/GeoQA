import { lazy, Suspense } from "react"
import { NavLink, Route, Routes } from "react-router-dom"
import { ExternalLink, Map, PlayCircle } from "lucide-react"
import AppFooter from "./components/AppFooter"
import LoadingState from "./components/LoadingState"

const LandingPage = lazy(() => import("./pages/LandingPage"))
const DatasetGallery = lazy(() => import("./pages/DatasetGallery"))
const DatasetWorkspace = lazy(() => import("./pages/DatasetWorkspace"))
const RunQaPage = lazy(() => import("./pages/RunQaPage"))

export default function App() {
  return (
    <div className="app-shell">
      <header className="topbar">
        <NavLink to="/" className="brand" aria-label="GeoQA Atlas home">
          <span className="brand-mark">
            <Map size={18} />
          </span>
          <span>GeoQA Atlas</span>
        </NavLink>
        <nav className="nav-links" aria-label="Primary navigation">
          <NavLink to="/datasets">Datasets</NavLink>
          <NavLink to="/run">
            <PlayCircle size={16} />
            Run QA
          </NavLink>
          <a href="https://github.com/NiloferTaher/GeoQA" target="_blank" rel="noreferrer">
            <ExternalLink size={16} />
            GitHub
          </a>
          <a href="https://ae.linkedin.com/in/nilofertaher" target="_blank" rel="noreferrer">
            <ExternalLink size={16} />
            LinkedIn
          </a>
        </nav>
      </header>
      <main>
        <Suspense fallback={<LoadingState label="Loading Atlas page" />}>
          <Routes>
            <Route path="/" element={<LandingPage />} />
            <Route path="/datasets" element={<DatasetGallery />} />
            <Route path="/datasets/:datasetId" element={<DatasetWorkspace />} />
            <Route path="/run" element={<RunQaPage />} />
          </Routes>
        </Suspense>
      </main>
      <AppFooter />
    </div>
  )
}
