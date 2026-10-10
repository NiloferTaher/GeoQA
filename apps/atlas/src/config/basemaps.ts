export type BasemapKey = "dark" | "light" | "satellite"

export type AtlasBasemap = {
  key: BasemapKey
  name: string
  tileUrl: string
  labelTileUrl?: string
  attribution: string
  configured: boolean
}

const cartoAttribution = "&copy; OpenStreetMap contributors &copy; CARTO"

export const ATLAS_BASEMAPS = {
  dark: {
    key: "dark",
    name: "Atlas dark",
    tileUrl: "https://{s}.basemaps.cartocdn.com/dark_nolabels/{z}/{x}/{y}{r}.png",
    labelTileUrl: "https://{s}.basemaps.cartocdn.com/rastertiles/voyager_only_labels/{z}/{x}/{y}{r}.png",
    attribution: cartoAttribution,
    configured: true,
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
    tileUrl: "",
    labelTileUrl: "",
    attribution: "",
    configured: false,
  },
} satisfies Record<BasemapKey, AtlasBasemap>

export function getAtlasBasemaps(): Record<BasemapKey, AtlasBasemap> {
  const dark = {
    ...ATLAS_BASEMAPS.dark,
    tileUrl: import.meta.env.VITE_ATLAS_DARK_TILE_URL || import.meta.env.VITE_ATLAS_TILE_URL || ATLAS_BASEMAPS.dark.tileUrl,
    labelTileUrl:
      import.meta.env.VITE_ATLAS_DARK_LABEL_TILE_URL || import.meta.env.VITE_ATLAS_LABEL_TILE_URL || ATLAS_BASEMAPS.dark.labelTileUrl,
    attribution:
      import.meta.env.VITE_ATLAS_DARK_TILE_ATTRIBUTION || import.meta.env.VITE_ATLAS_TILE_ATTRIBUTION || ATLAS_BASEMAPS.dark.attribution,
    configured: true,
  }
  const light = {
    ...ATLAS_BASEMAPS.light,
    tileUrl: import.meta.env.VITE_ATLAS_LIGHT_TILE_URL || ATLAS_BASEMAPS.light.tileUrl,
    labelTileUrl: import.meta.env.VITE_ATLAS_LIGHT_LABEL_TILE_URL || ATLAS_BASEMAPS.light.labelTileUrl,
    attribution: import.meta.env.VITE_ATLAS_LIGHT_TILE_ATTRIBUTION || ATLAS_BASEMAPS.light.attribution,
    configured: true,
  }
  const satelliteTileUrl = import.meta.env.VITE_ATLAS_SATELLITE_TILE_URL || ""
  const satellite = {
    ...ATLAS_BASEMAPS.satellite,
    tileUrl: satelliteTileUrl,
    labelTileUrl: import.meta.env.VITE_ATLAS_SATELLITE_LABEL_TILE_URL || "",
    attribution: import.meta.env.VITE_ATLAS_SATELLITE_TILE_ATTRIBUTION || "",
    configured: Boolean(satelliteTileUrl),
  }
  return { dark, light, satellite }
}

export function getAtlasBasemap(key: BasemapKey = "dark"): AtlasBasemap {
  const basemaps = getAtlasBasemaps()
  return basemaps[key]?.configured ? basemaps[key] : basemaps.dark
}
