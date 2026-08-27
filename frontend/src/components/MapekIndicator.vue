<template>
  <v-card class="mapek-card rounded-xl pa-5 h-100 d-flex flex-column" elevation="0">
    <!-- Header -->
    <v-card-title class="d-flex align-center justify-space-between pa-0 mb-4 flex-shrink-0">
      <div class="d-flex align-center ga-3">
        <v-avatar color="cyan-accent-3" variant="tonal" size="38">
          <v-icon icon="mdi-sync-circle" size="24" />
        </v-avatar>
        <div>
          <h2 class="text-h6 font-weight-bold text-slate-100 mb-0 leading-tight">
            MAPE-K Autonomic Loop
          </h2>
          <p class="text-caption text-slate-400 mb-0 font-weight-regular mt-1">
            Real-time execution stage of the self-healing control cycle
          </p>
        </div>
      </div>
      <v-chip
        size="small"
        variant="tonal"
        color="cyan-accent-3"
        class="font-weight-bold font-mono"
      >
        <v-icon icon="mdi-orbit" start size="14" />
        LOOP ACTIVE
      </v-chip>
    </v-card-title>

    <!-- Timeline Content -->
    <div class="flex-grow-1 d-flex flex-column justify-space-between">
      <div class="timeline-container my-auto">
        <v-timeline side="end" align="start" density="compact" truncate-line="both" class="mapek-timeline">
          <v-timeline-item
            v-for="phase in phases"
            :key="phase.id"
            :dot-color="phase.active ? 'cyan-accent-3' : 'slate-700'"
            :size="phase.active ? 'small' : 'x-small'"
            fill-dot
            class="mb-3"
          >
            <template #icon>
              <v-icon
                :icon="phase.icon"
                :color="phase.active ? '#0f172a' : 'rgba(148, 163, 184, 0.6)'"
                :size="phase.active ? 16 : 12"
                :class="{ 'phase-icon-active': phase.active }"
              />
            </template>

            <div
              class="timeline-content-box pa-3 rounded-lg"
              :class="{ 'active-phase-box': phase.active }"
            >
              <div class="d-flex align-center justify-space-between ga-2">
                <div class="min-w-0">
                  <div
                    class="text-body-2 font-weight-bold font-mono"
                    :class="phase.active ? 'text-cyan-accent-3' : 'text-slate-200'"
                  >
                    Phase {{ phase.number }} — {{ phase.label }}
                  </div>
                  <div class="text-caption text-slate-400 mt-1 leading-normal">
                    {{ phase.description }}
                  </div>
                </div>

                <v-chip
                  v-if="phase.active"
                  size="x-small"
                  color="cyan-accent-3"
                  variant="flat"
                  class="font-weight-bold font-mono flex-shrink-0 text-slate-900"
                  prepend-icon="mdi-radiobox-marked"
                >
                  ACTIVE
                </v-chip>
              </div>
            </div>
          </v-timeline-item>
        </v-timeline>
      </div>

      <!-- Active Phase Alert Banner -->
      <v-sheet
        rounded="lg"
        class="pa-3 status-banner d-flex align-center ga-3 mt-4 flex-shrink-0"
        :class="`border-phase-${activePhase}`"
      >
        <v-avatar :color="alertColor" variant="tonal" size="36" class="flex-shrink-0 ns-pulse-glow">
          <v-icon :icon="alertIcon" size="20" />
        </v-avatar>
        <div class="d-flex flex-column flex-grow-1 min-w-0">
          <div class="d-flex align-center justify-space-between flex-wrap ga-2">
            <span class="text-caption text-slate-400 font-mono text-uppercase font-weight-bold">
              Current Loop Phase
            </span>
            <span class="text-caption text-slate-300 font-mono text-truncate">{{ activePhaseHint }}</span>
          </div>
          <span class="text-body-2 font-weight-bold text-slate-100 font-mono">
            {{ activePhaseLabel }}
          </span>
        </div>
      </v-sheet>
    </div>
  </v-card>
</template>

<script setup>
import { computed } from 'vue'
import { useNetworkStore } from '@/stores/network'

const store = useNetworkStore()

