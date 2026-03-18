/**
 * Web Worker for computing correlation matrices.
 * Offloads heavy computation from the main thread.
 *
 * Usage:
 *   const worker = new Worker(new URL('./correlation-worker.ts', import.meta.url), { type: 'module' })
 *   worker.postMessage({ series: { 'crude_oil': [1,2,3], 'lng': [4,5,6] } })
 *   worker.onmessage = (e) => { console.log(e.data.matrix) }
 */

interface CorrelationInput {
  series: Record<string, number[]>
}

interface CorrelationOutput {
  labels: string[]
  matrix: number[][]
}

function pearsonCorrelation(x: number[], y: number[]): number {
  const n = Math.min(x.length, y.length)
  if (n < 2) return 0

  let sumX = 0, sumY = 0, sumXY = 0, sumX2 = 0, sumY2 = 0
  for (let i = 0; i < n; i++) {
    sumX += x[i]
    sumY += y[i]
    sumXY += x[i] * y[i]
    sumX2 += x[i] * x[i]
    sumY2 += y[i] * y[i]
  }

  const denominator = Math.sqrt(
    (n * sumX2 - sumX * sumX) * (n * sumY2 - sumY * sumY)
  )
  if (denominator === 0) return 0
  return (n * sumXY - sumX * sumY) / denominator
}

function computeCorrelationMatrix(input: CorrelationInput): CorrelationOutput {
  const labels = Object.keys(input.series)
  const n = labels.length
  const matrix: number[][] = Array.from({ length: n }, () => Array(n).fill(0))

  for (let i = 0; i < n; i++) {
    matrix[i][i] = 1
    for (let j = i + 1; j < n; j++) {
      const corr = pearsonCorrelation(input.series[labels[i]], input.series[labels[j]])
      matrix[i][j] = Math.round(corr * 1000) / 1000
      matrix[j][i] = matrix[i][j]
    }
  }

  return { labels, matrix }
}

self.onmessage = (e: MessageEvent<CorrelationInput>) => {
  const result = computeCorrelationMatrix(e.data)
  self.postMessage(result)
}
