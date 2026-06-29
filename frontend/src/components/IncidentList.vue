<template>
  <v-card color="surface" elevation="2" class="h-100">
    <v-card-title>
      <v-icon icon="mdi-alert-octagon" class="mr-2 text-error"></v-icon>
      Active Incidents
    </v-card-title>

    <v-card-text>
      <!-- Empty state -->
      <div v-if="store.latestIncidents.length === 0" class="text-center py-12">
        <v-icon icon="mdi-shield-check" size="64" color="success" class="mb-3"></v-icon>
        <div class="text-body-2 text-secondary">No incidents detected</div>
        <div class="text-caption text-secondary mt-1">System is operating normally</div>
      </div>

      <!-- Loading state -->
      <div v-else-if="store.loading" class="text-center py-8">
        <v-progress-circular indeterminate color="primary" size="40" class="mb-3"></v-progress-circular>
        <div class="text-body-2 text-secondary">Loading incidents...</div>
      </div>

      <!-- Incidents table -->
      <v-table v-else density="compact" hover class="bg-transparent">
        <thead>
          <tr>
            <th class="text-left text-caption text-secondary">Type</th>
            <th class="text-left text-caption text-secondary">Device</th>
            <th class="text-left text-caption text-secondary">Status</th>
            <th class="text-left text-caption text-secondary">Confidence</th>
            <th class="text-left text-caption text-secondary">Detected</th>
            <th class="text-center text-caption text-secondary">Actions</th>
          </tr>
        </thead>

        <tbody>
          <tr v-for="incident in store.latestIncidents" :key="incident.id">
            <!-- Incident Type -->
            <td class="text-left">
              <v-chip
                :color="getIncidentTypeColor(incident.type)"
                size="small"
                variant="flat"
                class="font-weight-medium"
              >
                {{ formatIncidentType(incident.type) }}
              </v-chip>
            </td>

            <!-- Device -->
            <td class="text-left">
              <div class="text-body-2 font-weight-medium">{{ incident.device || 'Unknown' }}</div>
            </td>

            <!-- Status -->
            <td class="text-left">
              <v-chip
                :color="getStatusColor(incident.status)"
                size="x-small"
                variant="tonal"
              >
                {{ incident.status || 'Unknown' }}
              </v-chip>
            </td>

            <!-- Confidence -->
            <td class="text-left">
              <div class="d-flex align-center gap-1">
                <v-progress-linear
                  :model-value="getConfidencePercentage(incident.confidence)"
                  :color="getConfidenceColor(incident.confidence)"
                  height="4"
                  style="min-width: 60px; max-width: 80px"
                ></v-progress-linear>
                <span class="text-caption text-secondary" style="min-width: 40px">
                  {{ getConfidencePercentage(incident.confidence) }}%
                </span>
              </div>
            </td>

            <!-- Detected Time -->
            <td class="text-left">
              <div class="text-caption text-secondary">{{ formatDetectedTime(incident.detected_at) }}</div>
            </td>

            <!-- Actions -->
            <td class="text-center">
              <!-- Manual Review Actions -->
              <div v-if="incident.status === 'Manual Review'" class="d-flex justify-center gap-1">
                <v-btn
                  size="x-small"
                  color="success"
                  variant="tonal"
                  :loading="approvingId === incident.id"
                  @click="approveHealing(incident.id)"
                  prepend-icon="mdi-check"
                >
                  Approve
                </v-btn>
                <v-btn
                  size="x-small"
                  color="error"
                  variant="tonal"
                  :loading="rejectingId === incident.id"
                  @click="rejectHealing(incident.id)"
                  prepend-icon="mdi-close"
                >
                  Reject
                </v-btn>
              </div>

              <!-- Other states: info icon only -->
              <div v-else class="d-flex justify-center">
                <v-icon size="small" color="secondary" icon="mdi-information-outline"></v-icon>
              </div>
            </td>
          </tr>
        </tbody>
      </v-table>
    </v-card-text>
  </v-card>
</template>

<script setup>
import { ref } from 'vue'
import { useNetworkStore } from '@/stores/network'

const store = useNetworkStore()
const approvingId = ref(null)
const rejectingId = ref(null)

function formatIncidentType(type) {
  if (type === 'SERVICE_CRASH') return 'Service Crash'
  if (type === 'LINK_FAILURE') return 'Link Failure'
  if (type === 'DDOS_ATTACK') return 'DDoS Attack'
  return type || 'Unknown'
}

function getIncidentTypeColor(type) {
  if (type === 'SERVICE_CRASH') return 'error'
  if (type === 'LINK_FAILURE') return 'warning'
  if (type === 'DDOS_ATTACK') return 'purple'
  return 'secondary'
}

function getStatusColor(status) {
  if (!status) return 'secondary'

  const statusLower = status.toLowerCase()
  if (statusLower.includes('manual')) return 'warning'
  if (statusLower.includes('executing') || statusLower.includes('healing')) return 'info'
  if (statusLower.includes('detected') || statusLower.includes('analyzing')) return 'secondary'
  if (statusLower.includes('resolved')) return 'success'

  return 'secondary'
}

function getConfidencePercentage(confidence) {
  if (confidence == null) return 0

  const percentage = Math.round(confidence * 100)
  return Math.min(100, Math.max(0, percentage))
}

function getConfidenceColor(confidence) {
  const percentage = getConfidencePercentage(confidence)
  if (percentage >= 80) return 'success'
  if (percentage >= 60) return 'warning'
  return 'error'
}

function formatDetectedTime(isoString) {
  if (!isoString) return '--'

  try {
    const date = new Date(isoString)
    const now = new Date()
    const diffMs = now - date
    const diffSecs = Math.floor(diffMs / 1000)
    const diffMins = Math.floor(diffSecs / 60)
    const diffHours = Math.floor(diffMins / 60)
    const diffDays = Math.floor(diffHours / 24)

    if (diffSecs < 60) return `${diffSecs}s ago`
    if (diffMins < 60) return `${diffMins}m ago`
    if (diffHours < 24) return `${diffHours}h ago`
    return `${diffDays}d ago`
  } catch (e) {
    return '--'
  }
}

async function approveHealing(incidentId) {
  approvingId.value = incidentId
  try {
    await store.approveIncident(incidentId)
  } catch (error) {
    console.error('Failed to approve healing:', error)
  } finally {
    approvingId.value = null
  }
}

async function rejectHealing(incidentId) {
  rejectingId.value = incidentId
  try {
    await store.rejectIncident(incidentId)
  } catch (error) {
    console.error('Failed to reject healing:', error)
  } finally {
    rejectingId.value = null
  }
}
</script>

<style scoped>
.gap-1 {
  gap: 0.25rem;
}

:deep(.v-table__wrapper) {
  background-color: transparent;
}

:deep(tbody tr:hover) {
  background-color: rgba(148, 163, 184, 0.05);
}
</style>