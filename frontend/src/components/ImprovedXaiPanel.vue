<template>
  <v-card class="xai-card rounded-xl pa-2 h-100 d-flex flex-column" elevation="0">
    <!-- Header -->
    <v-card-title class="d-flex align-center justify-space-between py-3 px-4 flex-shrink-0">
      <div class="d-flex align-center ga-2">
        <v-avatar color="violet" variant="tonal" size="36" class="mr-1">
          <v-icon icon="mdi-brain" size="20" />
        </v-avatar>
        <div>
          <span class="text-h6 font-weight-bold text-slate-100">Explainable AI Diagnosis</span>
          <p class="text-caption text-slate-400 mb-0 font-weight-regular">
            Plain-English diagnosis with supporting telemetry evidence
          </p>
        </div>
      </div>
      <v-chip
        v-if="hasExplanation"
        size="small"
        variant="tonal"
        :color="confidenceLevelColor"
        class="font-weight-bold font-mono"
      >
        <v-icon icon="mdi-shield-check-outline" start size="14" />
        {{ confidencePercentage }}% · {{ store.xaiExplanation.confidence_level }}
      </v-chip>
    </v-card-title>

    <!-- Main Content Container with Fixed Flex Overflow -->
    <div class="card-body-wrapper flex-grow-1 px-4 pb-4">
      <!-- Loading Overlay -->
      <v-overlay
        :model-value="store.xaiLoading && !hasExplanation"
        contained
        class="align-center justify-center rounded-lg"
        scrim="rgba(15, 23, 42, 0.85)"
      >
        <div class="text-center pa-4">
          <v-progress-circular indeterminate color="violet-accent" size="48" width="4" />
          <p class="text-body-2 text-slate-300 font-weight-medium mt-4 mb-0">
            Analyzing incident with AI models…
          </p>
        </div>
      </v-overlay>

      <!-- State 1: No Incident -->
      <div v-if="!store.latestIncident" class="state-panel text-center pa-6">
        <v-avatar color="emerald-accent-4" variant="tonal" size="64" class="mb-4">
          <v-icon icon="mdi-shield-check" size="32" />
        </v-avatar>
        <p class="text-h6 font-weight-bold text-slate-100 mb-1">System Status: Stable</p>
        <p class="text-caption text-slate-400 max-w-sm mb-0">
          AI models are continuously monitoring telemetry. Diagnostic explanations will populate here automatically.
        </p>
      </div>

      <!-- State 2: Error -->
      <div v-else-if="store.xaiError && !hasExplanation" class="state-panel text-center pa-6">
        <v-avatar color="rose-400" variant="tonal" size="56" class="mb-3">
          <v-icon icon="mdi-alert-circle-outline" size="28" />
        </v-avatar>
        <p class="text-body-2 text-rose-300 mb-4">{{ store.xaiError }}</p>
        <v-btn
          variant="tonal"
          color="cyan-accent-3"
          size="small"
          prepend-icon="mdi-refresh"
          :loading="retrying"
          @click="retryExplanation"
        >
          Retry Analysis
        </v-btn>
      </div>

      <!-- State 3: Loading (First Fetch) -->
      <div v-else-if="store.xaiLoading && !hasExplanation" class="state-panel text-center pa-6">
        <v-progress-circular indeterminate color="violet-accent" size="40" class="mb-3" />
        <p class="text-caption text-slate-400 mb-0 font-mono">Loading diagnosis explanation…</p>
      </div>

      <!-- State 4: No Explanation Recorded -->
      <div v-else-if="!hasExplanation" class="state-panel text-center pa-6">
        <v-avatar color="slate-600" variant="tonal" size="48" class="mb-3">
          <v-icon icon="mdi-information-outline" size="24" />
        </v-avatar>
        <p class="text-body-2 text-slate-400 mb-0">
          No diagnostic explanation generated for this incident yet.
        </p>
      </div>

      <!-- State 5: Main Explanation View -->
      <div v-else class="scrollable-content pr-2">
        <!-- Banner Card -->
        <div class="incident-header-banner rounded-lg pa-4 mb-4">
          <div class="d-flex align-center justify-space-between flex-wrap ga-2">
            <div>
              <p class="text-caption text-violet-accent font-weight-bold text-uppercase mb-1 font-mono">
                Active Target
              </p>
              <h3 class="text-h6 font-weight-bold text-slate-100 leading-tight">
                {{ incidentTypeLabel }}
              </h3>
              <p class="text-caption text-slate-400 mb-0 font-mono">
                Device: <span class="text-slate-200 font-weight-medium">{{ store.latestIncident.device_name }}</span> · Detected {{ formattedDetectionTime }}
              </p>
            </div>
            <v-chip size="small" variant="flat" :color="statusChipColor" class="font-weight-bold text-uppercase">
              {{ store.latestIncident.status_display || store.latestIncident.status }}
            </v-chip>
          </div>
        </div>

        <!-- Target Context Alert -->
        <v-sheet
          v-if="store.xaiExplanation?.concrete_context"
          rounded="lg"
          class="pa-3 mb-4 context-sheet d-flex align-start ga-3"
        >
          <v-icon icon="mdi-target-account" color="amber-accent-3" size="20" class="mt-1" />
          <div>
            <p class="text-caption font-weight-bold text-amber-accent-3 text-uppercase mb-1 font-mono">
              Target Context
            </p>
            <p class="text-caption text-slate-200 mb-0 font-mono">
              {{ store.xaiExplanation.concrete_context }}
            </p>
          </div>
        </v-sheet>

        <!-- Diagnosis Summary -->
        <section class="mb-4">
          <p class="text-caption text-uppercase text-slate-400 font-weight-bold mb-2 d-flex align-center ga-1 font-mono">
            <v-icon icon="mdi-text-box-outline" size="14" color="violet-accent" />
            Diagnosis Summary
          </p>
          <v-sheet rounded="lg" class="pa-3 dark-subpanel">
            <p class="text-body-2 text-slate-200 mb-0 leading-relaxed">
              {{ store.xaiExplanation.summary }}
            </p>
          </v-sheet>
        </section>

        <!-- Key Evidence -->
        <section class="mb-4">
          <p class="text-caption text-uppercase text-slate-400 font-weight-bold mb-2 d-flex align-center ga-1 font-mono">
            <v-icon icon="mdi-file-search-outline" size="14" color="cyan-accent-3" />
            Telemetry Evidence
          </p>
          <v-sheet v-if="keyEvidence.length > 0" rounded="lg" class="pa-3 dark-subpanel">
            <ul class="evidence-list mb-0">
              <li v-for="(evidence, index) in keyEvidence" :key="index" class="text-body-2 text-slate-300 font-mono">
                <span class="text-cyan-accent-3 mr-1">></span> {{ evidence }}
              </li>
            </ul>
          </v-sheet>
          <p v-else class="text-caption text-slate-400 mb-0 italic">
            No specific telemetry points attached.
          </p>
        </section>

        <!-- Operational Impact -->
        <section class="mb-4">
          <p class="text-caption text-uppercase text-slate-400 font-weight-bold mb-2 d-flex align-center ga-1 font-mono">
            <v-icon icon="mdi-lightbulb-on-outline" size="14" color="amber-accent-3" />
            Operational Impact
          </p>
          <v-sheet rounded="lg" class="pa-3 dark-subpanel">
            <p class="text-body-2 text-slate-300 mb-0 leading-relaxed">
              {{ store.xaiExplanation.what_this_means }}
            </p>
          </v-sheet>
        </section>

        <!-- Contributing Factors -->
        <section v-if="contributingFactors.length > 0" class="mb-2">
          <p class="text-caption text-uppercase text-slate-400 font-weight-bold mb-2 d-flex align-center ga-1 font-mono">
            <v-icon icon="mdi-chart-bell-curve" size="14" color="rose-400" />
            Contributing Factors
          </p>
          <div class="d-flex flex-column ga-2">
            <v-sheet
              v-for="(factor, index) in contributingFactors"
              :key="index"
              rounded="lg"
              class="pa-2 px-3 factor-sheet d-flex align-center ga-2"
            >
              <v-icon icon="mdi-alert-circle-outline" size="16" color="rose-400" />
              <span class="text-caption text-rose-200 font-mono">{{ factor }}</span>
            </v-sheet>
          </div>
        </section>
      </div>
    </div>
  </v-card>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import { useNetworkStore } from '@/stores/network'

