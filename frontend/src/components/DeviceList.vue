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
      <div v-else-if="store.devicesError && store.devices.length === 0" class="state-panel text-center py-10">
        <v-icon icon="mdi-alert-circle-outline" size="44" color="error" class="mb-3" />
        <p class="text-body-2 text-error mb-4">{{ store.devicesError }}</p>
        <v-btn variant="outlined" color="cyan-accent-2" size="small" @click="store.fetchDevices()">
          Retry
        </v-btn>
      </div>

      <!-- Device Grid/List -->
      <div v-else class="device-list ga-2 d-flex flex-column">
        <div
          v-for="device in store.devices"
          :key="device.id"
          class="device-item-row clickable-row d-flex align-center justify-space-between pa-3 rounded-lg"
          role="button"
          tabindex="0"
          :aria-label="`View details for ${device.name}`"
          @click="openDeviceModal(device.id)"
          @keyup.enter="openDeviceModal(device.id)"
          @keyup.space.prevent="openDeviceModal(device.id)"
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
                  color="grey"
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
            <v-icon icon="mdi-chevron-right" size="20" color="grey" class="ml-1" />
          </div>
        </div>

        <div v-if="store.devices.length === 0" class="text-center py-8">
          <v-icon icon="mdi-lan-disconnect" size="40" color="grey" class="mb-2" />
          <p class="text-body-2 text-slate-400 mb-0">No network devices registered</p>
        </div>
      </div>
    </v-card-text>

    <!-- Detailed Device Metrics Dialog -->
    <v-dialog v-model="dialogOpen" max-width="650" width="100%">
      <v-card v-if="selectedDevice" class="device-modal rounded-xl pa-2">
        <v-card-title class="d-flex align-center py-3 px-4">
          <div class="d-flex align-center">
            <v-avatar color="cyan-accent-4" variant="tonal" size="40" class="mr-3">
              <v-icon icon="mdi-router-wireless" size="24" />
            </v-avatar>
            <div>
              <h3 class="text-h6 font-weight-bold text-slate-100 mb-0">{{ selectedDevice.name }}</h3>
              <p class="text-caption text-slate-400 mb-0 font-mono">{{ selectedDevice.ip_address }}</p>
            </div>
          </div>
          <v-spacer />
          <v-btn icon="mdi-close" variant="text" size="small" color="grey" @click="dialogOpen = false" />
        </v-card-title>

        <v-card-text class="pa-4">
          <!-- Main Metrics Overview Grid -->
          <div class="grid-metrics mb-4">
            <div class="detail-metric-card pa-3 rounded-lg text-center">
              <span class="metric-label d-block">CPU USAGE</span>
              <span class="text-h6 font-weight-bold text-cyan-accent-2">
                {{ formatPercent(selectedTelemetry?.cpu ?? selectedTelemetry?.cpu_usage) }}
              </span>
            </div>
            <div class="detail-metric-card pa-3 rounded-lg text-center">
              <span class="metric-label d-block">MEMORY</span>
              <span class="text-h6 font-weight-bold text-violet-accent">
                {{ formatPercent(selectedTelemetry?.memory ?? selectedTelemetry?.memory_usage) }}
              </span>
            </div>
            <div class="detail-metric-card pa-3 rounded-lg text-center">
              <span class="metric-label d-block">PACKET LOSS</span>
              <span class="text-h6 font-weight-bold text-rose-400">
                {{ formatPercent(selectedTelemetry?.packet_loss) }}
              </span>
            </div>
            <div class="detail-metric-card pa-3 rounded-lg text-center">
              <span class="metric-label d-block">LATENCY</span>
              <span class="text-h6 font-weight-bold text-amber-accent-2">
                {{ selectedTelemetry?.latency_ms !== undefined ? selectedTelemetry.latency_ms + ' ms' : '--' }}
              </span>
            </div>
          </div>

          <!-- Extended Telemetry Details -->
          <div class="d-flex flex-column ga-3">
            <!-- Routing & Links Summary -->
            <div class="detail-panel pa-3 rounded-lg">
              <div class="d-flex align-center justify-space-between mb-2">
                <span class="font-weight-bold text-slate-200 text-body-2">Routing Overview</span>
                <v-chip size="x-small" color="cyan" variant="tonal">
                  OSPF Active: {{ selectedTelemetry?.ospf_neighbors ?? 0 }} Neighbors
                </v-chip>
              </div>
              <div class="d-flex ga-4 text-caption text-slate-400">
                <span>Bandwidth Util: <strong class="text-slate-200">{{ selectedTelemetry?.bandwidth_util ?? 0 }}%</strong></span>
                <span>Interfaces Active: <strong class="text-emerald-400">{{ activeInterfacesCount }}</strong></span>
              </div>
            </div>

            <!-- Interfaces Status List -->
            <div class="detail-panel pa-3 rounded-lg">
              <span class="font-weight-bold text-slate-200 text-body-2 d-block mb-2">Interfaces</span>

              <div v-if="interfaceEntries.length > 0" class="d-flex flex-column ga-2">
                <div
                  v-for="[ifaceName, ifaceData] in interfaceEntries"
                  :key="ifaceName"
                  class="iface-row d-flex align-center justify-space-between px-3 py-2 rounded-md"
                >
                  <div class="d-flex align-center ga-2">
                    <v-icon
                      :icon="ifaceData.status === 'up' ? 'mdi-check-circle-outline' : 'mdi-alert-circle-outline'"
                      size="16"
                      :color="ifaceData.status === 'up' ? 'emerald-accent-3' : 'rose-accent-2'"
                    />
                    <span class="font-mono text-body-2 font-weight-medium text-slate-100">{{ ifaceName }}</span>
                  </div>
                  <div class="d-flex align-center ga-3">
                    <span class="text-caption text-slate-400">Errors: {{ ifaceData.errors ?? 0 }}</span>
                    <v-chip
                      size="x-small"
                      :color="ifaceData.status === 'up' ? 'success' : 'error'"
                      variant="tonal"
                      class="text-uppercase"
                    >
                      {{ ifaceData.status }}
                    </v-chip>
                  </div>
                </div>
              </div>

              <p v-else class="text-caption text-slate-500 mb-0">No interface details available</p>
            </div>
          </div>
        </v-card-text>
      </v-card>
    </v-dialog>
  </v-card>
