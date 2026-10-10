declare module "shpjs" {
  import type { FeatureCollection } from "geojson"

  export type ShpjsFeatureCollection = FeatureCollection & {
    fileName?: string
  }

  export default function shp(input: string | ArrayBuffer | ArrayBufferView | Record<string, unknown>): Promise<
    ShpjsFeatureCollection | ShpjsFeatureCollection[]
  >
}
