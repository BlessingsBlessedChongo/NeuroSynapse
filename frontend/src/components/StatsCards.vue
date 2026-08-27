<template>
  <v-row dense class="mb-2">
    <v-col
      v-for="card in metricCards"
      :key="card.key"
      cols="12"
      sm="6"
      lg="3"
    >
      <v-card
        elevation="0"
        class="metric-card pa-4 h-100 rounded-xl d-flex flex-column justify-space-between"
        :class="card.accentClass"
      >
        <div class="d-flex align-start justify-space-between mb-3">
          <div>
            <p class="metric-label text-caption text-uppercase font-weight-bold mb-1">
              {{ card.label }}
            </p>
            <p class="metric-value text-h3 font-weight-extrabold" :class="card.valueClass">
              {{ card.value }}
            </p>
          </div>

          <v-avatar
            :color="card.iconColor"
            variant="tonal"
            size="46"
            rounded="lg"
            class="metric-avatar"
          >
            <v-icon :icon="card.icon" size="24" />
          </v-avatar>
        </div>

        <p class="metric-caption text-caption text-slate-400 mb-0">
          {{ card.caption }}
        </p>
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
    valueClass: 'text-cyan-accent-2',
    accentClass: 'accent-cyan',
    caption: 'Active nodes under continuous telemetry watch',
  },
  {
    key: 'open',
    label: 'Open Incidents',
    value: store.openIncidents,
    icon: 'mdi-alert-rhombus-outline',
    iconColor: store.openIncidents > 0 ? 'warning' : 'success',
    valueClass: store.openIncidents > 0 ? 'text-amber-accent-2' : 'text-emerald-accent-3',
    accentClass: store.openIncidents > 0 ? 'accent-amber' : 'accent-emerald',
    caption: store.openIncidents > 0 ? 'Anomalies requiring attention' : 'No active failures detected',
  },
  {
    key: 'healed',
    label: 'Resolved Incidents',
    value: store.resolvedIncidents,
    icon: 'mdi-shield-check-outline',
    iconColor: 'success',
    valueClass: 'text-emerald-accent-3',
    accentClass: 'accent-emerald',
    caption: 'Incidents successfully healed by autonomic loop',
  },
  {
    key: 'lifetime',
    label: 'Lifetime Incidents Processed',
    value: store.totalIncidents,
    icon: 'mdi-database-clock-outline',
    iconColor: 'violet-accent',
    valueClass: 'text-violet-accent',
    accentClass: 'accent-purple',
    caption: 'Cumulative failures analyzed by AI engine',
  },
])
</script>

<style scoped>
.metric-card {
  background: rgba(15, 23, 42, 0.65) !important;
  backdrop-filter: blur(16px);
  -webkit-backdrop-filter: blur(16px);
  border: 1px solid rgba(148, 163, 184, 0.12);
  transition: all 0.25s cubic-bezier(0.16, 1, 0.3, 1);
  position: relative;
  overflow: hidden;
}

.metric-card:hover {
  transform: translateY(-3px);
  border-color: rgba(0, 229, 255, 0.25);
  box-shadow: 0 12px 30px rgba(0, 0, 0, 0.4);
}

.metric-label {
  color: #94a3b8;
  letter-spacing: 0.8px;
  font-size: 0.68rem !important;
}

.metric-value {
  letter-spacing: -1px;
}

.metric-caption {
  font-size: 0.75rem !important;
  line-height: 1.4;
}

/* Glassmorphism Icon Box */
.metric-avatar {
  border: 1px solid rgba(255, 255, 255, 0.08);
}

/* Glowing Top Accent Borders */
.accent-cyan {
  border-top: 2px solid #00e5ff;
}

.accent-amber {
  border-top: 2px solid #ffd600;
}

.accent-emerald {
  border-top: 2px solid #00e676;
}

.accent-purple {
  border-top: 2px solid #A855F7;
}
</style>