const store = useNetworkStore()
const retrying = ref(false)
const loadingIncidentId = ref(null)

// Robust check to ensure explanation actually exists and isn't an empty object
const hasExplanation = computed(() => {
  return Boolean(
    store.xaiExplanation && 
    typeof store.xaiExplanation === 'object' && 
    Object.keys(store.xaiExplanation).length > 0
  )
})

const incidentTypeLabel = computed(
  () => store.latestIncident?.failure_type_display || store.latestIncident?.failure_type || 'Unknown Incident',
)

const formattedDetectionTime = computed(() => {
  const detectedAt = store.latestIncident?.detected_at
  if (!detectedAt) return 'Unknown'
  try {
    return new Date(detectedAt).toLocaleString([], {
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
    })
  } catch {
    return 'Unknown'
  }
})

const confidencePercentage = computed(() => {
  const confidence = store.xaiExplanation?.confidence ?? store.latestIncident?.confidence_score
  if (confidence == null) return 0
  return Math.min(100, Math.max(0, Math.round(confidence * 100)))
})

const confidenceLevelColor = computed(() => {
  const level = store.xaiExplanation?.confidence_level
  if (level === 'Very High' || level === 'High') return 'emerald-accent-4'
  if (level === 'Moderate') return 'amber-accent-3'
  return 'rose-400'
})

