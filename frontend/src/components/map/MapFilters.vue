<template>
  <div class="map-filters">
    <select v-model="mapStore.vesselTypeFilter" class="filter-select">
      <option :value="null">All vessels</option>
      <option value="tanker">Tankers</option>
      <option value="bulk_carrier">Bulk carriers</option>
      <option value="container">Containers</option>
      <option value="lng_carrier">LNG carriers</option>
    </select>
    <select v-model="mapStore.commodityFilter" class="filter-select" @change="onCommodityChange">
      <option :value="null">All commodities</option>
      <option value="crude_oil">Crude Oil</option>
      <option value="coal">Coal</option>
      <option value="iron_ore">Iron Ore</option>
      <option value="copper">Copper</option>
      <option value="lng">LNG</option>
    </select>
  </div>
</template>

<script setup lang="ts">
import { useMapStore } from '../../stores/useMapStore'

const mapStore = useMapStore()

function onCommodityChange() {
  mapStore.fetchTradeFlows()
}
</script>

<style scoped>
.map-filters {
  position: absolute;
  top: 1rem;
  right: 1rem;
  display: flex;
  gap: 0.5rem;
  z-index: 10;
}

.filter-select {
  background: rgba(15, 23, 42, 0.9);
  border: 1px solid #334155;
  border-radius: 6px;
  color: #e2e8f0;
  padding: 0.5rem 0.75rem;
  font-size: 0.85rem;
  cursor: pointer;
}

.filter-select:focus {
  outline: none;
  border-color: #3b82f6;
}
</style>
