import type { MapPoint } from './types'

/** The top tenth of analysed PRs by hybrid score (shared by the story map and its text). */
export interface StoryStats {
  topCut: number // hybrid score at the top-10% boundary
  topIds: Set<number>
}

export function storyStats(points: MapPoint[]): StoryStats {
  const sorted = [...points].sort((a, b) => b.score - a.score)
  const n = Math.max(1, Math.round(points.length / 10))
  return { topCut: sorted[n - 1]?.score ?? 100, topIds: new Set(sorted.slice(0, n).map((p) => p.number)) }
}
