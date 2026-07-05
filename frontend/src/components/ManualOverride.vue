<template>
  <v-card color="surface" elevation="2" class="override-card">
    <v-card-title class="d-flex align-center">
      <v-icon
        :icon="hasManualReview ? 'mdi-account-alert' : 'mdi-shield-lock-outline'"
        class="mr-2"
        :color="hasManualReview ? 'warning' : 'success'"
      />
      Human-in-the-Loop Control
    </v-card-title>

    <v-card-text>
      <v-alert
        v-if="hasManualReview"
        type="warning"
        variant="tonal"
        prominent
        border="start"
        icon="mdi-hand-back-right"
      >
        <v-alert-title class="font-weight-bold">Manual Review Required</v-alert-title>
        <p class="text-body-2 mb-0 mt-2">
          One or more incidents require operator approval before the AI engine can execute
          remediation. Review the pending actions in the incident control panel and use the
          <strong>Approve Healing</strong> or <strong>Reject/Isolate</strong> buttons to proceed.
        </p>
      </v-alert>

      <v-alert
        v-else
        type="success"
        variant="tonal"
        prominent
        border="start"
        icon="mdi-robot-happy-outline"
      >
        <v-alert-title class="font-weight-bold">Autonomic Status: Guarded</v-alert-title>
        <p class="text-body-2 mb-0 mt-2">
          All anomalies are being handled automatically by the AI engine.
        </p>
      </v-alert>
    </v-card-text>
  </v-card>
</template>

<script setup>
import { computed } from 'vue'
import { useNetworkStore } from '@/stores/network'

const store = useNetworkStore()

const hasManualReview = computed(() =>
  store.latestIncidents.some(incident => incident.status === 'Manual Review'),
)
</script>

<style scoped>
.override-card {
  border: 1px solid rgba(148, 163, 184, 0.08);
}
</style>