const activePhase = computed(() => {
  const hasExecutingHealing = store.recentHealings.some(
    (h) => h.status === 'EXECUTING' || h.status === 'VALIDATING',
  )

  if (hasExecutingHealing) return 3

  const openIncidents = store.latestIncidents.filter((incident) => {
    const status = incident.status || ''
    return !['HEALED', 'FAILED', 'ROLLED_BACK'].includes(status)
  })

  const hasPlanPhase = openIncidents.some((incident) => {
    const status = incident.status || ''
    return status === 'READY_FOR_ACTION' || status === 'MANUAL_REVIEW' || status === 'HEALING'
  })

  if (hasPlanPhase) return 2

  const hasAnalyzePhase = openIncidents.some((incident) => {
    const status = incident.status || ''
    return status === 'DETECTED' || status === 'DIAGNOSING'
  })

  if (hasAnalyzePhase) return 1

  if (store.openIncidents === 0 && store.resolvedIncidents > 0) return 4

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
  phaseDefinitions.map((phase) => ({
    ...phase,
    active: activePhase.value === phase.number,
  })),
)

const activePhaseLabel = computed(
  () => phaseDefinitions.find((p) => p.number === activePhase.value)?.label || 'MONITOR',
)

const activePhaseHint = computed(() => {
  switch (activePhase.value) {
    case 1: return 'Incident detection & AI diagnosis in progress.'
    case 2: return 'Healing plan prepared — awaiting review.'
    case 3: return 'Automated remediation scripts executing.'
    case 4: return 'Resolved incidents feeding knowledge base.'
    default: return 'System monitoring health — no active anomalies.'
  }
})

const alertColor = computed(() => {
  switch (activePhase.value) {
    case 1: return 'amber-accent-3'
    case 2: return 'cyan-accent-3'
    case 3: return 'violet-accent'
    case 4: return 'emerald-accent-4'
    default: return 'slate-400'
  }
})

const alertIcon = computed(() => {
  switch (activePhase.value) {
    case 1: return 'mdi-magnify-scan'
    case 2: return 'mdi-file-cog-outline'
    case 3: return 'mdi-lightning-bolt'
    case 4: return 'mdi-database-check'
    default: return 'mdi-shield-check-outline'
  }
})
</script>

<style scoped>
.mapek-card {
  background: rgba(15, 23, 42, 0.65) !important;
  backdrop-filter: blur(16px);
  -webkit-backdrop-filter: blur(16px);
  border: 1px solid rgba(148, 163, 184, 0.12);
}

.timeline-content-box {
  background: rgba(30, 41, 59, 0.35);
  border: 1px solid rgba(148, 163, 184, 0.08);
  transition: all 0.2s ease;
}

.timeline-content-box:hover {
  transform: translateY(-1px);
  border-color: rgba(0, 229, 255, 0.2);
}

.active-phase-box {
  background: rgba(0, 229, 255, 0.06) !important;
  border: 1px solid rgba(0, 229, 255, 0.3) !important;
}

/* Pixel-consistent timeline node/connector spacing */
.mapek-timeline :deep(.v-timeline-item__body) {
  padding-block-end: 0;
}

.mapek-timeline :deep(.v-timeline-divider) {
  align-self: flex-start;
}

.mapek-timeline :deep(.v-timeline-divider__dot) {
  box-shadow: none;
}

.mapek-timeline :deep(.v-timeline-divider__inner-dot) {
  transition: filter 0.25s ease;
}

.status-banner {
  background: rgba(7, 16, 24, 0.75) !important;
  border: 1px solid rgba(148, 163, 184, 0.12);
}

.border-phase-0 { border-left: 3px solid #94a3b8 !important; }
.border-phase-1 { border-left: 3px solid #ffab00 !important; }
.border-phase-2 { border-left: 3px solid #00e5ff !important; }
.border-phase-3 { border-left: 3px solid #A855F7 !important; }
.border-phase-4 { border-left: 3px solid #00e676 !important; }

.phase-icon-active {
  filter: drop-shadow(0 0 4px rgba(0, 229, 255, 0.8));
}

.text-cyan-accent-3 {
  color: #00e5ff !important;
}

.leading-tight { line-height: 1.15; }
.leading-normal { line-height: 1.35; }

.font-mono {
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace !important;
}
</style>