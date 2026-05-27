<template>
  <v-card color="surface" elevation="2">
    <v-card-title>
      <v-icon icon="mdi-lightbulb" class="mr-2 text-warning"></v-icon>
      Explainable AI (XAI)
    </v-card-title>

    <v-card-text>
      <div v-if="store.latestIncidents.length > 0" class="xai-content">
        <div class="text-subtitle-1 font-weight-bold mb-2">
          Latest Detection
        </div>
        <p class="text-body-2">
          The AI detected a
          <strong>{{ store.latestIncidents[0].type }}</strong>
          on <strong>{{ store.latestIncidents[0].device }}</strong>
          with {{ (store.latestIncidents[0].confidence * 100).toFixed(0) }}% confidence.
        </p>

        <div class="text-caption text-secondary mt-2">
          The ML model analyzed telemetry patterns including CPU usage,
          memory consumption, packet loss, and interface status to make
          this diagnosis. Healing actions are selected based on learned
          experience from previous incidents.
        </div>
      </div>

      <div v-else class="text-center py-4">
        <v-icon icon="mdi-shield-check" size="48" color="success" class="mb-2"></v-icon>
        <p class="text-secondary">
          NeuroSynapse is monitoring your network. When anomalies are detected,
          explanations for diagnosis and healing decisions will appear here.
        </p>
      </div>
    </v-card-text>
  </v-card>
</template>

<script setup>
import { useNetworkStore } from '@/stores/network'

const store = useNetworkStore()
</script>

<style scoped>
.xai-content {
  line-height: 1.6;
}
</style>