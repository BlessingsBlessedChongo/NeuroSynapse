<template>
  <v-card color="surface" elevation="2" class="device-card">
    <v-card-title class="d-flex align-center">
      <v-icon icon="mdi-router-wireless" class="mr-2 text-primary" />
      Network Device Inventory
      <v-spacer />
      <span v-if="store.lastUpdated" class="text-caption text-medium-emphasis">
        Updated {{ formattedLastUpdated }}
      </span>
    </v-card-title>

    <v-card-text class="pa-0">
      <div v-if="store.loading && store.devices.length === 0" class="state-panel text-center py-10">
        <v-progress-circular indeterminate color="primary" size="44" class="mb-3" />
        <p class="text-body-2 text-medium-emphasis">Loading device inventory…</p>
      </div>

      <div v-else-if="store.error && store.devices.length === 0" class="state-panel text-center py-10">
        <v-icon icon="mdi-alert-circle-outline" size="44" color="error" class="mb-3" />
        <p class="text-body-2 text-error mb-4">{{ store.error }}</p>
        <v-btn variant="outlined" color="primary" size="small" @click="store.fetchStatus()">
          Retry
        </v-btn>
      </div>

      <v-list v-else bg-color="transparent" lines="two" class="py-0">
        <template v-for="(device, index) in store.devices" :key="device.id">
          <v-list-item class="device-item px-4 py-3">
            <template #prepend>
              <span
                class="status-dot mr-3"
                :class="statusDotClass(device.status)"
                :title="statusLabel(device.status)"
              />
            </template>

            <v-list-item-title class="font-weight-bold">
              {{ device.name }}
            </v-list-item-title>

            <v-list-item-subtitle class="text-medium-emphasis">
              {{ device.ip || 'No IP assigned' }}
              <v-chip
                size="x-small"
                variant="tonal"
                :color="statusChipColor(device.status)"
                class="ml-2"
              >
                {{ statusLabel(device.status) }}
              </v-chip>
            </v-list-item-subtitle>

            <template #append>
              <div class="metrics-block text-right">
                <div class="metric-row">
                  <span class="metric-label">CPU</span>
                  <span class="metric-value text-cyan">{{ formatPercent(device.cpu) }}</span>
                </div>
                <div class="metric-row">
                  <span class="metric-label">Memory</span>
                  <span class="metric-value text-purple">{{ formatPercent(device.memory) }}</span>
                </div>
                <div class="metric-row">
                  <span class="metric-label">Loss</span>
                  <span class="metric-value text-error">{{ formatPercent(device.packet_loss) }}</span>
                </div>
              </div>
            </template>
          </v-list-item>

          <v-divider v-if="index < store.devices.length - 1" class="mx-4" />
        </template>

        <v-list-item v-if="store.devices.length === 0" class="py-10">
          <div class="w-100 text-center">
            <v-icon icon="mdi-lan-disconnect" size="48" color="secondary" class="mb-3 opacity-60" />
            <p class="text-body-2 text-medium-emphasis mb-0">No network devices registered</p>
          </div>
        </v-list-item>
      </v-list>
    </v-card-text>
  </v-card>
</template>

<script setup>
import { computed } from 'vue'
import { useNetworkStore } from '@/stores/network'

const store = useNetworkStore()

const formattedLastUpdated = computed(() => {
  if (!store.lastUpdated) return '--'
  return store.lastUpdated.toLocaleTimeString()
})

function statusLabel(status) {
  switch (status) {
    case 'HEALTHY':
      return 'Active'
    case 'WARNING':
      return 'Degraded'
    case 'CRITICAL':
      return 'Down'
    default:
      return 'Unknown'
  }
}

function statusDotClass(status) {
  switch (status) {
    case 'HEALTHY':
      return 'dot-active'
    case 'WARNING':
      return 'dot-degraded'
    case 'CRITICAL':
      return 'dot-down'
    default:
      return 'dot-unknown'
  }
}

function statusChipColor(status) {
  switch (status) {
    case 'HEALTHY':
      return 'success'
    case 'WARNING':
      return 'warning'
    case 'CRITICAL':
      return 'error'
    default:
      return 'secondary'
  }
}

function formatPercent(value) {
  if (value === null || value === undefined) return '--'
  return `${Number(value).toFixed(1)}%`
}
</script>

<style scoped>
.device-card {
  border: 1px solid rgba(148, 163, 184, 0.08);
}

.status-dot {
  display: inline-block;
  width: 10px;
  height: 10px;
  border-radius: 50%;
  flex-shrink: 0;
  box-shadow: 0 0 8px currentColor;
}

.dot-active {
  background-color: #4ade80;
  color: rgba(74, 222, 128, 0.6);
}

.dot-degraded {
  background-color: #facc15;
  color: rgba(250, 204, 21, 0.6);
}

.dot-down {
  background-color: #f87171;
  color: rgba(248, 113, 113, 0.6);
}

.dot-unknown {
  background-color: #64748b;
  color: rgba(100, 116, 139, 0.6);
}

.metrics-block {
  min-width: 110px;
}

.metric-row {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  font-size: 0.75rem;
  line-height: 1.6;
}

.metric-label {
  color: rgba(148, 163, 184, 0.9);
}

.metric-value {
  font-weight: 600;
  font-variant-numeric: tabular-nums;
}

.text-cyan {
  color: #00e5ff !important;
}

.text-purple {
  color: #e040fb !important;
}

.state-panel {
  min-height: 160px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
}

.opacity-60 {
  opacity: 0.6;
}
</style>
