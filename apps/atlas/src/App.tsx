import { NavLink, Route, Routes } from "react-router-dom"
import { ExternalLink, Map, PlayCircle } from "lucide-react"
import DatasetGallery from "./pages/DatasetGallery"
import DatasetWorkspace from "./pages/DatasetWorkspace"
import LandingPage from "./pages/LandingPage"
import RunQaPage from "./pages/RunQaPage"

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
        </nav>
      </header>
      <main>
        <Routes>
          <Route path="/" element={<LandingPage />} />
          <Route path="/datasets" element={<DatasetGallery />} />
          <Route path="/datasets/:datasetId" element={<DatasetWorkspace />} />
          <Route path="/run" element={<RunQaPage />} />
        </Routes>
      </main>
    </div>
  )
}
