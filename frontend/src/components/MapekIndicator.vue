<template>
  <v-card color="surface" elevation="2">
    <v-card-title>
      <v-icon icon="mdi-sync-circle" class="mr-2 text-primary"></v-icon>
      MAPE-K Loop Status
    </v-card-title>

    <v-card-subtitle class="text-secondary">
      Autonomic Control Cycle Phase
    </v-card-subtitle>

    <v-card-text>
      <v-timeline align="start" side="end" density="compact">
        <v-timeline-item
          v-for="phase in phases"
          :key="phase.id"
          :dot-color="phase.active ? 'primary' : 'rgb(75, 85, 99)'"
          :size="phase.active ? 'large' : 'small'"
          fill-dot
        >
          <template v-slot:icon>
            <v-icon
              :icon="phase.icon"
              :color="phase.active ? 'white' : 'rgb(148, 163, 184)'"
              :class="{ 'animate-spin': phase.active }"
            ></v-icon>
          </template>

          <div class="d-flex align-center justify-space-between">
            <div>
              <div
                class="font-weight-bold text-body-2"
                :class="phase.active ? 'text-primary' : 'text-secondary'"
              >
                {{ phase.number }}. {{ phase.label }}
              </div>
              <div class="text-caption text-secondary mt-1">
                {{ phase.description }}
              </div>
            </div>

            <v-chip
              v-if="phase.active"
              size="x-small"
              color="primary"
              variant="flat"
              class="ml-3"
              prepend-icon="mdi-radiobox-marked"
            >
              ACTIVE
            </v-chip>
          </div>
        </v-timeline-item>
      </v-timeline>

      <v-alert variant="tonal" color="surface" class="mt-6 py-3">
        <div class="d-flex align-center justify-space-between">
          <div>
            <div class="text-caption text-secondary mb-1">Current loop phase</div>
            <div class="text-body-2 font-weight-medium">{{ activePhaseLabel }}</div>
          </div>
          <div class="text-caption text-secondary">
            {{ activePhaseHint }}
          </div>
        </div>
      </v-alert>

      <v-divider class="my-6"></v-divider>

      <v-row dense>
        <v-col cols="12" sm="6">
          <div class="text-caption text-secondary text-uppercase font-weight-bold mb-2">
            <v-icon icon="mdi-alert-circle" size="16" class="mr-1"></v-icon>
            Open Incidents
          </div>
          <div class="text-h6 font-weight-bold text-error">{{ store.openIncidents }}</div>
        </v-col>

        <v-col cols="12" sm="6">
          <div class="text-caption text-secondary text-uppercase font-weight-bold mb-2">
            <v-icon icon="mdi-check-circle" size="16" class="mr-1"></v-icon>
            Healed Today
          </div>
          <div class="text-h6 font-weight-bold text-success">{{ store.healedToday }}</div>
        </v-col>
      </v-row>
    </v-card-text>
  </v-card>
</template>

<script setup>
import { computed } from 'vue'
import { useNetworkStore } from '@/stores/network'

const store = useNetworkStore()

const activePhase = computed(() => {
  const openIncidents = store.openIncidents
  const latestIncident = store.latestIncident

  // Phase 0 (MONITOR): Default state when no active incidents
  // This resets from KNOWLEDGE phase if all incidents are resolved
  if (openIncidents === 0) {
    return 0
  }

  // Phase detection based on latest incident status
  if (latestIncident) {
    const status = latestIncident.status?.toLowerCase() || ''

    // Phase 1 (ANALYZE): Detecting and diagnosing
    if (status.includes('detected') || status.includes('detecting') || status.includes('analyzing')) {
      return 1
    }

    // Phase 2 (PLAN): Planning remediation
    if (status.includes('manual') || status.includes('ready') || status.includes('planned')) {
      return 2
    }

    // Phase 3 (EXECUTE): Healing in progress
    if (status.includes('executing') || status.includes('healing')) {
      return 3
    }
  }

  // Return to MONITOR if no incidents
  return 0
})

const phases = computed(() => [
  {
    id: 'monitor',
    number: 0,
    label: 'MONITOR',
    description: 'Continuously observing telemetry, topology and device health.',
    icon: 'mdi-eye',
    active: activePhase.value === 0,
  },
  {
    id: 'analyze',
    number: 1,
    label: 'ANALYZE',
    description: 'Detecting anomalies and diagnosing root causes.',
    icon: 'mdi-brain',
    active: activePhase.value === 1,
  },
  {
    id: 'plan',
    number: 2,
    label: 'PLAN',
    description: 'Planning remediation actions and awaiting approval.',
    icon: 'mdi-lightbulb-on',
    active: activePhase.value === 2,
  },
  {
    id: 'execute',
    number: 3,
    label: 'EXECUTE',
    description: 'Executing healing actions across the network.',
    icon: 'mdi-flash',
    active: activePhase.value === 3,
  },
  {
    id: 'knowledge',
    number: 4,
    label: 'KNOWLEDGE',
    description: 'Learning from resolved incidents for future improvements.',
    icon: 'mdi-check-decagram',
    active: activePhase.value === 4,
  },
])

const activePhaseLabel = computed(() => phases.value.find(p => p.active)?.label || 'MONITOR')

const activePhaseHint = computed(() => {
  switch (activePhase.value) {
    case 1:
      return 'Incident detection and diagnosis in progress.'
    case 2:
      return 'Healing plan prepared and awaiting validation.'
    case 3:
      return 'Automated remediation actions are running.'
    case 4:
      return 'Resolved incidents are feeding system learning.'
    default:
      return 'System is monitoring network health.'
  }
})
</script>

<style scoped>
@keyframes spin {
  from {
    transform: rotate(0deg);
  }
  to {
    transform: rotate(360deg);
  }
}

.animate-spin {
  animation: spin 2s linear infinite;
}

:deep(.v-timeline-item__dot) {
  transition: all 0.25s ease;
}

:deep(.v-timeline-item__dot.primary) {
  box-shadow: 0 0 0 4px rgba(59, 130, 246, 0.18);
}
</style>