<template>
  <v-card color="surface" elevation="2" class="h-100">
    <v-card-title>
      <v-icon icon="mdi-alert-octagon" class="mr-2 text-error"></v-icon>
      Latest Incidents
    </v-card-title>

    <v-list bg-color="transparent" max-height="400" class="overflow-y-auto">
      <v-list-item
        v-for="incident in store.latestIncidents"
        :key="incident.id"
        :value="incident.id"
      >
        <template v-slot:prepend>
          <v-chip
            :color="incidentTypeColor(incident.type)"
            size="x-small"
            variant="flat"
          >
            {{ incident.type }}
          </v-chip>
        </template>

        <v-list-item-title class="text-body-2">
          {{ incident.device }}
        </v-list-item-title>

        <v-list-item-subtitle class="text-caption">
          <span v-if="incident.confidence">
            {{ (incident.confidence * 100).toFixed(0) }}% confidence
          </span>
          <span class="mx-1">|</span>
          <span>{{ incident.status }}</span>
          <span class="mx-1">|</span>
          <span>{{ formatTime(incident.detected_at) }}</span>
        </v-list-item-subtitle>
      </v-list-item>

      <v-list-item v-if="store.latestIncidents.length === 0">
        <v-list-item-title class="text-secondary text-center py-4">
          <v-icon icon="mdi-shield-check" size="40" color="success"></v-icon>
          <div class="mt-2">No incidents detected</div>
        </v-list-item-title>
      </v-list-item>
    </v-list>
  </v-card>
</template>

<script setup>
import { useNetworkStore } from '@/stores/network'

const store = useNetworkStore()

function incidentTypeColor(type) {
  switch (type) {
    case 'Service Crash': return 'error'
    case 'Link Failure': return 'warning'
    case 'DDoS Attack': return 'purple'
    default: return 'secondary'
  }
}

function formatTime(isoString) {
  if (!isoString) return '--'
  return new Date(isoString).toLocaleTimeString()
}
</script>