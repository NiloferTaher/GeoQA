export type BasemapKey = "dark" | "light" | "satellite"

export type AtlasBasemap = {
  key: BasemapKey
  name: string
  tileUrl: string
  labelTileUrl?: string
  attribution: string
  configured: boolean
}

/**
 * Keyless basemaps.
 *
 * CARTO's `basemaps.cartocdn.com` endpoint now returns a watermarked
 * "API KEY REQUIRED" tile for every keyless request, which silently destroys
 * the map. The defaults below are Esri ArcGIS Online basemaps, which serve
 * real tiles with no account or API key. Every entry can still be overridden
 * with a VITE_ATLAS_* environment variable if you prefer another provider.
 */
const esriAttribution =
  "Tiles &copy; Esri &mdash; Esri, DeLorme, NAVTEQ, USGS, InterMap, iPC, NRCAN, Esri Japan, METI, Esri China (Hong Kong), Esri (Thailand), TomTom, &copy; OpenStreetMap contributors"

export const ATLAS_BASEMAPS = {
  dark: {
    key: "dark",
    name: "Atlas dark",
    tileUrl:
      "https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Dark_Gray_Base/MapServer/tile/{z}/{y}/{x}",
    labelTileUrl:
      "https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Dark_Gray_Reference/MapServer/tile/{z}/{y}/{x}",
    attribution: esriAttribution,
    configured: true,
  },
  light: {
    key: "light",
    name: "Atlas light",
    tileUrl:
      "https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Light_Gray_Base/MapServer/tile/{z}/{y}/{x}",
    labelTileUrl:
      "https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Light_Gray_Reference/MapServer/tile/{z}/{y}/{x}",
    attribution: esriAttribution,
    configured: true,
  },
  satellite: {
    key: "satellite",
    name: "Satellite",
    tileUrl:
      "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
    labelTileUrl: "",
    attribution: "Imagery &copy; Esri, Maxar, Earthstar Geographics",
    configured: true,
  },
} satisfies Record<BasemapKey, AtlasBasemap>

export function getAtlasBasemaps(): Record<BasemapKey, AtlasBasemap> {
  const dark = {
    ...ATLAS_BASEMAPS.dark,
    tileUrl:
      import.meta.env.VITE_ATLAS_DARK_TILE_URL ||
      import.meta.env.VITE_ATLAS_TILE_URL ||
      ATLAS_BASEMAPS.dark.tileUrl,
    labelTileUrl:
      import.meta.env.VITE_ATLAS_DARK_LABEL_TILE_URL ||
      import.meta.env.VITE_ATLAS_LABEL_TILE_URL ||
      ATLAS_BASEMAPS.dark.labelTileUrl,
    attribution:
      import.meta.env.VITE_ATLAS_DARK_TILE_ATTRIBUTION ||
      import.meta.env.VITE_ATLAS_TILE_ATTRIBUTION ||
      ATLAS_BASEMAPS.dark.attribution,
    configured: true,
  }
  const light = {
    ...ATLAS_BASEMAPS.light,
    tileUrl:
      import.meta.env.VITE_ATLAS_LIGHT_TILE_URL || ATLAS_BASEMAPS.light.tileUrl,
    labelTileUrl:
      import.meta.env.VITE_ATLAS_LIGHT_LABEL_TILE_URL || ATLAS_BASEMAPS.light.labelTileUrl,
    attribution:
      import.meta.env.VITE_ATLAS_LIGHT_TILE_ATTRIBUTION || ATLAS_BASEMAPS.light.attribution,
    configured: true,
  }
  const satelliteTileUrl =
    import.meta.env.VITE_ATLAS_SATELLITE_TILE_URL || ATLAS_BASEMAPS.satellite.tileUrl
  const satellite = {
    ...ATLAS_BASEMAPS.satellite,
    tileUrl: satelliteTileUrl,
    labelTileUrl: import.meta.env.VITE_ATLAS_SATELLITE_LABEL_TILE_URL || "",
    attribution:
      import.meta.env.VITE_ATLAS_SATELLITE_TILE_ATTRIBUTION ||
      ATLAS_BASEMAPS.satellite.attribution,
    configured: Boolean(satelliteTileUrl),
  }
  return { dark, light, satellite }
}

export function getAtlasBasemap(key: BasemapKey = "dark"): AtlasBasemap {
  const basemaps = getAtlasBasemaps()
  return basemaps[key]?.configured ? basemaps[key] : basemaps.dark
}
