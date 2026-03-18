<template>
  <div class="ss-data-table">
    <div class="table-wrapper">
      <table>
        <thead>
          <tr>
            <th
              v-for="col in columns"
              :key="col.key"
              :class="{ sortable: sortable, sorted: sortKey === col.key }"
              @click="sortable && toggleSort(col.key)"
            >
              <span class="th-content">
                {{ col.label }}
                <span v-if="sortable && sortKey === col.key" class="sort-icon">
                  {{ sortDir === 'asc' ? '\u25B2' : '\u25BC' }}
                </span>
              </span>
            </th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="(row, idx) in paginatedData" :key="idx">
            <td v-for="col in columns" :key="col.key">
              <slot :name="`cell-${col.key}`" :row="row" :value="row[col.key]">
                {{ row[col.key] }}
              </slot>
            </td>
          </tr>
          <tr v-if="!paginatedData.length">
            <td :colspan="columns.length" class="empty-row">No data</td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- Pagination -->
    <div v-if="paginated && totalPages > 1" class="pagination">
      <button class="page-btn" :disabled="currentPage <= 1" @click="currentPage--">
        &lsaquo;
      </button>
      <span class="page-info">{{ currentPage }} / {{ totalPages }}</span>
      <button class="page-btn" :disabled="currentPage >= totalPages" @click="currentPage++">
        &rsaquo;
      </button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, type PropType } from 'vue'

export interface Column {
  key: string
  label: string
}

const props = defineProps({
  columns: {
    type: Array as PropType<Column[]>,
    required: true,
  },
  data: {
    type: Array as PropType<Record<string, any>[]>,
    required: true,
  },
  sortable: {
    type: Boolean,
    default: false,
  },
  paginated: {
    type: Boolean,
    default: false,
  },
  pageSize: {
    type: Number,
    default: 10,
  },
})

const sortKey = ref<string>('')
const sortDir = ref<'asc' | 'desc'>('asc')
const currentPage = ref(1)

function toggleSort(key: string) {
  if (sortKey.value === key) {
    sortDir.value = sortDir.value === 'asc' ? 'desc' : 'asc'
  } else {
    sortKey.value = key
    sortDir.value = 'asc'
  }
  currentPage.value = 1
}

const sortedData = computed(() => {
  if (!sortKey.value) return props.data
  const k = sortKey.value
  const dir = sortDir.value === 'asc' ? 1 : -1
  return [...props.data].sort((a, b) => {
    const va = a[k]
    const vb = b[k]
    if (va == null) return 1
    if (vb == null) return -1
    if (typeof va === 'number' && typeof vb === 'number') return (va - vb) * dir
    return String(va).localeCompare(String(vb)) * dir
  })
})

const totalPages = computed(() =>
  props.paginated ? Math.max(1, Math.ceil(sortedData.value.length / props.pageSize)) : 1
)

const paginatedData = computed(() => {
  if (!props.paginated) return sortedData.value
  const start = (currentPage.value - 1) * props.pageSize
  return sortedData.value.slice(start, start + props.pageSize)
})
</script>

<style scoped>
.ss-data-table {
  width: 100%;
}

.table-wrapper {
  overflow-x: auto;
}

table {
  width: 100%;
  border-collapse: collapse;
  font-size: var(--ss-text-sm, 0.875rem);
}

thead th {
  text-align: left;
  padding: var(--ss-space-sm, 8px) var(--ss-space-md, 12px);
  color: var(--ss-text-muted, #94a3b8);
  font-weight: var(--ss-font-medium, 500);
  font-size: var(--ss-text-xs, 0.75rem);
  text-transform: uppercase;
  letter-spacing: 0.05em;
  border-bottom: 1px solid var(--ss-border, #475569);
  white-space: nowrap;
  user-select: none;
}

thead th.sortable {
  cursor: pointer;
}

thead th.sortable:hover {
  color: var(--ss-text-primary, #f8fafc);
}

.th-content {
  display: inline-flex;
  align-items: center;
  gap: var(--ss-space-xs, 4px);
}

.sort-icon {
  font-size: 0.6rem;
  opacity: 0.7;
}

tbody td {
  padding: var(--ss-space-sm, 8px) var(--ss-space-md, 12px);
  color: var(--ss-text-primary, #f8fafc);
  border-bottom: 1px solid var(--ss-border-light, #334155);
}

tbody tr:hover {
  background: var(--ss-bg-hover, rgba(71, 85, 105, 0.3));
}

.empty-row {
  text-align: center;
  color: var(--ss-text-muted, #94a3b8);
  padding: var(--ss-space-xl, 24px);
}

.pagination {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: var(--ss-space-md, 12px);
  padding: var(--ss-space-md, 12px) 0;
}

.page-btn {
  background: transparent;
  border: 1px solid var(--ss-border, #475569);
  border-radius: var(--ss-radius-md, 6px);
  color: var(--ss-text-secondary, #cbd5e1);
  padding: var(--ss-space-xs, 4px) var(--ss-space-sm, 8px);
  cursor: pointer;
  font-size: var(--ss-text-md, 1rem);
  transition: all var(--ss-transition-fast, 150ms ease);
}

.page-btn:hover:not(:disabled) {
  background: var(--ss-bg-hover, #475569);
  color: var(--ss-text-primary, #f8fafc);
}

.page-btn:disabled {
  opacity: 0.3;
  cursor: not-allowed;
}

.page-info {
  color: var(--ss-text-muted, #94a3b8);
  font-size: var(--ss-text-sm, 0.875rem);
}
</style>
