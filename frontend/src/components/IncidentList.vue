<template>
  <v-card color="surface" elevation="2" class="incident-card h-100">
    <v-card-title class="d-flex align-center">
      <v-icon icon="mdi-alert-octagon" class="mr-2 text-error" />
      Active Incidents
      <v-spacer />
      <v-chip
        v-if="store.openIncidents > 0"
        size="small"
        color="error"
        variant="tonal"
      >
        {{ store.openIncidents }} open
      </v-chip>
    </v-card-title>

    <v-card-text>
      <div v-if="store.loading && store.latestIncidents.length === 0" class="state-panel text-center py-10">
        <v-progress-circular indeterminate color="primary" size="44" class="mb-3" />
        <p class="text-body-2 text-medium-emphasis">Loading incident records…</p>
      </div>

      <div v-else-if="store.error && store.latestIncidents.length === 0" class="state-panel text-center py-10">
        <v-icon icon="mdi-alert-circle-outline" size="44" color="error" class="mb-3" />
        <p class="text-body-2 text-error mb-4">{{ store.error }}</p>
        <v-btn variant="outlined" color="primary" size="small" @click="store.fetchStatus()">
          Retry
        </v-btn>
      </div>

      <div v-else-if="store.latestIncidents.length === 0" class="state-panel text-center py-10">
        <v-icon icon="mdi-shield-check" size="56" color="success" class="mb-3 opacity-70" />
        <p class="text-body-1 font-weight-medium">No incidents detected</p>
        <p class="text-caption text-medium-emphasis">System is operating within normal parameters</p>
      </div>

      <v-data-table
        v-else
        :headers="headers"
        :items="store.latestIncidents"
        item-value="id"
        density="compact"
        hover
        class="incident-table bg-transparent"
        :items-per-page="10"
        hide-default-footer
      >
        <template #item.type="{ item }">
          <v-chip
            :color="getIncidentTypeColor(item.type)"
            size="small"
            variant="flat"
            class="font-weight-medium"
          >
            {{ formatIncidentType(item.type) }}
          </v-chip>
        </template>

        <template #item.device="{ item }">
          <span class="text-body-2 font-weight-medium">{{ item.device || 'Unknown' }}</span>
        </template>

        <template #item.status="{ item }">
          <v-chip
            :color="getStatusColor(item.status)"
            size="x-small"
            variant="tonal"
          >
            {{ item.status || 'Unknown' }}
          </v-chip>
        </template>

        <template #item.confidence="{ item }">
          <div class="d-flex align-center ga-2">
            <v-progress-linear
              :model-value="getConfidencePercentage(item.confidence)"
              :color="getConfidenceColor(item.confidence)"
              height="5"
              rounded
              style="min-width: 64px; max-width: 80px"
            />
            <span class="text-caption text-medium-emphasis">
              {{ getConfidencePercentage(item.confidence) }}%
            </span>
          </div>
        </template>

        <template #item.detected_at="{ item }">
          <span class="text-caption text-medium-emphasis">
            {{ formatDetectedTime(item.detected_at) }}
          </span>
        </template>

        <template #item.actions="{ item }">
          <div v-if="item.status === 'Manual Review'" class="d-flex flex-wrap ga-1 justify-center">
            <v-btn
              size="x-small"
              color="success"
              variant="flat"
              prepend-icon="mdi-check-circle"
              :loading="approvingId === item.id"
              :disabled="rejectingId === item.id"
              @click="handleApprove(item.id)"
            >
              Approve Healing
            </v-btn>
            <v-btn
              size="x-small"
              color="error"
              variant="flat"
              prepend-icon="mdi-close-circle"
              :loading="rejectingId === item.id"
              :disabled="approvingId === item.id"
              @click="handleReject(item.id)"
            >
              Reject/Isolate
            </v-btn>
          </div>
          <v-icon
            v-else
            icon="mdi-information-outline"
            size="18"
            color="secondary"
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

const headers = [
  { title: 'Type', key: 'type', sortable: false },
  { title: 'Device', key: 'device', sortable: false },
  { title: 'Status', key: 'status', sortable: false },
  { title: 'Confidence', key: 'confidence', sortable: false },
  { title: 'Detected', key: 'detected_at', sortable: false },
  { title: 'Actions', key: 'actions', sortable: false, align: 'center' },
]

function normalizeType(type) {
  if (!type) return ''
  return type.toUpperCase().replace(/\s+/g, '_')
}

function formatIncidentType(type) {
  const normalized = normalizeType(type)
  if (normalized === 'SERVICE_CRASH' || type === 'Service Crash') return 'Service Crash'
  if (normalized === 'LINK_FAILURE' || type === 'Link Failure') return 'Link Failure'
  if (normalized === 'DDOS_ATTACK' || type === 'DDoS Attack') return 'DDoS Attack'
  return type || 'Unknown'
}

function getIncidentTypeColor(type) {
  const normalized = normalizeType(type)
  if (normalized === 'SERVICE_CRASH' || type === 'Service Crash') return 'error'
  if (normalized === 'LINK_FAILURE' || type === 'Link Failure') return 'warning'
  if (normalized === 'DDOS_ATTACK' || type === 'DDoS Attack') return 'purple'
  return 'secondary'
}

function getStatusColor(status) {
  if (!status) return 'secondary'
  const lower = status.toLowerCase()
  if (lower.includes('manual')) return 'warning'
  if (lower.includes('executing') || lower.includes('healing')) return 'info'
  if (lower.includes('detected') || lower.includes('diagnosing')) return 'secondary'
  if (lower.includes('ready')) return 'cyan'
  if (lower.includes('healed') || lower.includes('resolved')) return 'success'
  return 'secondary'
}

function getConfidencePercentage(confidence) {
  if (confidence == null) return 0
  return Math.min(100, Math.max(0, Math.round(confidence * 100)))
}

function getConfidenceColor(confidence) {
  const pct = getConfidencePercentage(confidence)
  if (pct >= 80) return 'success'
  if (pct >= 60) return 'warning'
  return 'error'
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
    await store.approveHealing(id)
    await store.fetchStatus()
  } catch (error) {
    console.error('Failed to approve healing:', error)
  } finally {
    approvingId.value = null
  }
}

async function handleReject(id) {
  rejectingId.value = id
  try {
    await store.rejectHealing(id)
    await store.fetchStatus()
  } catch (error) {
    console.error('Failed to reject healing:', error)
  } finally {
    rejectingId.value = null
  }
}
</script>

<style scoped>
.incident-card {
  border: 1px solid rgba(148, 163, 184, 0.08);
}

.incident-table :deep(.v-data-table__thead th) {
  font-size: 0.7rem !important;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: rgba(148, 163, 184, 0.9) !important;
  background: transparent !important;
}

.incident-table :deep(.v-data-table__tr:hover) {
  background: rgba(148, 163, 184, 0.05) !important;
}

.state-panel {
  min-height: 200px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
}

.opacity-70 {
  opacity: 0.7;
}
</style>
