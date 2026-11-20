// Shared geometry for the two risk maps (the story on the start page and the interactive map).
export const MAP_SIZE = 560
export const PAD = { left: 44, right: 16, top: 16, bottom: 40 }
export const PLOT_W = MAP_SIZE - PAD.left - PAD.right
export const PLOT_H = MAP_SIZE - PAD.top - PAD.bottom
/** percentile (0-100) to SVG x / y */
export const mx = (p: number) => PAD.left + (p / 100) * PLOT_W
export const my = (p: number) => PAD.top + PLOT_H - (p / 100) * PLOT_H

/** Endpoints of the line where size% + llm% = 2 x score, clipped to the plot. */
export function diagonal(score: number) {
  const t = 2 * score
  const x1 = Math.max(0, t - 100)
  const x2 = Math.min(100, t)
  return { x1: mx(x1), y1: my(t - x1), x2: mx(x2), y2: my(t - x2) }
}

/** Polygon covering every point with hybrid >= score (the top-right corner). */
export function regionAbove(score: number) {
  const t = 2 * score
  const pts: [number, number][] =
    t <= 100
      ? [[0, t], [0, 100], [100, 100], [100, 0], [t, 0]]
      : [[t - 100, 100], [100, 100], [100, t - 100]]
  return pts.map(([a, b]) => `${mx(a)},${my(b)}`).join(' ')
}
