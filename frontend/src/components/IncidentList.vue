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

        <!--
          Actions cell: always right-aligned (justify-end) so the Download
          button — present on every row — lands in the exact same x
          position regardless of how many contextual buttons (Approve/
          Reject/Rollback) sit to its left. Previously this used
          justify-center, which shifts Download's position depending on
          its sibling count: centered alone on most rows, but pushed left
          of center when paired with Approve+Reject or Rollback. That
          inconsistency, not the icon choice, was the "conflicting" look.

          Download is also visually demoted (variant="text", muted slate)
          relative to Approve/Reject/Rollback (variant="flat"/"tonal",
          saturated color) since it's a zero-risk, every-row utility
          action and shouldn't compete for attention with the actions
          that actually change system state.
        -->
        <template #item.actions="{ item }">
          <div class="d-flex align-center justify-end ga-1 actions-cell">
            <template v-if="item.status === 'MANUAL_REVIEW'">
              <v-tooltip v-if="!store.canApprove" text="Requires Administrator Privileges" location="top">
                <template #activator="{ props }">
                  <span v-bind="props">
                    <v-btn size="x-small" color="success" variant="flat" disabled icon="mdi-check" />
                  </span>
                </template>
              </v-tooltip>
              <template v-else>
                <v-tooltip text="Approve healing action" location="top">
                  <template #activator="{ props }">
                    <v-btn
                      v-bind="props"
                      size="x-small"
                      color="success"
                      variant="flat"
                      icon="mdi-check"
                      :loading="approvingId === item.id"
                      :disabled="rejectingId === item.id"
                      @click="handleApprove(item.id)"
                    />
                  </template>
                </v-tooltip>
                <v-tooltip text="Reject and return to monitoring" location="top">
                  <template #activator="{ props }">
                    <v-btn
                      v-bind="props"
                      size="x-small"
                      color="error"
                      variant="flat"
                      icon="mdi-close"
                      :loading="rejectingId === item.id"
                      :disabled="approvingId === item.id"
                      @click="handleReject(item.id)"
                    />
                  </template>
                </v-tooltip>
              </template>
            </template>

            <template v-else-if="item.status === 'HEALED' && store.canApprove">
              <v-tooltip text="Roll back this healing action" location="top">
                <template #activator="{ props }">
                  <v-btn
                    v-bind="props"
                    size="x-small"
                    color="amber-accent-4"
                    variant="tonal"
                    icon="mdi-backup-restore"
                    :loading="rollingBackId === item.id"
                    @click="confirmRollback(item)"
                  />
                </template>
              </v-tooltip>
            </template>

            <v-tooltip text="Download healing log" location="top">
              <template #activator="{ props }">
                <v-btn
                  v-bind="props"
                  size="x-small"
                  variant="text"
                  class="download-btn"
                  icon="mdi-download"
                  :loading="downloadingLogId === item.id"
                  @click.stop="downloadLog(item.id)"
                />
              </template>
            </v-tooltip>
          </div>
        </template>
      </v-data-table>

      <!-- Rollback confirmation dialog -->
      <v-dialog v-model="rollbackDialog.show" max-width="440" persistent>
        <v-card class="rollback-dialog rounded-xl pa-2">
          <v-card-title class="d-flex align-center ga-3 pt-4 px-4">
            <v-avatar color="amber-accent-4" variant="tonal" size="36">
              <v-icon icon="mdi-backup-restore" size="20" />
            </v-avatar>
            <span class="text-h6 font-weight-bold text-slate-100">Roll back this healing action?</span>
          </v-card-title>
          <v-card-text class="px-4 pt-2 text-body-2 text-slate-300">
            <p class="mb-2">
              Incident <span class="font-mono text-slate-100">#{{ rollbackDialog.incident?.id }}</span>
              ({{ rollbackDialog.incident?.failure_type_display || rollbackDialog.incident?.failure_type }})
              on <span class="font-weight-bold text-slate-100">{{ rollbackDialog.incident?.device_name }}</span>
              will return to <span class="font-mono">MONITORING</span> for re-evaluation.
            </p>
            <p class="mb-0 text-amber-300">
              This cannot be undone from here — the device will be re-assessed on the next
              monitoring cycle as if the healing action hadn't happened.
            </p>
          </v-card-text>
          <v-card-actions class="px-4 pb-4 pt-3">
            <v-spacer />
            <v-btn variant="text" color="slate-300" :disabled="rollingBackId !== null" @click="cancelRollback">
              Cancel
            </v-btn>
            <v-btn
              variant="flat"
              color="amber-accent-4"
              prepend-icon="mdi-backup-restore"
              :loading="rollingBackId === rollbackDialog.incident?.id"
              @click="proceedRollback"
            >
              Roll Back
            </v-btn>
          </v-card-actions>
        </v-card>
      </v-dialog>

      <!-- Error snackbar for download failures -->
      <v-snackbar v-model="snackbar.show" :color="snackbar.color" :timeout="4000" location="bottom right">
        {{ snackbar.message }}
        <template #actions>
          <v-btn variant="text" @click="snackbar.show = false">Close</v-btn>
        </template>
      </v-snackbar>
    </v-card-text>
  </v-card>
