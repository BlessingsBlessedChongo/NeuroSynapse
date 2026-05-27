<template>
  <v-app-bar color="surface" elevation="2">
    <v-app-bar-title>
      <v-icon icon="mdi-brain" color="primary" size="28" class="mr-2"></v-icon>
      <span class="text-primary font-weight-bold">NeuroSynapse</span>
      <span class="text-secondary text-caption ml-3">AI-Powered Self-Healing Network Intelligence</span>
    </v-app-bar-title>

    <template v-slot:append>
      <v-chip
        :color="statusColor"
        size="large"
        variant="flat"
        class="px-4"
      >
        <v-icon start :icon="statusIcon" size="16"></v-icon>
        {{ statusText }}
      </v-chip>
    </template>
  </v-app-bar>
</template>

<script setup>
import { computed } from 'vue'
import { useNetworkStore } from '@/stores/network'

const store = useNetworkStore()

const statusColor = computed(() => {
  switch (store.overallHealth) {
    case 'HEALTHY': return 'success'
    case 'WARNING': return 'warning'
    case 'CRITICAL': return 'error'
    default: return 'secondary'
  }
})

const statusIcon = computed(() => {
  switch (store.overallHealth) {
    case 'HEALTHY': return 'mdi-check-circle'
    case 'WARNING': return 'mdi-alert'
    case 'CRITICAL': return 'mdi-alert-circle'
    default: return 'mdi-help-circle'
  }
})

const statusText = computed(() => {
  switch (store.overallHealth) {
    case 'HEALTHY': return 'SYSTEM HEALTHY'
    case 'WARNING': return 'WARNING'
    case 'CRITICAL': return 'INCIDENT ACTIVE'
    default: return 'UNKNOWN'
  }
})
</script>