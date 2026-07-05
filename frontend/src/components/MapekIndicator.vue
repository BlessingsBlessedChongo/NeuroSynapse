<template>
  <v-card color="surface" elevation="2" class="mapek-card h-100">
    <v-card-title class="d-flex align-center">
      <v-icon icon="mdi-sync-circle" class="mr-2 text-primary" />
      MAPE-K Autonomic Loop
    </v-card-title>

    <v-card-subtitle class="text-medium-emphasis pb-2">
      Real-time execution stage of the self-healing control cycle
    </v-card-subtitle>

    <v-card-text>
      <v-timeline side="end" align="start" density="compact" truncate-line="both">
        <v-timeline-item
          v-for="phase in phases"
          :key="phase.id"
          :dot-color="phase.active ? 'cyan' : 'grey-darken-2'"
          :size="phase.active ? 'default' : 'x-small'"
          fill-dot
        >
          <template #icon>
            <v-icon
              :icon="phase.icon"
              :color="phase.active ? '#0f172a' : 'rgba(148, 163, 184, 0.7)'"
              :size="phase.active ? 22 : 16"
              :class="{ 'phase-icon-active': phase.active }"
            />
          </template>

          <div class="d-flex align-center justify-space-between">
            <div>
              <div
                class="text-body-2 font-weight-bold"
                :class="phase.active ? 'text-cyan' : 'text-medium-emphasis'"
              >
                Phase {{ phase.number }} — {{ phase.label }}
              </div>
              <div class="text-caption text-medium-emphasis mt-1">
                {{ phase.description }}
              </div>
            </div>

            <v-chip
              v-if="phase.active"
              size="x-small"
              color="cyan"
              variant="flat"
              class="ml-3 font-weight-bold"
              prepend-icon="mdi-radiobox-marked"
            >
              ACTIVE
            </v-chip>
          </div>
        </v-timeline-item>
      </v-timeline>

      <v-alert
        variant="tonal"
        :color="activePhase === 4 ? 'success' : activePhase === 0 ? 'info' : 'cyan'"
        density="comfortable"
        class="mt-4"
      >
        <div class="d-flex align-center justify-space-between flex-wrap ga-2">
          <div>
            <div class="text-caption text-medium-emphasis mb-1">Current Loop Phase</div>
            <div class="text-body-2 font-weight-bold">{{ activePhaseLabel }}</div>
          </div>
          <div class="text-caption text-medium-emphasis">{{ activePhaseHint }}</div>
        </div>
      </v-alert>
    </v-card-text>
  </v-card>
</template>

<script setup>
import { computed } from 'vue'
import { useNetworkStore } from '@/stores/network'

const store = useNetworkStore()

const activePhase = computed(() => {
  const hasExecutingHealing = store.recentHealings.some(
    h => h.status === 'Executing',
  )

  if (hasExecutingHealing) {
    return 3
  }

  const openIncidents = store.latestIncidents.filter(incident => {
    const status = incident.status || ''
    return !['Healed', 'Failed', 'Rolled Back'].includes(status)
  })

  const hasPlanPhase = openIncidents.some(incident => {
    const status = incident.status || ''
    return status === 'Ready for Action' || status === 'Manual Review'
  })

  if (hasPlanPhase) {
    return 2
  }

  const hasAnalyzePhase = openIncidents.some(incident => {
    const status = incident.status || ''
    return status === 'Detected' || status === 'Diagnosing'
  })

  if (hasAnalyzePhase) {
    return 1
  }

  if (store.openIncidents === 0 && store.healedToday > 0) {
    return 4
  }

  if (store.openIncidents === 0 && store.healedToday === 0) {
    return 0
  }

  return 0
})

const phaseDefinitions = [
  {
    id: 'monitor',
    number: 0,
    label: 'MONITOR',
    description: 'Continuously observing telemetry, topology, and device health.',
    icon: 'mdi-eye',
  },
  {
    id: 'analyze',
    number: 1,
    label: 'ANALYZE',
    description: 'Detecting anomalies and diagnosing root causes.',
    icon: 'mdi-brain',
  },
  {
    id: 'plan',
    number: 2,
    label: 'PLAN',
    description: 'Planning remediation actions and awaiting operator validation.',
    icon: 'mdi-cog',
  },
  {
    id: 'execute',
    number: 3,
    label: 'EXECUTE',
    description: 'Executing healing actions across the network fabric.',
    icon: 'mdi-flash',
  },
  {
    id: 'knowledge',
    number: 4,
    label: 'KNOWLEDGE',
    description: 'Learning from resolved incidents to improve future responses.',
    icon: 'mdi-check-decagram',
  },
]

const phases = computed(() =>
  phaseDefinitions.map(phase => ({
    ...phase,
    active: activePhase.value === phase.number,
  })),
)

const activePhaseLabel = computed(
  () => phaseDefinitions.find(p => p.number === activePhase.value)?.label || 'MONITOR',
)

const activePhaseHint = computed(() => {
  switch (activePhase.value) {
    case 1:
      return 'Incident detection and AI diagnosis in progress.'
    case 2:
      return 'Healing plan prepared — awaiting approval or review.'
    case 3:
      return 'Automated remediation scripts are executing.'
    case 4:
      return 'Resolved incidents are feeding the knowledge base.'
    default:
      return 'System is monitoring network health with no active anomalies.'
  }
})
</script>

<style scoped>
.mapek-card {
  border: 1px solid rgba(148, 163, 184, 0.08);
}

.text-cyan {
  color: #00e5ff !important;
}

.phase-icon-active {
  transform: scale(1.15);
  filter: drop-shadow(0 0 6px rgba(0, 229, 255, 0.6));
}

:deep(.v-timeline-item__dot) {
  transition: all 0.3s ease;
}

:deep(.v-timeline-item__dot.bg-cyan) {
  box-shadow: 0 0 0 4px rgba(0, 229, 255, 0.2);
}
</style>
