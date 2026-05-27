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
      ></v-btn>
    </v-card-title>

    <v-card-text v-if="store.rlStats">
      <v-row dense>
        <v-col cols="6">
          <div class="text-caption text-secondary">Training Episodes</div>
          <div class="text-h6">{{ store.rlStats.episode_count }}</div>
        </v-col>
        <v-col cols="6">
          <div class="text-caption text-secondary">Exploration Rate</div>
          <div class="text-h6">{{ (store.rlStats.epsilon * 100).toFixed(1) }}%</div>
        </v-col>
        <v-col cols="6">
          <div class="text-caption text-secondary">Recent Performance</div>
          <div class="text-h6 text-success">{{ (store.rlStats.recent_performance * 100).toFixed(0) }}%</div>
        </v-col>
        <v-col cols="6">
          <div class="text-caption text-secondary">Q-Table Size</div>
          <div class="text-h6">{{ store.rlStats.q_table_size }}</div>
        </v-col>
      </v-row>

      <v-divider class="my-3"></v-divider>

      <div class="text-caption text-secondary mb-2">Learned Best Actions</div>
      <v-chip
        v-for="(info, failureType) in store.rlStats.best_actions"
        :key="failureType"
        size="small"
        variant="flat"
        color="primary"
        class="mr-1 mb-1"
      >
        {{ failureType }}: Action {{ info.action_index }}
      </v-chip>
    </v-card-text>

    <v-card-text v-else>
      <div class="text-center text-secondary py-2">
        <v-progress-circular indeterminate color="primary" class="mb-2"></v-progress-circular>
        <div>Loading RL stats...</div>
      </div>
    </v-card-text>
  </v-card>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useNetworkStore } from '@/stores/network'

const store = useNetworkStore()
const loading = ref(false)

async function loadStats() {
  loading.value = true
  await store.fetchRLStats()
  loading.value = false
}

onMounted(() => {
  loadStats()
})
</script>