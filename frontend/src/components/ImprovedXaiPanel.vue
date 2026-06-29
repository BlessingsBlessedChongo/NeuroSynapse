<template>
  <v-card color="surface" elevation="2">
    <v-card-title>
      <v-icon icon="mdi-brain" class="mr-2 text-warning"></v-icon>
      Explainable AI Diagnosis
    </v-card-title>

    <v-card-subtitle class="text-secondary">
      AI-powered incident diagnosis with contributing factors
    </v-card-subtitle>

    <v-card-text>
      <!-- Stable system state -->
      <div v-if="isSystemStable">
        <v-alert type="info" variant="tonal" color="info" class="mb-4">
          <template v-slot:prepend>
            <v-icon icon="mdi-shield-check"></v-icon>
          </template>
          System Status: Stable. AI Models continuously monitoring telemetry...
        </v-alert>

        <v-row dense class="mt-4">
          <v-col cols="12">
            <div class="text-center">
              <v-icon icon="mdi-monitor-dashboard" size="56" color="success" class="opacity-60"></v-icon>
              <div class="text-body-2 text-secondary mt-3">
                No incidents detected. All systems operating normally.
              </div>
            </div>
          </v-col>
        </v-row>
      </div>

      <!-- Loading state -->
      <div v-else-if="store.xaiLoading">
        <v-progress-linear indeterminate color="primary" class="mb-4"></v-progress-linear>
        <div class="text-center py-8">
          <v-progress-circular indeterminate color="primary" size="48" class="mb-3"></v-progress-circular>
          <div class="text-body-2 text-secondary">Analyzing incident with AI models...</div>
        </div>
      </div>

      <!-- Error state -->
      <div v-else-if="store.xaiError">
        <v-alert type="error" variant="tonal" color="error" class="mb-4">
          <template v-slot:prepend>
            <v-icon icon="mdi-alert-circle"></v-icon>
          </template>
          {{ store.xaiError }}
        </v-alert>

        <div class="text-center py-4">
          <v-btn
            size="small"
            variant="outlined"
            color="primary"
            @click="retryExplanation"
            prepend-icon="mdi-refresh"
          >
            Retry
          </v-btn>
        </div>
      </div>

      <!-- XAI Explanation content -->
      <div v-else-if="latestIncident">
        <!-- Incident Header -->
        <v-row dense class="mb-4">
          <v-col cols="12" md="8">
            <div class="text-caption text-secondary mb-2">Latest Incident</div>
            <div class="text-h6 font-weight-bold">{{ incidentTypeLabel }} on {{ latestIncident.device }}</div>
            <div class="text-caption text-secondary mt-1">
              Detected: {{ formattedDetectionTime }}
            </div>
          </v-col>

          <v-col cols="12" md="4" class="d-flex align-center justify-end gap-2">
            <v-chip
              size="small"
              color="secondary"
              variant="tonal"
              :prepend-icon="confidenceIcon"
            >
              {{ confidencePercentage }}% Confidence
            </v-chip>

            <v-chip
              size="small"
              :color="statusChipColor"
              variant="tonal"
            >
              {{ latestIncident.status || 'UNKNOWN' }}
            </v-chip>
          </v-col>
        </v-row>

        <v-divider class="my-4"></v-divider>

        <!-- AI Summary Section -->
        <div class="mb-6">
          <div class="text-caption text-secondary text-uppercase font-weight-bold mb-2">
            <v-icon icon="mdi-text-box" size="16" class="mr-1"></v-icon>
            Diagnosis Summary
          </div>
          <v-card color="background" variant="outlined" class="pa-3">
            <div class="text-body-2">
              {{ explanationSummary }}
            </div>
          </v-card>
        </div>

        <!-- Contributing Factors Section -->
        <div class="mb-6">
          <div class="text-caption text-secondary text-uppercase font-weight-bold mb-3">
            <v-icon icon="mdi-chart-pie" size="16" class="mr-1"></v-icon>
            Key Contributing Factors
          </div>

          <div v-if="contributingFactors.length > 0" class="space-y-2">
            <div v-for="(factor, idx) in contributingFactors" :key="idx" class="mb-3">
              <div class="d-flex align-center justify-between mb-1">
                <div class="text-body-2 font-weight-medium">{{ factor.label }}</div>
                <div class="text-caption" :class="factor.isNegative ? 'text-error' : 'text-success'">
                  {{ factor.weightPercentage }}%
                </div>
              </div>

              <v-progress-linear
                :model-value="factor.weightPercentage"
                :color="factor.isNegative ? 'error' : 'success'"
                height="6"
                class="mb-1"
              ></v-progress-linear>

              <div class="text-caption text-secondary">{{ factor.detail }}</div>
            </div>
          </div>

          <div v-else class="text-center py-4">
            <div class="text-body-2 text-secondary">No factor details available</div>
          </div>
        </div>

        <!-- Recommended Action Section -->
        <div>
          <div class="text-caption text-secondary text-uppercase font-weight-bold mb-2">
            <v-icon icon="mdi-lightbulb" size="16" class="mr-1"></v-icon>
            Recommended Action
          </div>
          <v-chip
            color="primary"
            variant="tonal"
            size="medium"
            class="font-weight-medium"
          >
            {{ recommendedActionText }}
          </v-chip>
        </div>
      </div>

      <!-- No incident state (should not render due to isSystemStable check, but kept for safety) -->
      <div v-else>
        <v-alert type="info" variant="tonal" color="info" class="mb-4">
          <template v-slot:prepend>
            <v-icon icon="mdi-information"></v-icon>
          </template>
          Awaiting incident data. The AI diagnosis will appear when an incident is detected.
        </v-alert>
      </div>
    </v-card-text>
  </v-card>
