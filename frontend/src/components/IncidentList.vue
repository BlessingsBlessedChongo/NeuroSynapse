<template>
  <v-card class="incidents-card rounded-xl pa-2 h-100" elevation="0">
    <v-card-title class="d-flex align-center py-3 px-4">
      <div class="d-flex align-center ga-2">
        <v-avatar color="rose-accent-3" variant="tonal" size="36" class="mr-1">
          <v-icon icon="mdi-alert-octagon" size="20" />
        </v-avatar>
        <span class="text-h6 font-weight-bold text-slate-100">Active Incidents</span>
      </div>
      <v-spacer />
      <v-chip
        v-if="store.openIncidents > 0"
        size="small"
        color="error"
        variant="flat"
        class="font-weight-bold"
      >
        {{ store.openIncidents }} Open
      </v-chip>
    </v-card-title>

    <v-card-text class="pa-2">
      <!-- Loading State -->
      <div v-if="store.loading && store.incidents.length === 0" class="px-2 pt-2">
        <v-skeleton-loader type="table-row" class="mb-2" />
        <v-skeleton-loader type="table-row" class="mb-2" />
        <v-skeleton-loader type="table-row" class="mb-2" />
        <v-skeleton-loader type="table-row" />
      </div>

      <!-- Error State -->
      <div v-else-if="store.error && store.incidents.length === 0" class="state-panel text-center py-10">
        <v-icon icon="mdi-alert-circle-outline" size="44" color="error" class="mb-3" />
        <p class="text-body-2 text-error mb-4">{{ store.error }}</p>
        <v-btn variant="outlined" color="cyan-accent-2" size="small" @click="store.fetchIncidents()">
          Retry
        </v-btn>
      </div>

      <!-- Empty State -->
      <div v-else-if="store.latestIncidents.length === 0" class="state-panel text-center py-10">
        <v-icon icon="mdi-shield-check" size="52" color="success" class="mb-3 opacity-80" />
        <p class="text-body-1 font-weight-bold text-slate-200 mb-1">No Incidents Detected</p>
        <p class="text-caption text-slate-400 mb-0">System is operating within optimal baseline parameters</p>
      </div>

      <!-- Data Table -->
      <v-data-table
        v-else
        :headers="headers"
        :items="store.latestIncidents"
        item-value="id"
        density="compact"
        class="incident-table bg-transparent"
        :items-per-page="10"
        hide-default-footer
      >
        <template #item.failure_type="{ item }">
          <div class="py-2">
            <v-chip
              :color="getIncidentTypeColor(item.failure_type)"
              size="small"
              variant="flat"
              class="font-weight-bold"
            >
              {{ item.failure_type_display || item.failure_type }}
            </v-chip>
            <div v-if="hasContext(item)" class="context-line mt-1 font-mono">
              {{ formatContext(item) }}
            </div>
          </div>
        </template>

        <template #item.device_name="{ item }">
          <span class="text-body-2 font-weight-semibold text-slate-200">{{ item.device_name || 'Unknown' }}</span>
        </template>

        <template #item.status="{ item }">
          <v-chip
            :color="getStatusColor(item.status)"
            size="x-small"
            variant="tonal"
            class="font-weight-bold text-uppercase"
          >
            {{ item.status_display || item.status }}
          </v-chip>
        </template>

        <template #item.confidence_score="{ item }">
          <div class="d-flex align-center ga-2">
            <v-progress-linear
              :model-value="getConfidencePercentage(item.confidence_score)"
              :color="getConfidenceColor(item.confidence_score)"
              height="6"
              rounded
              style="min-width: 60px; max-width: 80px"
            />
            <span class="text-caption font-weight-bold text-slate-300 font-mono">
              {{ getConfidencePercentage(item.confidence_score) }}%
            </span>
          </div>
        </template>

        <template #item.detected_at="{ item }">
          <span class="text-caption text-slate-400 font-mono">
            {{ formatDetectedTime(item.detected_at) }}
          </span>
        </template>

        <template #item.actions="{ item }">
          <div v-if="item.status === 'MANUAL_REVIEW'" class="d-flex flex-wrap ga-1 justify-center">
            <v-tooltip v-if="!store.canApprove" text="Requires Administrator Privileges" location="top">
              <template #activator="{ props }">
                <span v-bind="props">
                  <v-btn size="x-small" color="success" variant="flat" disabled icon="mdi-check" />
                </span>
              </template>
            </v-tooltip>
            <template v-else>
              <v-btn
                size="x-small"
                color="success"
                variant="flat"
                icon="mdi-check"
                :loading="approvingId === item.id"
                :disabled="rejectingId === item.id"
                @click="handleApprove(item.id)"
              />
              <v-btn
                size="x-small"
                color="error"
                variant="flat"
                icon="mdi-close"
                :loading="rejectingId === item.id"
                :disabled="approvingId === item.id"
                @click="handleReject(item.id)"
              />
            </template>
          </div>

          <div v-else-if="item.status === 'HEALED' && store.canApprove" class="d-flex justify-center">
            <v-btn
              size="x-small"
              color="amber-accent-4"
              variant="tonal"
              icon="mdi-backup-restore"
              :loading="rollingBackId === item.id"
              @click="handleRollback(item.id)"
            />
          </div>

          <v-icon
            v-else
            icon="mdi-minus"
            size="18"
            color="slate-500"
          />
        </template>
      </v-data-table>
    </v-card-text>
  </v-card>
