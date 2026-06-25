import type { Dataset, DatasetListResponse, IssuesResponse, PreviewUploadResponse, Report } from "./types"
import type { FeatureCollection } from "geojson"

const API_BASE = import.meta.env.VITE_API_BASE ?? ""
const STATIC_BASE = "/demo-data"

function normalizeDataset(dataset: Dataset): Dataset {
  const cleanedGeojson = dataset.cleaned_geojson ?? dataset.cleanedGeoJsonPath
  const hasCleanedLayer = dataset.has_cleaned_layer ?? dataset.hasCleanedLayer ?? Boolean(cleanedGeojson)
  const cleanedLayerNote =
    dataset.cleaned_layer_note ??
    dataset.cleanedLayerNote ??
    (hasCleanedLayer
      ? "Cleaned preview available for supported geometry fixes only."
      : "No cleaned layer is available for this demo.")
  return {
    ...dataset,
    cleaned_geojson: cleanedGeojson,
    cleanedGeoJsonPath: cleanedGeojson,
    has_cleaned_layer: hasCleanedLayer,
    hasCleanedLayer,
    cleaned_layer_note: cleanedLayerNote,
    cleanedLayerNote,
  }
}

async function request<T>(path: string): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`)
  if (!response.ok) {
    const message = response.status === 404 ? "The requested GeoQA demo data was not found." : "GeoQA Atlas could not load this data."
    throw new Error(message)
  }
  return response.json() as Promise<T>
}

async function staticRequest<T>(path: string): Promise<T> {
  const response = await fetch(`${STATIC_BASE}${path}`)
  if (!response.ok) {
    throw new Error("GeoQA Atlas could not load its static demo data.")
  }
  return response.json() as Promise<T>
}

async function withStaticFallback<T>(apiPath: string, staticPath: string): Promise<T> {
  try {
    return await request<T>(apiPath)
  } catch {
    return staticRequest<T>(staticPath)
  }
}

export function listDatasets(): Promise<DatasetListResponse> {
  return withStaticFallback<DatasetListResponse>("/api/datasets", "/datasets.json").then((payload) => {
    const datasets = payload.datasets.map(normalizeDataset)
    if (payload.stats) return { datasets, stats: payload.stats }
    const checks = new Set(datasets.flatMap((dataset) => Object.keys(dataset.summary?.by_problem ?? { [dataset.profile]: 1 })))
    return {
      datasets,
      stats: {
        datasets: datasets.length,
        checks: checks.size,
        issues: datasets.reduce((total, dataset) => total + dataset.issue_count, 0),
      },
    }
  })
}

export function getDataset(id: string): Promise<Dataset> {
  return request<Dataset>(`/api/datasets/${id}`).catch(async () => {
    const payload = await staticRequest<DatasetListResponse>("/datasets.json")
    const dataset = payload.datasets.find((item) => item.id === id)
    if (!dataset) {
      throw new Error("The requested GeoQA demo data was not found.")
    }
    return normalizeDataset(dataset)
  })
}

export function getDatasetGeojson(id: string): Promise<FeatureCollection> {
  return request<FeatureCollection>(`/api/datasets/${id}/geojson`).catch(async () => {
    const dataset = await getDataset(id)
    if (!dataset.geojson) {
      throw new Error("Dataset preview is not available.")
    }
    return staticRequest<FeatureCollection>(`/${dataset.geojson}`)
  })
}

export function getCleanedGeojson(id: string): Promise<FeatureCollection> {
  return request<FeatureCollection>(`/api/datasets/${id}/cleaned-geojson`).catch(async () => {
    const dataset = await getDataset(id)
    if (!dataset.cleaned_geojson) {
      throw new Error("Cleaned layer is not available for this dataset.")
    }
    return staticRequest<FeatureCollection>(`/${dataset.cleaned_geojson}`)
  })
}

export function getReport(id: string): Promise<Report> {
  return withStaticFallback<Report>(`/api/datasets/${id}/report`, `/reports/${id}.json`)
}

export function getIssues(id: string): Promise<IssuesResponse> {
  return withStaticFallback<IssuesResponse>(`/api/datasets/${id}/issues`, `/issues/${id}.json`)
}

export function reportDownloadUrl(id: string): string {
  return `${STATIC_BASE}/reports/${id}.json`
}

export async function previewUploadedLayer(file: File): Promise<PreviewUploadResponse> {
  const response = await fetch(`${API_BASE}/api/preview-layer?filename=${encodeURIComponent(file.name)}`, {
    method: "POST",
    headers: {
      "Content-Type": "application/octet-stream",
    },
    body: file,
  })
  if (!response.ok) {
    throw new Error("GeoQA Atlas backend preview is not available for this file.")
  }
  return response.json() as Promise<PreviewUploadResponse>
}