</template>

<script setup>
import { ref, computed, watch } from 'vue'
import { useNetworkStore } from '@/stores/network'

const store = useNetworkStore()
const dialogOpen = ref(false)

// Store the id, not a snapshot of the device object. `store.devices` is
// wholesale-replaced by every fetchDevices() poll, so holding onto the
// old object reference meant the open modal's status/name/etc. froze
// at whatever they were the moment it was opened, even while the
// underlying device kept changing every 10 seconds in the background.
const selectedDeviceId = ref(null)

const selectedDevice = computed(() => {
  if (selectedDeviceId.value == null) return null
  return store.devices.find((d) => d.id === selectedDeviceId.value) || null
})

// If the selected device disappears from the list entirely (e.g.
// deleted, or filtered out), close the dialog instead of leaving it
// open with no backing data.
watch(selectedDevice, (device) => {
  if (dialogOpen.value && !device) {
    dialogOpen.value = false
  }
})

const formattedLastUpdated = computed(() => {
  if (!store.lastUpdated) return '--'
  return store.lastUpdated.toLocaleTimeString()
})

const selectedTelemetry = computed(() => {
  if (!selectedDevice.value) return null
  return store.deviceTelemetry[selectedDevice.value.name] || null
})

const interfaceEntries = computed(() => {
  const status = selectedTelemetry.value?.interface_status
  if (!status || typeof status !== 'object') return []
  return Object.entries(status)
})

const activeInterfacesCount = computed(() => {
  return interfaceEntries.value.filter(([_, data]) => data.status === 'up').length
})

function openDeviceModal(deviceId) {
  selectedDeviceId.value = deviceId
  dialogOpen.value = true
}

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

.clickable-row {
  cursor: pointer;
}

.clickable-row:focus-visible {
  outline: 2px solid #00e5ff;
  outline-offset: 2px;
}

.device-item-row:hover {
  background: rgba(30, 41, 59, 0.8);
  border-color: rgba(0, 229, 255, 0.3);
  transform: translateY(-1px);
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

/* Modal Styling */
.device-modal {
  background: #0f172a !important;
  border: 1px solid rgba(148, 163, 184, 0.15);
}

.grid-metrics {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 12px;
}

.detail-metric-card, .detail-panel {
  background: rgba(30, 41, 59, 0.5);
  border: 1px solid rgba(148, 163, 184, 0.08);
}

.iface-row {
  background: rgba(15, 23, 42, 0.5);
  border: 1px solid rgba(255, 255, 255, 0.03);
}

.font-mono {
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace !important;
}
</style>