</template>

<script setup>
import { ref, reactive } from 'vue'
import { useNetworkStore } from '@/stores/network'

const store = useNetworkStore()
const approvingId = ref(null)
const rejectingId = ref(null)
const rollingBackId = ref(null)
const downloadingLogId = ref(null)

const rollbackDialog = reactive({
  show: false,
  incident: null,
})

const snackbar = reactive({
  show: false,
  message: '',
  color: 'error',
})

const headers = [
  { title: 'Type', key: 'failure_type', sortable: false },
  { title: 'Device', key: 'device_name', sortable: false },
  { title: 'Status', key: 'status', sortable: false },
  { title: 'Confidence', key: 'confidence_score', sortable: false },
  { title: 'Detected', key: 'detected_at', sortable: false },
  { title: 'Actions', key: 'actions', sortable: false, align: 'end', width: 132 },
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

function showError(message) {
  snackbar.message = message
  snackbar.color = 'error'
  snackbar.show = true
}

async function handleApprove(id) {
  approvingId.value = id
  try {
    await store.approveIncident(id)
  } catch (error) {
    console.error('Failed to approve healing:', error)
    showError(error.response?.data?.detail || 'Failed to approve healing.')
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
    showError(error.response?.data?.detail || 'Failed to reject healing.')
  } finally {
    rejectingId.value = null
  }
}

// Rollback is destructive and irreversible from the UI, so it now goes
// through a confirmation dialog instead of firing immediately on click.
function confirmRollback(item) {
  rollbackDialog.incident = item
  rollbackDialog.show = true
}

function cancelRollback() {
  rollbackDialog.show = false
  rollbackDialog.incident = null
}

async function proceedRollback() {
  const id = rollbackDialog.incident?.id
  if (!id) return
  rollingBackId.value = id
  try {
    await store.rollbackIncident(id)
    rollbackDialog.show = false
    rollbackDialog.incident = null
  } catch (error) {
    console.error('Failed to roll back incident:', error)
    showError(error.response?.data?.detail || 'Failed to roll back incident.')
    // Leave the dialog open on failure so the user can see the error
    // and retry, rather than silently closing on a failed rollback.
  } finally {
    rollingBackId.value = null
  }
}

/**
 * Extract a human-readable error message from an axios error whose response
 * may be a Blob (because we requested responseType: 'blob').
 */
async function extractErrorDetail(error) {
  const data = error?.response?.data

  if (data instanceof Blob) {
    try {
      const text = await data.text()
      if (!text) return null
      try {
        const parsed = JSON.parse(text)
        return parsed?.detail || parsed?.message || text
      } catch {
        return text
      }
    } catch {
      return null
    }
  }

  if (typeof data === 'string') return data
  if (data && typeof data === 'object') return data.detail || data.message || null
  return null
}

async function downloadLog(id) {
  downloadingLogId.value = id
  try {
    const response = await store.downloadIncidentLog(id)
    const blob = response.data instanceof Blob
      ? response.data
      : new Blob([response.data], { type: 'text/plain' })
    const url = URL.createObjectURL(blob)
    const link = document.createElement('a')
    const disposition = response.headers['content-disposition'] || ''
    const filenameMatch = disposition.match(/filename="?([^";]+)"?/i)
    link.href = url
    link.download = filenameMatch?.[1] || `incident_${id}_healing.log`
    document.body.appendChild(link)
    link.click()
    link.remove()
    URL.revokeObjectURL(url)
  } catch (error) {
    // A 401 from the download endpoint is treated by the api interceptor as
    // a session expiry and will already log the user out. For everything
    // else (404, 500, network error, malformed response) we show a message
    // instead of dropping the user's session.
    if (error.response?.status !== 401) {
      const detail = await extractErrorDetail(error)
      console.error('Failed to download healing log:', error)
      showError(detail || 'Failed to download healing log.')
    } else {
      // Backend rejected the token specifically for this endpoint —
      // surface it so it's not a silent logout.
      const detail = await extractErrorDetail(error)
      console.error('Download rejected (401):', detail || error)
      showError(detail || 'Your session is no longer valid for this download.')
    }
  } finally {
    downloadingLogId.value = null
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

/* Fixed-width, right-aligned actions cell so Download's x-position never
   shifts based on how many contextual buttons are next to it. */
.actions-cell {
  min-width: 96px;
}

/* Demoted, low-emphasis style for the always-present Download button —
   deliberately quieter than Approve/Reject/Rollback so it doesn't compete
   for attention with the actions that actually change system state. */
.download-btn {
  opacity: 0.7;
  color: #94a3b8 !important;
}
.download-btn:hover {
  opacity: 1;
  color: #67e8f9 !important;
}

.rollback-dialog {
  background: #0f172a !important;
  border: 1px solid rgba(148, 163, 184, 0.15);
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