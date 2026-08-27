<template>
  <v-card class="rl-card rounded-xl pa-2 h-100 d-flex flex-column" elevation="0">
    <!-- Header -->
    <v-card-title class="d-flex align-center justify-space-between py-3 px-4 flex-shrink-0">
      <div class="d-flex align-center ga-2">
        <v-avatar color="cyan-accent-4" variant="tonal" size="36" class="mr-1">
          <v-icon icon="mdi-robot" size="20" />
        </v-avatar>
        <div>
          <span class="text-h6 font-weight-bold text-slate-100">Reinforcement Learning Agent</span>
          <p class="text-caption text-slate-400 mb-0 font-weight-regular">
            Q-learning training metrics & policy feedback loop
          </p>
        </div>
      </div>
      <v-btn
        icon="mdi-refresh"
        variant="tonal"
        color="slate-400"
        size="small"
        :loading="loading"
        aria-label="Refresh RL stats"
        @click="loadStats"
      />
    </v-card-title>

    <!-- Main Content Body -->
    <div class="card-body-wrapper flex-grow-1 px-4 pb-4">
      <!-- Loading State -->
      <div v-if="loading && !loaded" class="pt-2">
        <v-row dense class="mb-3">
          <v-col v-for="n in 3" :key="n" cols="6" sm="4">
            <v-skeleton-loader type="text" height="64" class="rounded-lg" />
          </v-col>
        </v-row>
        <v-skeleton-loader type="image" height="90" class="rounded-lg" />
      </div>

      <!-- Error State -->
      <div v-else-if="error" class="state-panel text-center pa-6">
        <v-avatar color="rose-400" variant="tonal" size="52" class="mb-3">
          <v-icon icon="mdi-alert-circle-outline" size="26" />
        </v-avatar>
        <p class="text-body-2 text-rose-300 mb-4 font-mono">{{ error }}</p>
        <v-btn
          variant="tonal"
          color="cyan-accent-3"
          size="small"
          prepend-icon="mdi-refresh"
          :loading="loading"
          @click="loadStats"
        >
          Retry Load
        </v-btn>
      </div>

      <!-- Stats Loaded -->
      <div v-else-if="store.rlStats" class="scrollable-content pr-2">
        <!-- Metric Grid -->
        <v-row dense class="mb-3">
          <v-col cols="6" sm="4">
            <v-sheet class="pa-3 metric-tile rounded-lg d-flex flex-column justify-center">
              <span class="text-caption text-slate-400 text-uppercase font-mono mb-1">Episodes</span>
              <span class="text-h5 font-weight-bold text-cyan-accent-3 font-mono">
                {{ store.rlStats.episode_count ?? 0 }}
              </span>
            </v-sheet>
          </v-col>

          <v-col cols="6" sm="4">
            <v-sheet class="pa-3 metric-tile rounded-lg d-flex flex-column justify-center">
              <span class="text-caption text-slate-400 text-uppercase font-mono mb-1">Exploration (ε)</span>
              <span class="text-h5 font-weight-bold text-violet-accent font-mono">
                {{ formatPercent(store.rlStats.epsilon) }}
              </span>
            </v-sheet>
          </v-col>

          <v-col cols="6" sm="4">
            <v-sheet class="pa-3 metric-tile rounded-lg d-flex flex-column justify-center">
              <span class="text-caption text-slate-400 text-uppercase font-mono mb-1">Learning Rate</span>
              <span class="text-h5 font-weight-bold text-slate-100 font-mono">
                {{ store.rlStats.learning_rate ?? '--' }}
              </span>
            </v-sheet>
          </v-col>

          <v-col cols="6" sm="4">
            <v-sheet class="pa-3 metric-tile rounded-lg d-flex flex-column justify-center">
              <span class="text-caption text-slate-400 text-uppercase font-mono mb-1">Success Rate</span>
              <span class="text-h5 font-weight-bold text-emerald-accent-4 font-mono">
                {{ formatPercent(store.rlStats.recent_performance) }}
              </span>
            </v-sheet>
          </v-col>

          <v-col cols="6" sm="4">
            <v-sheet class="pa-3 metric-tile rounded-lg d-flex flex-column justify-center">
              <span class="text-caption text-slate-400 text-uppercase font-mono mb-1">Optimization Δ</span>
              <span
                class="text-h5 font-weight-bold font-mono"
                :class="optimizationDelta >= 0 ? 'text-emerald-accent-4' : 'text-rose-400'"
              >
                {{ formatSignedPercent(store.rlStats.optimization_delta) }}
              </span>
            </v-sheet>
          </v-col>

          <v-col cols="6" sm="4">
            <v-sheet class="pa-3 metric-tile rounded-lg d-flex flex-column justify-center">
              <span class="text-caption text-slate-400 text-uppercase font-mono mb-1">Q-Table States</span>
              <span class="text-h5 font-weight-bold text-amber-accent-3 font-mono">
                {{ store.rlStats.q_table_size ?? 0 }}
              </span>
            </v-sheet>
          </v-col>
        </v-row>

        <!-- Target Progress Card -->
        <v-sheet rounded="lg" class="pa-3 mb-4 progress-card">
          <div class="d-flex justify-space-between align-center mb-2">
            <span class="text-caption text-slate-300 font-weight-semibold font-mono">
              Objective Target Improvement
            </span>
            <span class="text-caption text-emerald-accent-4 font-weight-bold font-mono">
              {{ targetProgress.toFixed(0) }}% Achieved
            </span>
          </div>

          <v-progress-linear
            :model-value="targetProgress"
            height="8"
            rounded
            color="emerald-accent-4"
            bg-color="rgba(148, 163, 184, 0.15)"
            class="mb-2"
          />

          <p class="text-caption text-slate-400 mb-0 font-mono leading-tight">
            Target: <span class="text-slate-200">{{ formatPercent(store.rlStats.target_improvement) }}</span> improvement · Currently at
            <span :class="optimizationDelta >= 0 ? 'text-emerald-accent-4' : 'text-rose-400'" class="font-weight-bold">
              {{ formatSignedPercent(store.rlStats.optimization_delta) }}
            </span>
            ({{ store.rlStats.replay_buffer_size ?? 0 }} experiences replayed)
          </p>
        </v-sheet>

        <!-- Top Policy Actions -->
        <section class="mb-2">
          <p class="text-caption text-uppercase text-slate-400 font-weight-bold mb-2 d-flex align-center ga-1 font-mono">
            <v-icon icon="mdi-star-four-points" size="14" color="violet-accent" />
            Top State → Remediation Pairs
          </p>

          <div v-if="topPairs.length > 0" class="d-flex flex-column ga-2">
            <v-sheet
              v-for="pair in topPairs"
              :key="pair.key"
              rounded="lg"
              class="pa-2 px-3 pair-chip d-flex align-center justify-space-between ga-2"
            >
              <div class="d-flex align-center ga-2 min-w-0">
                <v-icon icon="mdi-arrow-right-bold-circle-outline" size="16" color="cyan-accent-3" class="flex-shrink-0" />
                <span class="text-caption text-slate-200 font-mono text-truncate">
                  {{ pair.stateLabel }}
                  <v-icon icon="mdi-chevron-right" size="14" class="text-slate-500 mx-1" />
                  <strong class="text-cyan-accent-2">{{ pair.actionLabel }}</strong>
                </span>
              </div>
              <v-chip size="x-small" variant="tonal" color="violet-accent" class="font-mono font-weight-bold flex-shrink-0">
                Q: {{ pair.qValue }}
              </v-chip>
            </v-sheet>
          </div>

          <p v-else class="text-caption text-slate-400 mb-0 font-mono italic">
            No Q-table policy entries logged yet.
          </p>
        </section>
      </div>

      <!-- No RL Stats State -->
      <div v-else class="state-panel text-center pa-6">
        <v-avatar color="slate-700" variant="tonal" size="52" class="mb-3">
          <v-icon icon="mdi-robot-off-outline" size="26" color="slate-400" />
        </v-avatar>
        <p class="text-body-2 text-slate-400 mb-0 font-mono">No RL training metrics detected.</p>
      </div>
    </div>
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
  PERFORMANCE_DEGRADATION: 'Performance Degradation',
}

