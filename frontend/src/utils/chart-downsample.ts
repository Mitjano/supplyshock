/**
 * LTTB (Largest Triangle Three Buckets) downsampling algorithm.
 * Reduces the number of data points while preserving the visual shape of the chart.
 *
 * Reference: Sveinn Steinarsson, "Downsampling Time Series for Visual Representation"
 */

export interface TimeValue {
  time: number
  value: number
}

/**
 * Downsample an array of {time, value} points using the LTTB algorithm.
 * Returns the original array if its length is already <= targetPoints.
 *
 * @param data - Sorted array of {time, value} points
 * @param targetPoints - Desired number of output points (minimum 3)
 */
export function downsample(data: TimeValue[], targetPoints: number): TimeValue[] {
  const len = data.length
  if (targetPoints >= len || targetPoints < 3) {
    return data
  }

  const result: TimeValue[] = []

  // Always keep the first point
  result.push(data[0])

  const bucketSize = (len - 2) / (targetPoints - 2)

  let prevIndex = 0

  for (let i = 1; i < targetPoints - 1; i++) {
    // Calculate bucket boundaries
    const bucketStart = Math.floor((i - 1) * bucketSize) + 1
    const bucketEnd = Math.min(Math.floor(i * bucketSize) + 1, len - 1)

    // Calculate the average point of the NEXT bucket (for the triangle area)
    const nextBucketStart = Math.floor(i * bucketSize) + 1
    const nextBucketEnd = Math.min(Math.floor((i + 1) * bucketSize) + 1, len - 1)

    let avgTime = 0
    let avgValue = 0
    let nextBucketLen = 0
    for (let j = nextBucketStart; j < nextBucketEnd; j++) {
      avgTime += data[j].time
      avgValue += data[j].value
      nextBucketLen++
    }
    if (nextBucketLen > 0) {
      avgTime /= nextBucketLen
      avgValue /= nextBucketLen
    }

    // Find the point in the current bucket that forms the largest triangle
    // with the previous selected point and the average of the next bucket
    const prevTime = data[prevIndex].time
    const prevValue = data[prevIndex].value

    let maxArea = -1
    let maxIndex = bucketStart

    for (let j = bucketStart; j < bucketEnd; j++) {
      // Triangle area (using the cross-product formula, keeping only magnitude)
      const area = Math.abs(
        (prevTime - avgTime) * (data[j].value - prevValue) -
        (prevTime - data[j].time) * (avgValue - prevValue)
      )
      if (area > maxArea) {
        maxArea = area
        maxIndex = j
      }
    }

    result.push(data[maxIndex])
    prevIndex = maxIndex
  }

  // Always keep the last point
  result.push(data[len - 1])

  return result
}