const statusChipColor = computed(() => {
  switch (store.latestIncident?.status) {
    case 'MANUAL_REVIEW': return 'amber-accent-3'
    case 'READY_FOR_ACTION': return 'cyan-accent-3'
    case 'HEALED': return 'emerald-accent-4'
    case 'ROLLBACK': return 'violet'
    default: return 'slate-400'
  }
})

const keyEvidence = computed(() => store.xaiExplanation?.key_evidence || [])
const contributingFactors = computed(() => store.xaiExplanation?.contributing_factors || [])

async function retryExplanation() {
  const incidentId = store.latestIncident?.id
  if (!incidentId || retrying.value) return
  retrying.value = true
  try {
    await store.fetchIncidentDetail(incidentId, true)
  } finally {
    retrying.value = false
  }
}

// Watcher updated to guard against infinite re-fetching loops
watch(
  () => store.latestIncident?.id,
  async (newId, oldId) => {
    if (!newId || newId === oldId || loadingIncidentId.value === newId) return
    
    loadingIncidentId.value = newId
    try {
      await store.fetchIncidentDetail(newId)
    } finally {
      loadingIncidentId.value = null
    }
  },
  { immediate: true }
)
</script>

<style scoped>
.xai-card {
  background: rgba(15, 23, 42, 0.65) !important;
  backdrop-filter: blur(16px);
  -webkit-backdrop-filter: blur(16px);
  border: 1px solid rgba(148, 163, 184, 0.12);
  min-height: 380px;
}

.card-body-wrapper {
  display: flex;
  flex-direction: column;
  position: relative;
  min-height: 0;
  overflow: hidden;
}

.scrollable-content {
  max-height: 340px;
  overflow-y: auto;
}

.scrollable-content::-webkit-scrollbar {
  width: 6px;
}

.scrollable-content::-webkit-scrollbar-track {
  background: rgba(15, 23, 42, 0.2);
  border-radius: 4px;
}

.scrollable-content::-webkit-scrollbar-thumb {
  background: rgba(148, 163, 184, 0.25);
  border-radius: 4px;
}

.incident-header-banner {
  background: rgba(30, 41, 59, 0.5);
  border: 1px solid rgba(148, 163, 184, 0.12);
}

.dark-subpanel {
  background: rgba(7, 16, 24, 0.6) !important;
  border: 1px solid rgba(148, 163, 184, 0.08);
}

.context-sheet {
  background: rgba(245, 158, 11, 0.08) !important;
  border: 1px solid rgba(245, 158, 11, 0.25);
}

.factor-sheet {
  background: rgba(244, 63, 94, 0.08) !important;
  border: 1px solid rgba(244, 63, 94, 0.2);
}

.state-panel {
  min-height: 220px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
}

.evidence-list {
  list-style-type: none;
  padding-left: 0;
}

.evidence-list li {
  padding: 4px 0;
  line-height: 1.4;
  font-size: 0.8rem;
}

.max-w-sm {
  max-width: 320px;
}

.leading-relaxed {
  line-height: 1.6;
}

.font-mono {
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace !important;
}
</style>