const optimizationDelta = computed(() => Number(store.rlStats?.optimization_delta ?? 0))

const targetProgress = computed(() => {
  const target = Number(store.rlStats?.target_improvement ?? 0.15)
  const delta = optimizationDelta.value
  if (target <= 0) return 0
  return Math.min(100, Math.max(0, (delta / target) * 100))
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
      stateLabel,
      actionLabel,
      qValue,
    }
  })
})

function formatPercent(value) {
  return `${(Number(value ?? 0) * 100).toFixed(1)}%`
}

function formatSignedPercent(value) {
  const pct = Number(value ?? 0) * 100
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
  background: rgba(15, 23, 42, 0.65) !important;
  backdrop-filter: blur(16px);
  -webkit-backdrop-filter: blur(16px);
  border: 1px solid rgba(148, 163, 184, 0.12);
  min-height: 380px;
}

.card-body-wrapper {
  display: flex;
  flex-direction: column;
  position: relative;
  min-height: 0;
  overflow: hidden;
}

.scrollable-content {
  max-height: 340px;
  overflow-y: auto;
}

.scrollable-content::-webkit-scrollbar {
  width: 6px;
}

.scrollable-content::-webkit-scrollbar-track {
  background: rgba(15, 23, 42, 0.2);
  border-radius: 4px;
}

.scrollable-content::-webkit-scrollbar-thumb {
  background: rgba(148, 163, 184, 0.25);
  border-radius: 4px;
}

.metric-tile {
  background: rgba(7, 16, 24, 0.6) !important;
  border: 1px solid rgba(148, 163, 184, 0.08);
}

.progress-card {
  background: rgba(30, 41, 59, 0.5) !important;
  border: 1px solid rgba(148, 163, 184, 0.12);
}

.pair-chip {
  background: rgba(7, 16, 24, 0.6) !important;
  border: 1px solid rgba(0, 229, 255, 0.15);
}

.state-panel {
  min-height: 220px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
}

.leading-tight {
  line-height: 1.35;
}

.font-mono {
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace !important;
}
</style>