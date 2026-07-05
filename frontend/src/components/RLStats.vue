<template>
  <v-card color="surface" elevation="2" class="rl-card h-100">
    <v-card-title class="d-flex align-center">
      <v-icon icon="mdi-robot" class="mr-2 text-primary" />
      Reinforcement Learning Agent
      <v-spacer />
      <v-btn
        icon="mdi-refresh"
        variant="text"
        size="small"
        :loading="loading"
        aria-label="Refresh RL stats"
        @click="loadStats"
      />
    </v-card-title>

    <v-card-subtitle class="text-medium-emphasis pb-2">
      Q-learning training metrics and top remediation pairs
    </v-card-subtitle>

    <v-card-text>
      <div v-if="loading && !loaded" class="state-panel text-center py-10">
        <v-progress-circular indeterminate color="primary" size="48" width="4" class="mb-4" />
        <p class="text-body-2 text-medium-emphasis">Loading RL training metrics…</p>
      </div>

      <div v-else-if="error" class="state-panel text-center py-8">
        <v-icon icon="mdi-alert-circle-outline" size="48" color="error" class="mb-3" />
        <p class="text-body-2 text-error mb-4">{{ error }}</p>
        <v-btn
          variant="outlined"
          color="primary"
          prepend-icon="mdi-refresh"
          :loading="loading"
          @click="loadStats"
        >
          Retry
        </v-btn>
      </div>

      <div v-else-if="store.rlStats">
        <v-row dense>
          <v-col cols="6">
            <v-sheet color="background" variant="outlined" rounded="lg" class="pa-3 metric-tile">
              <p class="text-caption text-medium-emphasis text-uppercase mb-1">Training Episodes</p>
              <p class="text-h5 font-weight-bold text-info mb-0">
                {{ store.rlStats.episode_count ?? 0 }}
              </p>
            </v-sheet>
          </v-col>
          <v-col cols="6">
            <v-sheet color="background" variant="outlined" rounded="lg" class="pa-3 metric-tile">
              <p class="text-caption text-medium-emphasis text-uppercase mb-1">Exploration Rate (ε)</p>
              <p class="text-h5 font-weight-bold text-purple-lighten-1 mb-0">
                {{ formatEpsilon(store.rlStats.epsilon) }}
              </p>
            </v-sheet>
          </v-col>
          <v-col cols="6">
            <v-sheet color="background" variant="outlined" rounded="lg" class="pa-3 metric-tile">
              <p class="text-caption text-medium-emphasis text-uppercase mb-1">Optimization Delta</p>
              <p
                class="text-h5 font-weight-bold mb-0"
                :class="optimizationDelta >= 0 ? 'text-success' : 'text-error'"
              >
                {{ formatOptimizationDelta(store.rlStats) }}
              </p>
            </v-sheet>
          </v-col>
          <v-col cols="6">
            <v-sheet color="background" variant="outlined" rounded="lg" class="pa-3 metric-tile">
              <p class="text-caption text-medium-emphasis text-uppercase mb-1">Q-Table Size</p>
              <p class="text-h5 font-weight-bold text-cyan mb-0">
                {{ store.rlStats.q_table_size ?? 0 }}
              </p>
            </v-sheet>
          </v-col>
        </v-row>

        <v-divider class="my-5" />

        <section>
          <p class="text-caption text-uppercase text-medium-emphasis font-weight-bold mb-3">
            <v-icon icon="mdi-star-four-points" size="16" class="mr-1" />
            Top State → Remediation Pairs
          </p>

          <div v-if="topPairs.length > 0" class="d-flex flex-wrap ga-2">
            <v-chip
              v-for="pair in topPairs"
              :key="pair.key"
              color="primary"
              variant="tonal"
              size="small"
              prepend-icon="mdi-arrow-right-bold"
            >
              {{ pair.label }}
            </v-chip>
          </div>

          <p v-else class="text-body-2 text-medium-emphasis mb-0">
            No Q-table entries recorded yet. Run training episodes to populate state-action pairs.
          </p>
        </section>
      </div>
    </v-card-text>
  </v-card>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useNetworkStore } from '@/stores/network'

const store = useNetworkStore()
const loading = ref(false)
const loaded = ref(false)
const error = ref(null)

const ACTION_LABELS = {
  0: 'Restart Service',
  1: 'Reroute Traffic',
  2: 'Block Source IP',
  3: 'Reboot Device',
  4: 'Clear Cache',
  5: 'Rate Limit',
}

const FAILURE_LABELS = {
  SERVICE_CRASH: 'Service Crash',
  LINK_FAILURE: 'Link Failure',
  DDOS_ATTACK: 'DDoS Attack',
}

const optimizationDelta = computed(() => {
  const stats = store.rlStats
  if (!stats) return 0
  const delta = stats.optimization_delta ?? stats.recent_performance ?? 0
  return Number(delta)
})

const topPairs = computed(() => {
  const bestActions = store.rlStats?.best_actions
  if (!bestActions || typeof bestActions !== 'object') return []

  return Object.entries(bestActions).map(([failureType, data]) => {
    const actionIndex = data?.action_index ?? 0
    const qValue = data?.q_value ?? 0
    const stateLabel = FAILURE_LABELS[failureType] || failureType.replace(/_/g, ' ')
    const actionLabel = ACTION_LABELS[actionIndex] || `Action ${actionIndex}`

    return {
      key: `${failureType}-${actionIndex}`,
      label: `${stateLabel} → ${actionLabel} (Q: ${qValue})`,
    }
  })
})

function formatEpsilon(epsilon) {
  const value = Number(epsilon ?? 0)
  return `${(value * 100).toFixed(1)}%`
}

function formatOptimizationDelta(stats) {
  const delta = stats.optimization_delta ?? stats.recent_performance ?? 0
  const pct = Number(delta) * 100
  const sign = pct >= 0 ? '+' : ''
  return `${sign}${pct.toFixed(1)}%`
}

async function loadStats() {
  loading.value = true
  error.value = null

  try {
    await store.fetchRLStats()
    loaded.value = true
  } catch {
    error.value = store.rlError || 'Failed to load RL stats.'
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  loadStats()
})
</script>

<style scoped>
.rl-card {
  border: 1px solid rgba(148, 163, 184, 0.08);
}

.metric-tile {
  border-color: rgba(148, 163, 184, 0.12) !important;
  height: 100%;
}

.text-cyan {
  color: #00e5ff !important;
}

.state-panel {
  min-height: 180px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
}
</style>
