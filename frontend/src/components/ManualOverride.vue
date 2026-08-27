<template>
  <v-card class="override-card rounded-xl pa-2" elevation="0">
    <v-card-title class="d-flex align-center py-3 px-4">
      <div class="d-flex align-center ga-2">
        <v-avatar
          :color="hasManualReview ? 'amber-accent-4' : 'emerald-accent-4'"
          variant="tonal"
          size="36"
          class="mr-1"
        >
          <v-icon :icon="hasManualReview ? 'mdi-account-alert' : 'mdi-shield-check'" size="20" />
        </v-avatar>
        <span class="text-h6 font-weight-bold text-slate-100">Human-in-the-Loop Control</span>
      </div>
      <v-spacer />
      <v-chip
        v-if="!store.canApprove"
        size="small"
        variant="outlined"
        color="slate-400"
        prepend-icon="mdi-eye-outline"
        class="font-weight-medium"
      >
        Read-Only ({{ store.role }})
      </v-chip>
    </v-card-title>

    <v-card-text class="pa-3">
      <v-alert
        v-if="hasManualReview"
        type="warning"
        variant="tonal"
        prominent
        border="start"
        icon="mdi-hand-back-right"
        class="mb-4 rounded-lg border-amber-accent-4"
      >
        <v-alert-title class="font-weight-bold text-subtitle-1">Manual Review Required</v-alert-title>
        <p class="text-body-2 mb-0 mt-1 text-slate-300">
          <strong>{{ store.pendingManualReview.length }}</strong> incident(s) require manual authorization before execution. AI diagnostic confidence scores fell below the auto-heal threshold.
        </p>
      </v-alert>

      <v-alert
        v-else
        type="success"
        variant="tonal"
        prominent
        border="start"
        icon="mdi-robot-happy-outline"
        class="mb-4 rounded-lg"
      >
        <v-alert-title class="font-weight-bold text-subtitle-1">Autonomic Engine Active</v-alert-title>
        <p class="text-body-2 mb-0 mt-1 text-slate-300">
          All network telemetry anomalies are being mitigated autonomously by MAPE-K loop agents.
        </p>
      </v-alert>

      <div v-if="hasManualReview" class="d-flex flex-column ga-3">
        <v-sheet
          v-for="incident in store.pendingManualReview"
          :key="incident.id"
          rounded="lg"
          class="review-item-card pa-3 d-flex align-center justify-space-between flex-wrap ga-3"
        >
          <div>
            <div class="d-flex align-center ga-2 mb-1">
              <v-chip size="x-small" color="amber-accent-4" variant="flat" class="font-weight-bold">
                {{ incident.failure_type_display || incident.failure_type }}
              </v-chip>
              <span class="text-body-2 font-weight-bold text-slate-100">{{ incident.device_name }}</span>
            </div>
            <p class="text-caption text-slate-400 mb-0 font-mono">
              Confidence: {{ Math.round((incident.confidence_score || 0) * 100) }}% · ID #{{ incident.id }}
            </p>
          </div>

          <div class="d-flex ga-2">
            <v-btn
              size="small"
              color="emerald-accent-4"
              variant="flat"
              prepend-icon="mdi-check-circle"
              class="font-weight-bold"
              :disabled="!store.canApprove"
              :loading="approvingId === incident.id"
              @click="handleApprove(incident.id)"
            >
              Approve
            </v-btn>
            <v-btn
              size="small"
              color="rose-accent-3"
              variant="flat"
              prepend-icon="mdi-close-circle"
              class="font-weight-bold"
              :disabled="!store.canApprove"
              :loading="rejectingId === incident.id"
              @click="handleReject(incident.id)"
            >
              Reject
            </v-btn>
          </div>
        </v-sheet>
      </div>
    </v-card-text>
  </v-card>
</template>

<script setup>
import { computed, ref } from 'vue'
import { useNetworkStore } from '@/stores/network'

const store = useNetworkStore()
const approvingId = ref(null)
const rejectingId = ref(null)

const hasManualReview = computed(() => store.pendingManualReview.length > 0)

async function handleApprove(id) {
  approvingId.value = id
  try {
    await store.approveIncident(id)
  } finally {
    approvingId.value = null
  }
}

async function handleReject(id) {
  rejectingId.value = id
  try {
    await store.rejectIncident(id)
  } finally {
    rejectingId.value = null
  }
}
</script>

<style scoped>
.override-card {
  background: rgba(15, 23, 42, 0.65) !important;
  backdrop-filter: blur(16px);
  -webkit-backdrop-filter: blur(16px);
  border: 1px solid rgba(148, 163, 184, 0.12);
}

.review-item-card {
  background: rgba(30, 41, 59, 0.5) !important;
  border: 1px solid rgba(148, 163, 184, 0.1);
}

.font-mono {
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace !important;
}
</style>