</template>

<script setup>
import { ref } from 'vue'
import { useNetworkStore } from '@/stores/network'

const store = useNetworkStore()
const approvingId = ref(null)
const rejectingId = ref(null)
const rollingBackId = ref(null)

const headers = [
  { title: 'Type', key: 'failure_type', sortable: false },
  { title: 'Device', key: 'device_name', sortable: false },
  { title: 'Status', key: 'status', sortable: false },
  { title: 'Confidence', key: 'confidence_score', sortable: false },
  { title: 'Detected', key: 'detected_at', sortable: false },
  { title: 'Actions', key: 'actions', sortable: false, align: 'center' },
]

function hasContext(item) {
  return !!(item.source_ip || item.destination_port || item.interface_name || item.service_name)
}

function formatContext(item) {
  const parts = []
  if (item.source_ip) parts.push(`src ${item.source_ip}${item.source_port ? ':' + item.source_port : ''}`)
  if (item.destination_port) parts.push(`port ${item.destination_port}`)
  if (item.interface_name) parts.push(`iface ${item.interface_name}`)
  if (item.service_name) parts.push(item.service_name + (item.process_id ? ` (PID ${item.process_id})` : ''))
  if (item.traffic_volume) parts.push(`${Math.round(item.traffic_volume).toLocaleString()} pps`)
  return parts.join(' · ')
}

function getIncidentTypeColor(type) {
  switch (type) {
    case 'SERVICE_CRASH': return 'error'
    case 'LINK_FAILURE': return 'warning'
    case 'DDOS_ATTACK': return 'violet'
    case 'PERFORMANCE_DEGRADATION': return 'cyan-accent-3'
    default: return 'secondary'
  }
}

function getStatusColor(status) {
  switch (status) {
    case 'MANUAL_REVIEW': return 'warning'
    case 'HEALING':
    case 'READY_FOR_ACTION': return 'info'
    case 'DETECTED':
    case 'DIAGNOSING': return 'secondary'
    case 'HEALED': return 'success'
    case 'FAILED': return 'error'
    case 'ROLLED_BACK': return 'purple'
    default: return 'secondary'
  }
}

function getConfidencePercentage(confidence) {
  if (confidence == null) return 0
  return Math.min(100, Math.max(0, Math.round(confidence * 100)))
}

function getConfidenceColor(confidence) {
  const pct = getConfidencePercentage(confidence)
  if (pct >= 80) return 'cyan-accent-3'
  if (pct >= 60) return 'amber-accent-3'
  return 'rose-400'
}

function formatDetectedTime(isoString) {
  if (!isoString) return '--'
  try {
    const date = new Date(isoString)
    const diffMs = Date.now() - date.getTime()
    const diffSecs = Math.floor(diffMs / 1000)
    const diffMins = Math.floor(diffSecs / 60)
    const diffHours = Math.floor(diffMins / 60)
    const diffDays = Math.floor(diffHours / 24)

    if (diffSecs < 60) return `${diffSecs}s ago`
    if (diffMins < 60) return `${diffMins}m ago`
    if (diffHours < 24) return `${diffHours}h ago`
    return `${diffDays}d ago`
  } catch {
    return '--'
  }
}

async function handleApprove(id) {
  approvingId.value = id
  try {
    await store.approveIncident(id)
  } catch (error) {
    console.error('Failed to approve healing:', error)
  } finally {
    approvingId.value = null
  }
}

async function handleReject(id) {
  rejectingId.value = id
  try {
    await store.rejectIncident(id)
  } catch (error) {
    console.error('Failed to reject healing:', error)
  } finally {
    rejectingId.value = null
  }
}

async function handleRollback(id) {
  rollingBackId.value = id
  try {
    await store.rollbackIncident(id)
  } catch (error) {
    console.error('Failed to roll back incident:', error)
  } finally {
    rollingBackId.value = null
  }
}
</script>

<style scoped>
.incidents-card {
  background: rgba(15, 23, 42, 0.65) !important;
  backdrop-filter: blur(16px);
  -webkit-backdrop-filter: blur(16px);
  border: 1px solid rgba(148, 163, 184, 0.12);
}

.incident-table :deep(.v-data-table__thead th) {
  font-size: 0.7rem !important;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: #94a3b8 !important;
  background: transparent !important;
  border-bottom: 1px solid rgba(148, 163, 184, 0.1) !important;
}

.incident-table :deep(.v-data-table__tr) {
  border-bottom: 1px solid rgba(148, 163, 184, 0.05) !important;
}

.incident-table :deep(.v-data-table__tr:hover) {
  background: rgba(30, 41, 59, 0.5) !important;
}

.state-panel {
  min-height: 220px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
}

.context-line {
  font-size: 0.68rem;
  color: #94a3b8;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  max-width: 200px;
}

.font-mono {
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace !important;
}
</style>