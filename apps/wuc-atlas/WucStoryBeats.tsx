// WucStoryBeats.tsx — stub for WUC-2027 one-page code→run→map→table+Peace Story
// Reuses Tanager cinematic SceneStage pattern: intro → data → take
// TODO: Wire to reports/wuc-2027/*.json and geo-qa-pi.vercel.app/wuc route
import { useState } from 'react'

export const WUC_DATASETS = [
  { id: 'ds1', name: 'Roads 56.6k (Natural Earth)', url: 'https://naciscdn.org/naturalearth/10m/cultural/ne_10m_roads.zip', story: 'Slide 1 GPS lost trust — 49 findings' },
  { id: 'ds2', name: 'Self-intersection polygon', url: 'data/public_samples/edge_cases/self_intersection_polygon.geojson', story: 'Slide 3 Annexation HALT' },
  { id: 'ds3', name: 'Water network (line)', url: 'edge_cases/duplicate_vertex_line.geojson (water_network profile)', story: 'Slide 2 Bulk clipping misassignment' },
  { id: 'ds4', name: 'Water network strict (polygon)', url: 'self_intersection_polygon (water_network strict)', story: 'Slide 7 50% majority-area rule' },
  { id: 'ds5', name: 'Spectral anomaly (NDVI spike)', url: 'synthetic Tanager VR-5: s2proxy +0.252 vs s2_actual -0.080', story: 'Spectral guardrail — cross-acquisition non-comparable' },
] as const

export function WucStoryBeats() {
  const [active] = useState('ds1')
  return (
    <div>
      <h2>Code → Run → Map → Table + Story (WUC-2027 stub)</h2>
      <p>Active: {active} — see reports/wuc-2027/*.json for committed tables.</p>
      <ul>
        {WUC_DATASETS.map(d => <li key={d.id}><b>{d.name}</b> — {d.url} — {d.story}</li>)}
      </ul>
      <p>Terminal animates: python -m geoqa validate &lt;URL&gt; --low-resource → wuc_run_log.csv replay</p>
    </div>
  )
}
