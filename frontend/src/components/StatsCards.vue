<template>
  <v-row dense>
    <v-col
      v-for="card in metricCards"
      :key="card.key"
      cols="12"
      sm="6"
      lg="3"
    >
      <v-card
        color="surface"
        elevation="2"
        class="metric-card pa-4 h-100"
        :class="card.accentClass"
      >
        <div class="d-flex align-start justify-space-between mb-3">
          <div>
            <p class="text-caption text-uppercase text-medium-emphasis font-weight-bold mb-1">
              {{ card.label }}
            </p>
            <p
              class="text-h3 font-weight-bold"
              :class="card.valueClass"
            >
              {{ card.value }}
            </p>
          </div>
          <v-avatar
            :color="card.iconColor"
            variant="tonal"
            size="44"
            rounded="lg"
          >
            <v-icon :icon="card.icon" size="24" />
          </v-avatar>
        </div>
        <p class="text-caption text-medium-emphasis mb-0">{{ card.caption }}</p>
      </v-card>
    </v-col>
  </v-row>
</template>

<script setup>
import { computed } from 'vue'
import { useNetworkStore } from '@/stores/network'

const store = useNetworkStore()

const metricCards = computed(() => [
  {
    key: 'devices',
    label: 'Total Monitored Devices',
    value: store.deviceCount,
    icon: 'mdi-lan',
    iconColor: 'info',
    valueClass: 'text-info',
    accentClass: 'accent-info',
    caption: 'Active nodes under continuous telemetry watch',
  },
  {
    key: 'open',
    label: 'Open Incidents',
    value: store.openIncidents,
    icon: 'mdi-alert-rhombus-outline',
    iconColor: store.openIncidents > 0 ? 'warning' : 'success',
    valueClass: store.openIncidents > 0 ? 'text-warning' : 'text-success',
    accentClass: store.openIncidents > 0 ? 'accent-warning' : 'accent-success',
    caption: store.openIncidents > 0 ? 'Anomalies requiring attention' : 'No active failures detected',
  },
  {
    key: 'healed',
    label: 'Total Healed Today',
    value: store.healedToday,
    icon: 'mdi-shield-check-outline',
    iconColor: 'success',
    valueClass: 'text-success',
    accentClass: 'accent-success',
    caption: 'Autonomic remediations completed this epoch',
  },
  {
    key: 'lifetime',
    label: 'Lifetime Incidents Processed',
    value: store.totalIncidents,
    icon: 'mdi-database-clock-outline',
    iconColor: 'purple',
    valueClass: 'text-purple-lighten-1',
    accentClass: 'accent-purple',
    caption: 'Cumulative failures analyzed by the AI engine',
  },
])
</script>

<style scoped>
.metric-card {
  border: 1px solid rgba(148, 163, 184, 0.08);
  transition: border-color 0.2s ease, box-shadow 0.2s ease;
}

.metric-card:hover {
  box-shadow: 0 4px 24px rgba(0, 0, 0, 0.25);
}

.accent-info {
  border-left: 3px solid rgba(56, 189, 248, 0.7);
}

.accent-warning {
  border-left: 3px solid rgba(252, 211, 77, 0.7);
}

.accent-success {
  border-left: 3px solid rgba(110, 231, 183, 0.7);
}

.accent-purple {
  border-left: 3px solid rgba(224, 64, 251, 0.6);
}
</style>