</template>

<script setup>
import { computed, watch } from 'vue'
import { useNetworkStore } from '@/stores/network'

const store = useNetworkStore()

const latestIncident = computed(() => store.latestIncident)

const isSystemStable = computed(() => {
  return !latestIncident.value || !latestIncident.value.id
})

const incidentTypeLabel = computed(() => {
  if (!latestIncident.value) return 'Unknown'

  const type = latestIncident.value.type
  if (type === 'SERVICE_CRASH') return 'Service Crash'
  if (type === 'LINK_FAILURE') return 'Link Failure'
  if (type === 'DDOS_ATTACK') return 'DDoS Attack'
  return type || 'Unknown Incident'
})

const formattedDetectionTime = computed(() => {
  if (!latestIncident.value?.detected_at) return 'Unknown'

  try {
    const date = new Date(latestIncident.value.detected_at)
    return date.toLocaleString([], {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
    })
  } catch (e) {
    return 'Unknown'
  }
})

const confidencePercentage = computed(() => {
  if (!latestIncident.value?.confidence) return '0'

  const confidence = latestIncident.value.confidence
  const percentage = Math.round(confidence * 100)
  return Math.min(100, Math.max(0, percentage))
})

const confidenceIcon = computed(() => {
  const confidence = confidencePercentage.value
  if (confidence >= 80) return 'mdi-check-circle'
  if (confidence >= 60) return 'mdi-information'
  return 'mdi-alert'
})

const statusChipColor = computed(() => {
  const status = latestIncident.value?.status?.toLowerCase() || ''

  if (status.includes('manual')) return 'warning'
  if (status.includes('executing') || status.includes('healing')) return 'info'
  if (status.includes('detected') || status.includes('analyzing')) return 'secondary'
  if (status.includes('resolved')) return 'success'

  return 'secondary'
})

const explanationSummary = computed(() => {
  const explanation = store.xaiExplanation || {}

  return (
    explanation.summary ||
    explanation.diagnosis ||
    explanation.message ||
    'The AI models have analyzed the incident based on telemetry data, network topology, and historical patterns. Review the contributing factors below.'
  )
})

const contributingFactors = computed(() => {
  const explanation = store.xaiExplanation || {}

  let factors = []

  if (Array.isArray(explanation.factors) && explanation.factors.length > 0) {
    factors = explanation.factors
  } else if (Array.isArray(explanation.key_factors) && explanation.key_factors.length > 0) {
    factors = explanation.key_factors
  }

  return factors
    .slice(0, 5)
    .map(factor => {
      const weight = parseFloat(factor.weight) || parseFloat(factor.contribution) || 0
      const isNegative =
        factor.type === 'negative' || factor.impact === 'negative' || weight < 0

      return {
        label: factor.label || factor.name || 'Unknown Factor',
        detail: factor.detail || factor.description || factor.explanation || 'No additional details',
        weightPercentage: Math.round(Math.abs(weight) * 100),
        isNegative,
      }
    })
})

const recommendedActionText = computed(() => {
  const explanation = store.xaiExplanation || {}

  return (
    explanation.recommended_action ||
    explanation.recommendedAction ||
    explanation.action ||
    explanation.recommendation ||
    'Review and approve the healing plan'
  )
})

async function retryExplanation() {
  if (latestIncident.value?.id) {
    await store.fetchXaiExplanation(latestIncident.value.id)
  }
}

watch(
  () => latestIncident.value?.id,
  async incidentId => {
    if (incidentId) {
      await store.fetchXaiExplanation(incidentId)
    }
  },
  { immediate: true }
)
</script>

<style scoped>
.space-y-2 > * + * {
  margin-top: 0.5rem;
}

.opacity-60 {
  opacity: 0.6;
}

.gap-2 {
  gap: 0.5rem;
}
</style>
