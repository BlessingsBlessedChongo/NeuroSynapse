<template>
  <v-card class="device-card rounded-xl pa-2" elevation="0">
    <v-card-title class="d-flex align-center py-3 px-4">
      <div class="d-flex align-center">
        <v-avatar color="cyan-accent-4" variant="tonal" size="36" class="mr-3">
          <v-icon icon="mdi-router-wireless" size="20" />
        </v-avatar>
        <span class="text-h6 font-weight-bold text-slate-100">Network Device Inventory</span>
      </div>
      <v-spacer />
      <v-chip
        v-if="store.lastUpdated"
        size="small"
        variant="text"
        class="text-slate-400 font-weight-medium"
        prepend-icon="mdi-clock-outline"
      >
        Updated {{ formattedLastUpdated }}
      </v-chip>
    </v-card-title>

    <v-card-text class="pa-2">
      <!-- Loading State -->
      <div v-if="store.loading && store.devices.length === 0" class="device-list ga-2 d-flex flex-column">
        <div
          v-for="n in 4"
          :key="n"
          class="device-item-row d-flex align-center justify-space-between pa-3 rounded-lg"
        >
          <div class="d-flex align-center ga-4">
            <v-skeleton-loader type="avatar" width="12" height="12" class="rounded-circle" />
            <div>
              <v-skeleton-loader type="text" width="140" class="mb-1" />
              <v-skeleton-loader type="text" width="90" />
            </div>
          </div>
          <div class="d-flex ga-4">
            <v-skeleton-loader type="chip" width="60" />
            <v-skeleton-loader type="chip" width="60" />
            <v-skeleton-loader type="chip" width="60" />
          </div>
        </div>
      </div>

      <!-- Error State -->
      <div v-else-if="store.error && store.devices.length === 0" class="state-panel text-center py-10">
        <v-icon icon="mdi-alert-circle-outline" size="44" color="error" class="mb-3" />
        <p class="text-body-2 text-error mb-4">{{ store.error }}</p>
        <v-btn variant="outlined" color="cyan-accent-2" size="small" @click="store.fetchDevices()">
          Retry
        </v-btn>
      </div>

      <!-- Device Grid/List -->
      <div v-else class="device-list ga-2 d-flex flex-column">
        <div
          v-for="device in store.devices"
          :key="device.id"
          class="device-item-row d-flex align-center justify-space-between pa-3 rounded-lg"
        >
          <div class="d-flex align-center">
            <!-- Pulsing Status Dot -->
            <div class="status-pulse-wrapper mr-4">
              <span class="status-dot" :class="statusDotClass(device.status)" />
              <span class="status-ring" :class="statusDotClass(device.status)" />
            </div>

            <div>
              <div class="d-flex align-center ga-2">
                <span class="font-weight-bold text-slate-100 text-subtitle-1">{{ device.name }}</span>
                <v-chip
                  size="x-small"
                  variant="tonal"
                  :color="statusChipColor(device.status)"
                  class="font-weight-semibold"
                >
                  {{ statusLabel(device.status) }}
                </v-chip>
                <v-chip
                  v-if="device.device_type"
                  size="x-small"
                  variant="outlined"
                  color="slate-400"
                  class="font-weight-medium"
                >
                  {{ device.device_type }}
                </v-chip>
              </div>
              <p class="text-caption text-slate-400 mb-0 font-mono">
                {{ device.ip_address || 'No IP assigned' }}
              </p>
            </div>
          </div>

          <!-- Micro Metric Pill Cards -->
          <div class="d-flex ga-4 align-center">
            <div class="metric-pill px-3 py-1 rounded-md text-center">
              <span class="metric-label d-block">CPU</span>
              <span class="metric-val text-cyan-accent-2">{{ formatPercent(deviceMetric(device, 'cpu')) }}</span>
            </div>
            <div class="metric-pill px-3 py-1 rounded-md text-center">
              <span class="metric-label d-block">Memory</span>
              <span class="metric-val text-violet-accent">{{ formatPercent(deviceMetric(device, 'memory')) }}</span>
            </div>
            <div class="metric-pill px-3 py-1 rounded-md text-center">
              <span class="metric-label d-block">Loss</span>
              <span class="metric-val text-rose-400">{{ formatPercent(deviceMetric(device, 'packet_loss')) }}</span>
            </div>
          </div>
        </div>

        <div v-if="store.devices.length === 0" class="text-center py-8">
          <v-icon icon="mdi-lan-disconnect" size="40" color="slate-500" class="mb-2" />
          <p class="text-body-2 text-slate-400 mb-0">No network devices registered</p>
        </div>
      </div>
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
    case 'ONLINE': return 'Online'
    case 'DEGRADED': return 'Degraded'
    case 'OFFLINE': return 'Offline'
    default: return 'Unknown'
  }
}

