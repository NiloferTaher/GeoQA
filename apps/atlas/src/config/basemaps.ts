export type BasemapKey = "dark" | "light" | "satellite"

export type AtlasBasemap = {
  key: BasemapKey
  name: string
  tileUrl: string
  labelTileUrl?: string
  attribution: string
  configured: boolean
  className?: string
}

const blackMapAttribution = "&copy; OpenStreetMap contributors"
const cartoAttribution = "&copy; OpenStreetMap contributors &copy; CARTO"

export const ATLAS_BASEMAPS = {
  dark: {
    key: "dark",
    name: "Atlas dark",
    tileUrl: "https://tile.openstreetmap.org/{z}/{x}/{y}.png",
    labelTileUrl: "",
    attribution: "&copy; OpenStreetMap contributors",
    configured: true,
    className: "dark-map-tiles",
  },
  light: {
    key: "light",
    name: "Atlas light",
    tileUrl: "https://{s}.basemaps.cartocdn.com/rastertiles/voyager_nolabels/{z}/{x}/{y}{r}.png",
    labelTileUrl: "https://{s}.basemaps.cartocdn.com/rastertiles/voyager_only_labels/{z}/{x}/{y}{r}.png",
    attribution: cartoAttribution,
    configured: true,
  },
  satellite: {
    key: "satellite",
    name: "Satellite",
    tileUrl: "https://mt1.google.com/vt/lyrs=s&x={x}&y={y}&z={z}",
    labelTileUrl: "",
    attribution: "Imagery (C) Google",
    configured: true,
  },
} satisfies Record<BasemapKey, AtlasBasemap>

export function getAtlasBasemaps(): Record<BasemapKey, AtlasBasemap> {
  const dark = {
    ...ATLAS_BASEMAPS.dark,
    tileUrl: ATLAS_BASEMAPS.dark.tileUrl,
    labelTileUrl: ATLAS_BASEMAPS.dark.labelTileUrl,
    attribution: ATLAS_BASEMAPS.dark.attribution,
    configured: true,
  }
  const light = {
    ...ATLAS_BASEMAPS.light,
    tileUrl: import.meta.env.VITE_ATLAS_LIGHT_TILE_URL || ATLAS_BASEMAPS.light.tileUrl,
    labelTileUrl: import.meta.env.VITE_ATLAS_LIGHT_LABEL_TILE_URL || ATLAS_BASEMAPS.light.labelTileUrl,
    attribution: import.meta.env.VITE_ATLAS_LIGHT_TILE_ATTRIBUTION || ATLAS_BASEMAPS.light.attribution,
    configured: true,
  }
  const satelliteTileUrl = "https://mt1.google.com/vt/lyrs=s&x={x}&y={y}&z={z}"
  const satellite = {
    ...ATLAS_BASEMAPS.satellite,
    tileUrl: satelliteTileUrl,
    labelTileUrl: import.meta.env.VITE_ATLAS_SATELLITE_LABEL_TILE_URL || "",
    attribution: "Imagery (C) Google",
    configured: Boolean(satelliteTileUrl),
  }
  return { dark, light, satellite }
}

export function getAtlasBasemap(key: BasemapKey = "dark"): AtlasBasemap {
  const basemaps = getAtlasBasemaps()
  return basemaps[key]?.configured ? basemaps[key] : basemaps.dark
}
