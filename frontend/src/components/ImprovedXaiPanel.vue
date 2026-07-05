<template>
  <v-card color="surface" elevation="2" class="xai-card">
    <v-card-title class="d-flex align-center">
      <v-icon icon="mdi-brain" class="mr-2 text-purple-lighten-1" />
      Explainable AI Diagnosis
    </v-card-title>

    <v-card-subtitle class="text-medium-emphasis pb-2">
      Natural-language diagnosis with telemetry feature attribution
    </v-card-subtitle>

    <v-card-text class="position-relative">
      <v-overlay
        :model-value="store.xaiLoading"
        contained
        persistent
        class="align-center justify-center"
        scrim="rgba(15, 23, 42, 0.85)"
      >
        <v-progress-circular indeterminate color="primary" size="52" width="4" />
        <p class="text-body-2 text-medium-emphasis mt-4 text-center">
          Analyzing incident with AI models…
        </p>
      </v-overlay>

      <div v-if="!store.latestIncident" class="state-panel text-center py-10">
        <v-icon icon="mdi-radar" size="56" color="success" class="mb-4 opacity-70" />
        <p class="text-body-1 font-weight-medium mb-1">System Status: Stable</p>
        <p class="text-body-2 text-medium-emphasis mb-0">
          AI models are continuously monitoring telemetry. Diagnosis explanations will appear
          when an incident is detected.
        </p>
      </div>

      <div v-else-if="store.xaiError" class="state-panel text-center py-8">
        <v-icon icon="mdi-alert-circle-outline" size="48" color="error" class="mb-3" />
        <p class="text-body-1 text-error mb-4">{{ store.xaiError }}</p>
        <v-btn
          variant="outlined"
          color="primary"
          prepend-icon="mdi-refresh"
          :loading="retrying"
          @click="retryExplanation"
        >
          Retry
        </v-btn>
      </div>

      <div v-else>
        <v-row dense class="mb-4">
          <v-col cols="12" md="8">
            <p class="text-caption text-medium-emphasis text-uppercase mb-1">Active Incident</p>
            <h3 class="text-h6 font-weight-bold">
              {{ incidentTypeLabel }} on {{ store.latestIncident.device }}
            </h3>
            <p class="text-caption text-medium-emphasis mt-1">
              Detected {{ formattedDetectionTime }}
            </p>
          </v-col>
          <v-col cols="12" md="4" class="d-flex align-center justify-md-end ga-2 flex-wrap">
            <v-chip size="small" variant="tonal" color="secondary" prepend-icon="mdi-percent">
              {{ confidencePercentage }}% Confidence
            </v-chip>
            <v-chip size="small" variant="tonal" :color="statusChipColor">
              {{ store.latestIncident.status || 'Unknown' }}
            </v-chip>
          </v-col>
        </v-row>

        <v-divider class="mb-5" />

        <section class="mb-6">
          <p class="text-caption text-uppercase text-medium-emphasis font-weight-bold mb-2">
            <v-icon icon="mdi-text-box-outline" size="16" class="mr-1" />
            Diagnosis Summary
          </p>
          <v-sheet color="background" variant="outlined" rounded="lg" class="pa-4">
            <p class="text-body-2 mb-0">{{ explanationSummary }}</p>
          </v-sheet>
        </section>

        <section>
          <p class="text-caption text-uppercase text-medium-emphasis font-weight-bold mb-3">
            <v-icon icon="mdi-chart-bell-curve" size="16" class="mr-1" />
            Telemetry Feature Weights
          </p>

          <div v-if="featureWeights.length > 0">
            <div
              v-for="(factor, index) in featureWeights"
              :key="index"
              class="factor-row mb-4"
            >
              <div class="d-flex align-center justify-space-between mb-1">
                <span class="text-body-2 font-weight-medium">{{ factor.label }}</span>
                <span
                  class="text-caption font-weight-bold"
                  :class="factor.isNegative ? 'text-error' : 'text-success'"
                >
                  {{ factor.weightPercentage }}%
                </span>
              </div>
              <v-progress-linear
                :model-value="factor.weightPercentage"
                :color="factor.isNegative ? 'error' : 'success'"
                height="8"
                rounded
              />
              <p v-if="factor.detail" class="text-caption text-medium-emphasis mt-1 mb-0">
                {{ factor.detail }}
              </p>
            </div>
          </div>

          <div v-else class="text-center py-4">
            <p class="text-body-2 text-medium-emphasis mb-0">
              No feature weight data available for this incident.
            </p>
          </div>
        </section>
      </div>
    </v-card-text>
  </v-card>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import { useNetworkStore } from '@/stores/network'

