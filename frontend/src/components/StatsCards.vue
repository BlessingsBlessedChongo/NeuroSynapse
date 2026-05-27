<template>
  <v-row>
    <v-col cols="12" sm="6" lg="3">
      <v-card color="surface" class="pa-4" elevation="2">
        <v-card-subtitle class="text-secondary text-uppercase text-caption">
          <v-icon icon="mdi-monitor-dashboard" size="16" class="mr-1"></v-icon>
          Monitored Devices
        </v-card-subtitle>
        <v-card-text>
          <span class="text-h3 font-weight-bold">{{ store.deviceCount }}</span>
        </v-card-text>
      </v-card>
    </v-col>

    <v-col cols="12" sm="6" lg="3">
      <v-card color="surface" class="pa-4" elevation="2">
        <v-card-subtitle class="text-secondary text-uppercase text-caption">
          <v-icon icon="mdi-alert-circle" size="16" class="mr-1"></v-icon>
          Open Incidents
        </v-card-subtitle>
        <v-card-text>
          <span
            class="text-h3 font-weight-bold"
            :class="store.openIncidents > 0 ? 'text-error' : 'text-success'"
          >
            {{ store.openIncidents }}
          </span>
        </v-card-text>
      </v-card>
    </v-col>

    <v-col cols="12" sm="6" lg="3">
      <v-card color="surface" class="pa-4" elevation="2">
        <v-card-subtitle class="text-secondary text-uppercase text-caption">
          <v-icon icon="mdi-heart-pulse" size="16" class="mr-1"></v-icon>
          Healed Today
        </v-card-subtitle>
        <v-card-text>
          <span class="text-h3 font-weight-bold text-success">{{ store.healedToday }}</span>
        </v-card-text>
      </v-card>
    </v-col>

    <v-col cols="12" sm="6" lg="3">
      <v-card color="surface" class="pa-4" elevation="2">
        <v-card-subtitle class="text-secondary text-uppercase text-caption">
          <v-icon icon="mdi-chart-bar" size="16" class="mr-1"></v-icon>
          Total Incidents
        </v-card-subtitle>
        <v-card-text>
          <span class="text-h3 font-weight-bold">{{ store.totalIncidents }}</span>
        </v-card-text>
      </v-card>
    </v-col>
  </v-row>
</template>

<script setup>
import { useNetworkStore } from '@/stores/network'

const store = useNetworkStore()
</script>