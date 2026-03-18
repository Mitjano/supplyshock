<template>
  <div class="map-filters">
    <select v-model="mapStore.vesselTypeFilter" class="filter-select">
      <option :value="null">{{ t('map.allVessels') }}</option>
      <option value="tanker">{{ t('map.tankers') }}</option>
      <option value="bulk_carrier">{{ t('map.bulkCarriers') }}</option>
      <option value="container">{{ t('map.containers') }}</option>
      <option value="lng_carrier">{{ t('map.lngCarriers') }}</option>
    </select>
    <select v-model="mapStore.commodityFilter" class="filter-select" @change="onCommodityChange">
      <option :value="null">{{ t('map.allCommodities') }}</option>
      <option value="crude_oil">{{ t('map.crudeOil') }}</option>
      <option value="coal">{{ t('map.coal') }}</option>
      <option value="iron_ore">{{ t('map.ironOre') }}</option>
      <option value="copper">{{ t('map.copper') }}</option>
      <option value="lng">{{ t('map.lng') }}</option>
    </select>
  </div>
</template>

<script setup lang="ts">
import { useI18n } from 'vue-i18n'
import { useMapStore } from '../../stores/useMapStore'

const { t } = useI18n()
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