const store = useNetworkStore()
const retrying = ref(false)

const incidentTypeLabel = computed(() => {
  const type = store.latestIncident?.type
  if (!type) return 'Unknown Incident'
  const normalized = type.toUpperCase().replace(/\s+/g, '_')
  if (normalized === 'SERVICE_CRASH' || type === 'Service Crash') return 'Service Crash'
  if (normalized === 'LINK_FAILURE' || type === 'Link Failure') return 'Link Failure'
  if (normalized === 'DDOS_ATTACK' || type === 'DDoS Attack') return 'DDoS Attack'
  return type
})

const formattedDetectionTime = computed(() => {
  const detectedAt = store.latestIncident?.detected_at
  if (!detectedAt) return 'Unknown'
  try {
    return new Date(detectedAt).toLocaleString([], {
      year: 'numeric',
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
  const confidence = store.latestIncident?.confidence
  if (confidence == null) return 0
  return Math.min(100, Math.max(0, Math.round(confidence * 100)))
})

const statusChipColor = computed(() => {
  const status = store.latestIncident?.status?.toLowerCase() || ''
  if (status.includes('manual')) return 'warning'
  if (status.includes('executing') || status.includes('healing')) return 'info'
  if (status.includes('healed')) return 'success'
  return 'secondary'
})

const explanationSummary = computed(() => {
  const explanation = store.xaiExplanation || {}
  return (
    explanation.summary ||
    explanation.diagnosis ||
    explanation.message ||
    explanation.what_this_means ||
    'The AI engine has analyzed telemetry patterns for this incident. Review the feature weights below for contributing factors.'
  )
})

const featureWeights = computed(() => {
  const explanation = store.xaiExplanation || {}
  let rawFactors = []

  if (Array.isArray(explanation.contributing_factors) && explanation.contributing_factors.length) {
    rawFactors = explanation.contributing_factors.map((text, index) => ({
      label: `Factor ${index + 1}`,
      detail: typeof text === 'string' ? text : text?.description || '',
      weight: 0.15 + (index * 0.05),
      isNegative: true,
    }))
  }

  if (Array.isArray(explanation.factors) && explanation.factors.length) {
    rawFactors = explanation.factors
  } else if (Array.isArray(explanation.key_factors) && explanation.key_factors.length) {
    rawFactors = explanation.key_factors
  }

  if (rawFactors.length === 0 && Array.isArray(explanation.key_evidence)) {
    rawFactors = explanation.key_evidence.map((evidence, index) => ({
      label: `Evidence ${index + 1}`,
      detail: evidence,
      weight: Math.max(0.1, 0.35 - index * 0.05),
      isNegative: evidence.toLowerCase().includes('high') ||
        evidence.toLowerCase().includes('critical') ||
        evidence.toLowerCase().includes('elevated'),
    }))
  }

  return rawFactors.slice(0, 6).map((factor, index) => {
    if (typeof factor === 'string') {
      return {
        label: `Feature ${index + 1}`,
        detail: factor,
        weightPercentage: Math.round(100 / Math.min(rawFactors.length, 6)),
        isNegative: true,
      }
    }

    const weight = parseFloat(factor.weight ?? factor.contribution ?? factor.score ?? 0.2)
    const isNegative =
      factor.type === 'negative' ||
      factor.impact === 'negative' ||
      factor.is_negative === true ||
      weight < 0 ||
      (typeof factor.detail === 'string' &&
        (factor.detail.toLowerCase().includes('high') ||
          factor.detail.toLowerCase().includes('elevated')))

    return {
      label: factor.label || factor.name || factor.feature || `Feature ${index + 1}`,
      detail: factor.detail || factor.description || factor.explanation || '',
      weightPercentage: Math.min(100, Math.round(Math.abs(weight <= 1 ? weight * 100 : weight))),
      isNegative,
    }
  })
})

async function retryExplanation() {
  const incidentId = store.latestIncident?.id
  if (!incidentId) return
  retrying.value = true
  try {
    await store.fetchXaiExplanation(incidentId, true)
  } finally {
    retrying.value = false
  }
}

watch(
  () => store.latestIncident?.id,
  async incidentId => {
    if (incidentId) {
      await store.fetchXaiExplanation(incidentId)
    }
  },
  { immediate: true },
)
</script>

<style scoped>
.xai-card {
  border: 1px solid rgba(148, 163, 184, 0.08);
}

.state-panel {
  min-height: 220px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
}

.factor-row:last-child {
  margin-bottom: 0 !important;
}

.opacity-70 {
  opacity: 0.7;
}
</style>
