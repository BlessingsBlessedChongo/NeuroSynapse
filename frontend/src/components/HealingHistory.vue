<template>
  <v-card color="surface" elevation="2" class="healing-card h-100">
    <v-card-title class="d-flex align-center">
      <v-icon icon="mdi-bandage" class="mr-2 text-info" />
      Self-Healing Event Log
    </v-card-title>

    <v-card-subtitle class="text-medium-emphasis pb-2">
      Chronological record of executed network mitigations
    </v-card-subtitle>

    <v-card-text class="pa-0">
      <div v-if="store.recentHealings.length === 0" class="empty-state text-center py-12 px-4">
        <v-icon icon="mdi-history" size="56" color="secondary" class="mb-4 opacity-60" />
        <p class="text-body-1 text-medium-emphasis mb-0">
          No self-healing events logged for this epoch.
        </p>
      </div>

      <v-list v-else bg-color="transparent" class="py-0 healing-list">
        <template v-for="(healing, index) in store.recentHealings" :key="healing.id">
          <v-list-item class="healing-item px-4 py-3">
            <template #prepend>
              <v-avatar
                :color="runtimeStatusColor(healing.status)"
                variant="tonal"
                size="36"
                rounded="lg"
              >
                <v-icon
                  :icon="runtimeStatusIcon(healing.status)"
                  size="20"
                />
              </v-avatar>
            </template>

            <v-list-item-title class="font-weight-bold text-body-2">
              {{ healing.action || 'Unknown Script' }}
            </v-list-item-title>

            <v-list-item-subtitle class="text-medium-emphasis">
              Incident #{{ healing.incident_id }}
              <span class="mx-1">·</span>
              Duration: {{ formatDuration(healing) }}
            </v-list-item-subtitle>

            <template #append>
              <div class="text-right">
                <v-chip
                  size="x-small"
                  :color="runtimeStatusColor(healing.status)"
                  variant="flat"
                  class="font-weight-bold mb-1"
                >
                  {{ runtimeStatusLabel(healing.status) }}
                </v-chip>
                <div class="text-caption text-medium-emphasis">
                  {{ formatTimestamp(healing.created_at) }}
                </div>
              </div>
            </template>
          </v-list-item>

          <v-divider v-if="index < store.recentHealings.length - 1" class="mx-4" />
        </template>
      </v-list>
    </v-card-text>
  </v-card>
</template>

<script setup>
import { useNetworkStore } from '@/stores/network'

const store = useNetworkStore()

function runtimeStatusLabel(status) {
  if (status === 'Executed') return 'Success'
  if (status === 'Failed') return 'Failed'
  if (status === 'Executing') return 'Running'
  return status || 'Pending'
}

function runtimeStatusColor(status) {
  if (status === 'Executed') return 'success'
  if (status === 'Failed') return 'error'
  if (status === 'Executing') return 'info'
  return 'secondary'
}

function runtimeStatusIcon(status) {
  if (status === 'Executed') return 'mdi-check-circle'
  if (status === 'Failed') return 'mdi-close-circle'
  if (status === 'Executing') return 'mdi-loading'
  return 'mdi-clock-outline'
}

function formatTimestamp(isoString) {
  if (!isoString) return '--'
  try {
    return new Date(isoString).toLocaleString([], {
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
    })
  } catch {
    return '--'
  }
}

function formatDuration(healing) {
  if (healing.duration_ms != null) {
    const ms = Number(healing.duration_ms)
    if (ms < 1000) return `${ms}ms`
    return `${(ms / 1000).toFixed(1)}s`
  }

  if (healing.completed_at && healing.created_at) {
    const start = new Date(healing.created_at).getTime()
    const end = new Date(healing.completed_at).getTime()
    const diffMs = end - start
    if (diffMs >= 0) {
      if (diffMs < 1000) return `${diffMs}ms`
      return `${(diffMs / 1000).toFixed(1)}s`
    }
  }

  if (healing.status === 'Executing') return 'In progress'
  return '—'
}
</script>

<style scoped>
.healing-card {
  border: 1px solid rgba(148, 163, 184, 0.08);
}

.healing-list {
  max-height: 420px;
  overflow-y: auto;
}

.empty-state {
  min-height: 200px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
}

.opacity-60 {
  opacity: 0.6;
}
</style>
