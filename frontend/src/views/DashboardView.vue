<template>
  <v-container fluid class="pa-6">
    <!-- Stats Cards -->
    <div class="ns-enter" style="--ns-delay: 0ms">
      <StatsCards />
    </div>

    <!-- Device Status + Telemetry: paired side-by-side to reclaim vertical space -->
    <v-row class="mt-4">
      <v-col cols="12" xl="7">
        <div class="ns-enter" style="--ns-delay: 60ms">
          <DeviceList />
        </div>
      </v-col>
      <v-col cols="12" xl="5">
        <div class="ns-enter" style="--ns-delay: 120ms">
          <TelemetryChart />
        </div>
      </v-col>
    </v-row>

    <!-- Incidents and Healings -->
    <v-row class="mt-4">
      <v-col cols="12" md="6">
        <div class="ns-enter" style="--ns-delay: 160ms">
          <IncidentList />
        </div>
      </v-col>
      <v-col cols="12" md="6">
        <div class="ns-enter" style="--ns-delay: 200ms">
          <HealingHistory />
        </div>
      </v-col>
    </v-row>

    <!-- XAI and RL Stats -->
    <v-row class="mt-4">
      <v-col cols="12" lg="7">
        <div class="ns-enter" style="--ns-delay: 240ms">
          <ImprovedXaiPanel />
        </div>
      </v-col>
      <v-col cols="12" lg="5">
        <div class="ns-enter" style="--ns-delay: 280ms">
          <RLStats />
        </div>
      </v-col>
    </v-row>

    <!-- Manual Override -->
    <v-row class="mt-4">
      <v-col cols="12">
        <div class="ns-enter" style="--ns-delay: 320ms">
          <ManualOverride />
        </div>
      </v-col>
    </v-row>

    <!-- MAPE-K Loop and Policy Configuration -->
    <v-row class="mt-4">
      <v-col cols="12" lg="6">
        <div class="ns-enter" style="--ns-delay: 360ms">
          <MapekIndicator />
        </div>
      </v-col>
      <v-col cols="12" lg="6">
        <div class="ns-enter" style="--ns-delay: 400ms">
          <PolicyConfig />
        </div>
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
import PolicyConfig from '@/components/PolicyConfig.vue'

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
