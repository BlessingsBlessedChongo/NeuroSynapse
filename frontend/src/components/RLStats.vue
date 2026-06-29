<template>
  <v-card color="surface" elevation="2">
    <v-card-title>
      <v-icon icon="mdi-robot" class="mr-2 text-primary"></v-icon>
      RL Agent Status
      <v-spacer></v-spacer>
      <v-btn
        icon="mdi-refresh"
        size="small"
        variant="text"
        @click="loadStats"
        :loading="loading"
        :disabled="!loaded && loading"
      ></v-btn>
    </v-card-title>

    <v-card-text v-if="store.rlStats && loaded">
      <v-row dense>
        <v-col cols="6">
          <div class="text-caption text-secondary">Training Episodes</div>
          <div class="text-h6">{{ store.rlStats.episode_count || 0 }}</div>
        </v-col>
        <v-col cols="6">
          <div class="text-caption text-secondary">Exploration Rate</div>
          <div class="text-h6">{{ ((store.rlStats.epsilon || 0) * 100).toFixed(1) }}%</div>
        </v-col>
        <v-col cols="6">
          <div class="text-caption text-secondary">Recent Performance</div>
          <div class="text-h6 text-success">{{ ((store.rlStats.recent_performance || 0) * 100).toFixed(0) }}%</div>
        </v-col>
        <v-col cols="6">
          <div class="text-caption text-secondary">Q-Table Size</div>
          <div class="text-h6">{{ store.rlStats.q_table_size || 0 }}</div>
        </v-col>
      </v-row>
    </v-card-text>

    <v-card-text v-else-if="error" class="text-center py-4">
      <v-icon icon="mdi-alert-circle" size="48" color="error" class="mb-2"></v-icon>
      <p class="text-error text-body-2">{{ error }}</p>
      <v-btn size="small" variant="outlined" @click="loadStats" class="mt-2" :loading="loading">
        Retry
      </v-btn>
    </v-card-text>

    <v-card-text v-else-if="loading && !loaded" class="text-center py-4">
      <v-progress-circular indeterminate color="primary" size="32" class="mb-2"></v-progress-circular>
      <div class="text-secondary text-body-2">Loading RL stats...</div>
    </v-card-text>

    <v-card-text v-else class="text-center py-4">
      <v-icon icon="mdi-information" size="40" color="info" class="mb-2"></v-icon>
      <p class="text-secondary text-body-2">No RL data available</p>
    </v-card-text>
  </v-card>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useNetworkStore } from '@/stores/network'

const store = useNetworkStore()
const loading = ref(false)
const loaded = ref(false)
const error = ref(null)

async function loadStats() {
  loading.value = true
  error.value = null

  try {
    await store.fetchRLStats()
    loaded.value = true
  } catch (err) {
    error.value = 'Failed to load RL stats'
    console.error('RL stats fetch error:', err)
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  loadStats()
})
</script>