import type { CleanedPreview, Dataset, DatasetListResponse, IssuesResponse, PreviewUploadResponse, Report, ThermalStatus, UploadQaResponse } from "./types"
import type { FeatureCollection } from "geojson"

const API_BASE = import.meta.env.VITE_API_BASE ?? ""
const STATIC_BASE = "/demo-data"

function normalizeDataset(dataset: Dataset): Dataset {
  const cleanedGeojson = dataset.cleaned_geojson ?? dataset.cleanedGeoJsonPath
  const preview = normalizeCleanedPreview(dataset, cleanedGeojson)
  const hasCleanedLayer = preview.available && preview.meaningful
  const cleanedLayerNote =
    preview.note ??
    dataset.cleaned_layer_note ??
    dataset.cleanedLayerNote ??
    "No cleaned preview is available for this demo."
  return {
    ...dataset,
    cleaned_geojson: preview.path ?? cleanedGeojson,
    cleanedGeoJsonPath: preview.path ?? cleanedGeojson,
    has_cleaned_layer: hasCleanedLayer,
    hasCleanedLayer,
    cleaned_layer_note: cleanedLayerNote,
    cleanedLayerNote,
    cleaned_preview: preview,
    cleanedPreview: preview,
  }
}

function normalizeCleanedPreview(dataset: Dataset, cleanedGeojson?: string): CleanedPreview {
  const preview = dataset.cleaned_preview ?? dataset.cleanedPreview
  const supportedIssueTypes = preview?.supportedIssueTypes ?? preview?.supported_issue_types ?? []
  if (preview) {
    return {
      available: Boolean(preview.available),
      meaningful: Boolean(preview.meaningful),
      path: preview.path ?? cleanedGeojson,
      supportedIssueTypes,
      supported_issue_types: supportedIssueTypes,
      note: preview.note || "No cleaned preview is available for this demo.",
    }
  }
  const legacyAvailable = dataset.has_cleaned_layer ?? dataset.hasCleanedLayer ?? Boolean(cleanedGeojson)
  return {
    available: Boolean(legacyAvailable),
    meaningful: Boolean(legacyAvailable),
    path: cleanedGeojson,
    supportedIssueTypes: [],
    supported_issue_types: [],
    note: legacyAvailable ? "Cleaned preview is available for supported geometry fixes." : "No cleaned preview is available for this demo.",
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

export async function getThermalStatus(): Promise<ThermalStatus> {
  return request<ThermalStatus>("/api/thermal")
}

export async function previewUploadedLayer(file: File, layer?: string): Promise<PreviewUploadResponse> {
  const params = new URLSearchParams({ filename: file.name })
  if (layer) params.set("layer", layer)
  const response = await fetch(`${API_BASE}/api/preview-layer?${params.toString()}`, {
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

export async function runUploadedQa(file: File, profile: string, layer?: string): Promise<UploadQaResponse> {
  const params = new URLSearchParams({ filename: file.name, profile })
  if (layer) params.set("layer", layer)
  const controller = new AbortController()
  const timeout = window.setTimeout(() => controller.abort(), 300000)
  let response: Response
  try {
    response = await fetch(`${API_BASE}/api/run-qa?${params.toString()}`, {
      method: "POST",
      headers: {
        "Content-Type": "application/octet-stream",
      },
      body: file,
      signal: controller.signal,
    })
  } catch (error) {
    if (error instanceof DOMException && error.name === "AbortError") {
      throw new Error("GeoQA Atlas did not finish this QA run within five minutes. Try a smaller layer or a more specific profile.")
    }
    throw error
  } finally {
    window.clearTimeout(timeout)
  }
  if (!response.ok) {
    let message = "GeoQA Atlas could not run QA on this layer."
    try {
      const payload = await response.json()
      if (typeof payload?.detail === "string") message = payload.detail
    } catch {
      // Keep the generic message when the backend does not return JSON.
    }
    throw new Error(message)
  }
  return response.json() as Promise<UploadQaResponse>
}