function statusDotClass(status) {
  switch (status) {
    case 'ONLINE': return 'dot-active'
    case 'DEGRADED': return 'dot-degraded'
    case 'OFFLINE': return 'dot-down'
    default: return 'dot-unknown'
  }
}

function statusChipColor(status) {
  switch (status) {
    case 'ONLINE': return 'success'
    case 'DEGRADED': return 'warning'
    case 'OFFLINE': return 'error'
    default: return 'secondary'
  }
}

function deviceMetric(device, key) {
  const snapshot = store.deviceTelemetry[device.name]
  return snapshot ? snapshot[key] : null
}

function formatPercent(value) {
  if (value === null || value === undefined) return '--'
  return `${Number(value).toFixed(1)}%`
}
</script>

<style scoped>
.device-card {
  background: rgba(15, 23, 42, 0.65) !important;
  backdrop-filter: blur(16px);
  -webkit-backdrop-filter: blur(16px);
  border: 1px solid rgba(148, 163, 184, 0.12);
}

.device-item-row {
  background: rgba(30, 41, 59, 0.4);
  border: 1px solid rgba(148, 163, 184, 0.08);
  transition: all 0.2s ease;
}

.device-item-row:hover {
  background: rgba(30, 41, 59, 0.8);
  border-color: rgba(0, 229, 255, 0.3);
}

/* Pulsing Dots */
.status-pulse-wrapper {
  position: relative;
  width: 12px;
  height: 12px;
}

.status-dot {
  position: absolute;
  width: 10px;
  height: 10px;
  border-radius: 50%;
  top: 1px;
  left: 1px;
}

.status-ring {
  position: absolute;
  width: 12px;
  height: 12px;
  border-radius: 50%;
  animation: pulse-ring 2s cubic-bezier(0.215, 0.61, 0.355, 1) infinite;
}

@keyframes pulse-ring {
  0% { transform: scale(0.95); opacity: 0.8; }
  50% { transform: scale(1.8); opacity: 0; }
  100% { transform: scale(0.95); opacity: 0; }
}

.dot-active { background-color: #00e676; }
.dot-active.status-ring { border: 1px solid #00e676; }

.dot-degraded { background-color: #ffd600; }
.dot-degraded.status-ring { border: 1px solid #ffd600; }

.dot-down { background-color: #ff5252; }
.dot-down.status-ring { border: 1px solid #ff5252; }

.dot-unknown { background-color: #64748b; }

/* Micro Metric Pills */
.metric-pill {
  background: rgba(15, 23, 42, 0.6);
  border: 1px solid rgba(255, 255, 255, 0.05);
  min-width: 75px;
}

.metric-label {
  font-size: 0.65rem;
  color: #94a3b8;
  font-weight: 700;
  letter-spacing: 0.5px;
}

.metric-val {
  font-size: 0.85rem;
  font-weight: 700;
  font-variant-numeric: tabular-nums;
}

.font-mono {
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace !important;
  letter-spacing: -0.2px;
}
</style>