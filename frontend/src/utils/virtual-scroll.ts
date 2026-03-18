/**
 * Thin virtual scroll utility.
 * Computes which items are visible given container height, scroll offset, and item height.
 */

export interface VirtualScrollOptions {
  itemCount: number
  itemHeight: number
  containerHeight: number
  overscan?: number
}

export interface VirtualScrollResult {
  startIndex: number
  endIndex: number
  offsetTop: number
  totalHeight: number
  visibleCount: number
}

export function computeVirtualScroll(
  scrollTop: number,
  options: VirtualScrollOptions
): VirtualScrollResult {
  const { itemCount, itemHeight, containerHeight, overscan = 5 } = options

  const totalHeight = itemCount * itemHeight
  const visibleCount = Math.ceil(containerHeight / itemHeight)

  let startIndex = Math.floor(scrollTop / itemHeight) - overscan
  startIndex = Math.max(0, startIndex)

  let endIndex = startIndex + visibleCount + 2 * overscan
  endIndex = Math.min(itemCount - 1, endIndex)

  const offsetTop = startIndex * itemHeight

  return {
    startIndex,
    endIndex,
    offsetTop,
    totalHeight,
    visibleCount,
  }
}

export function createVirtualScroller(options: VirtualScrollOptions) {
  let currentScrollTop = 0
  let result = computeVirtualScroll(0, options)

  return {
    get result() { return result },
    onScroll(scrollTop: number) {
      currentScrollTop = scrollTop
      result = computeVirtualScroll(scrollTop, options)
      return result
    },
    updateOptions(newOptions: Partial<VirtualScrollOptions>) {
      Object.assign(options, newOptions)
      result = computeVirtualScroll(currentScrollTop, options)
      return result
    },
  }
}
