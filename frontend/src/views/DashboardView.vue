<template>
  <v-container fluid class="pa-6">
    <!-- Stats Cards -->
    <StatsCards />

    <!-- Device Status -->
    <v-row class="mt-4">
      <v-col cols="12">
        <DeviceList />
      </v-col>
    </v-row>

    <!-- Telemetry Chart -->
    <v-row class="mt-4">
      <v-col cols="12">
        <TelemetryChart />
      </v-col>
    </v-row>

    <!-- Incidents and Healings -->
    <v-row class="mt-4">
      <v-col cols="12" md="6">
        <IncidentList />
      </v-col>
      <v-col cols="12" md="6">
        <HealingHistory />
      </v-col>
    </v-row>

    <!-- XAI and RL Stats -->
    <v-row class="mt-4">
      <v-col cols="12" lg="7">
        <ImprovedXaiPanel />
      </v-col>
      <v-col cols="12" lg="5">
        <RLStats />
      </v-col>
    </v-row>

    <!-- Manual Override -->
    <v-row class="mt-4">
      <v-col cols="12">
        <ManualOverride />
      </v-col>
    </v-row>

    <v-row class="mt-4">
    <v-col cols="12" lg="6">
        <MapekIndicator />
      </v-col>
    </v-row>

    <!-- Refresh indicator -->
    <v-row class="mt-4">
      <v-col cols="12" class="text-center">
        <span class="text-caption text-secondary">
          Auto-refreshing every 2 seconds | Last updated: {{ lastUpdated }}
        </span>
      </v-col>
    </v-row>
  </v-container>
</template>

<script setup>
import { computed, onMounted, onUnmounted } from 'vue'
import { useNetworkStore } from '@/stores/network'
import StatsCards from '@/components/StatsCards.vue'
import DeviceList from '@/components/DeviceList.vue'
import IncidentList from '@/components/IncidentList.vue'
import HealingHistory from '@/components/HealingHistory.vue'
import ImprovedXaiPanel from '@/components/ImprovedXaiPanel.vue'
import TelemetryChart from '@/components/TelemetryChart.vue'
import RLStats from '@/components/RLStats.vue'
import ManualOverride from '@/components/ManualOverride.vue'
import MapekIndicator from '@/components/MapekIndicator.vue'

const store = useNetworkStore()

const lastUpdated = computed(() => {
  if (!store.lastUpdated) return '--'
  return store.lastUpdated.toLocaleTimeString()
})

onMounted(() => {
  store.startAutoRefresh(2000)
})

onUnmounted(() => {
  store.stopAutoRefresh()
})
</script>