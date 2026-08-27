<template>
  <v-card class="policy-card rounded-xl pa-5 h-100 d-flex flex-column" elevation="0">
    <!-- Header -->
    <v-card-title class="d-flex align-center justify-space-between pa-0 mb-4 flex-shrink-0">
      <div class="d-flex align-center ga-3">
        <v-avatar color="violet" variant="tonal" size="38">
          <v-icon icon="mdi-tune-variant" size="22" />
        </v-avatar>
        <div>
          <h2 class="text-h6 font-weight-bold text-slate-100 mb-0 leading-tight">
            Healing Policy Configuration
          </h2>
          <p class="text-caption text-slate-400 mb-0 font-weight-regular mt-1">
            UC-01 · Operational thresholds & RL reward control parameters
          </p>
        </div>
      </div>
      <div class="d-flex align-center ga-2">
        <v-chip
          v-if="!store.isSuperAdmin"
          size="x-small"
          variant="tonal"
          color="amber-accent-3"
          class="font-weight-bold font-mono"
        >
          <v-icon icon="mdi-lock-outline" start size="12" />
          READ ONLY
        </v-chip>
        <v-btn
          icon="mdi-refresh"
          variant="tonal"
          color="slate-400"
          size="small"
          :loading="loading"
          aria-label="Refresh policy configuration"
          @click="load"
        />
      </div>
    </v-card-title>

    <!-- Content Body -->
    <div class="flex-grow-1 d-flex flex-column justify-space-between">
      <!-- Loading State -->
      <div v-if="loading && !form" class="pt-2">
        <v-row dense>
          <v-col v-for="n in 8" :key="n" cols="12" sm="6" class="pb-3">
            <v-skeleton-loader type="text" height="40" class="rounded-lg" />
          </v-col>
        </v-row>
      </div>

      <!-- Error State -->
      <div v-else-if="store.policyError && !form" class="state-panel text-center pa-6 my-auto">
        <v-avatar color="rose-400" variant="tonal" size="48" class="mb-3">
          <v-icon icon="mdi-alert-circle-outline" size="24" />
        </v-avatar>
        <p class="text-body-2 text-rose-300 mb-4 font-mono">{{ store.policyError }}</p>
        <v-btn variant="tonal" color="violet-accent" size="small" prepend-icon="mdi-refresh" @click="load">
          Retry
        </v-btn>
      </div>

      <!-- Form View -->
      <v-form v-else-if="form" class="d-flex flex-column justify-space-between h-100" @submit.prevent="save">
        <!-- Input Grid with explicit row spacing to prevent top-label truncation -->
        <v-row dense class="pt-2">
          <v-col cols="12" sm="6" class="pb-3">
            <v-text-field
              v-model.number="form.confidence_threshold"
              type="number"
              step="0.01"
              min="0"
              max="1"
              label="Auto-Heal Confidence Threshold"
              variant="outlined"
              density="compact"
              hide-details="auto"
              :readonly="!store.isSuperAdmin"
              class="dark-field"
            />
          </v-col>
          <v-col cols="12" sm="6" class="pb-3">
            <v-text-field
              v-model.number="form.healing_timeout_seconds"
              type="number"
              min="1"
              label="Healing Timeout (seconds)"
              variant="outlined"
              density="compact"
              hide-details="auto"
              :readonly="!store.isSuperAdmin"
              class="dark-field"
            />
          </v-col>
          <v-col cols="12" sm="6" class="pb-3">
            <v-text-field
              v-model.number="form.max_cpu_threshold"
              type="number"
              min="0"
              max="100"
              label="Max CPU Threshold (%)"
              variant="outlined"
              density="compact"
              hide-details="auto"
              :readonly="!store.isSuperAdmin"
              class="dark-field"
            />
          </v-col>
          <v-col cols="12" sm="6" class="pb-3">
            <v-text-field
              v-model.number="form.max_latency_threshold_ms"
              type="number"
              min="0"
              label="Max Latency Threshold (ms)"
              variant="outlined"
              density="compact"
              hide-details="auto"
              :readonly="!store.isSuperAdmin"
              class="dark-field"
            />
          </v-col>
          <v-col cols="12" sm="6" class="pb-3">
            <v-text-field
              v-model.number="form.max_packet_loss_threshold"
              type="number"
              min="0"
              max="100"
              label="Max Packet Loss Threshold (%)"
              variant="outlined"
              density="compact"
              hide-details="auto"
              :readonly="!store.isSuperAdmin"
              class="dark-field"
            />
          </v-col>
          <v-col cols="12" sm="6" class="pb-3">
            <v-text-field
              v-model.number="form.telemetry_interval_seconds"
              type="number"
              min="1"
              label="Telemetry Interval (seconds)"
              variant="outlined"
              density="compact"
              hide-details="auto"
              :readonly="!store.isSuperAdmin"
              class="dark-field"
            />
          </v-col>
          <v-col cols="12" sm="6" class="pb-3">
            <v-text-field
              v-model.number="form.rl_reward_success"
              type="number"
              step="0.1"
              label="RL Reward · Success"
              variant="outlined"
              density="compact"
              hide-details="auto"
              :readonly="!store.isSuperAdmin"
              class="dark-field"
            />
          </v-col>
          <v-col cols="12" sm="6" class="pb-3">
            <v-text-field
              v-model.number="form.rl_reward_failure"
              type="number"
              step="0.1"
              label="RL Reward · Failure"
              variant="outlined"
              density="compact"
              hide-details="auto"
              :readonly="!store.isSuperAdmin"
              class="dark-field"
            />
          </v-col>
        </v-row>

        <!-- Dynamic Alerts & Footer Actions -->
        <div class="mt-2">
          <v-alert
            v-if="saveError"
            type="error"
            variant="tonal"
            density="comfortable"
            class="mb-3 text-caption font-mono"
          >
            {{ saveError }}
          </v-alert>

          <v-alert
            v-if="saveSuccess"
            type="success"
            variant="tonal"
            density="comfortable"
            class="mb-3 text-caption font-mono"
          >
            Policy configuration saved successfully.
          </v-alert>

          <div class="d-flex align-center justify-space-between flex-wrap ga-2 pt-2">
            <p class="text-caption text-slate-400 mb-0 font-mono">
              Last updated {{ formattedUpdatedAt }}
              <span v-if="store.policyConfig?.updated_by_username" class="text-slate-200">
                by {{ store.policyConfig.updated_by_username }}
              </span>
            </p>

            <v-btn
              v-if="store.isSuperAdmin"
              type="submit"
              color="violet-accent"
              variant="flat"
              prepend-icon="mdi-content-save-outline"
              :loading="store.policySaving"
              class="font-weight-bold"
            >
              Save Policy
            </v-btn>
          </div>
        </div>
      </v-form>
    </div>
  </v-card>
</template>

<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { useNetworkStore } from '@/stores/network'

const store = useNetworkStore()
const loading = ref(false)
const form = ref(null)
const saveError = ref(null)
const saveSuccess = ref(false)

const formattedUpdatedAt = computed(() => {
  const updatedAt = store.policyConfig?.updated_at
  if (!updatedAt) return 'never'
  try {
    return new Date(updatedAt).toLocaleString()
  } catch {
    return 'unknown'
  }
})

async function load() {
  loading.value = true
  await store.fetchPolicyConfig()
  if (store.policyConfig) {
    form.value = { ...store.policyConfig }
  }
  loading.value = false
}

async function save() {
  saveError.value = null
  saveSuccess.value = false
  const payload = { ...form.value }
  delete payload.updated_by_username
  delete payload.updated_at

  const success = await store.updatePolicyConfig(payload)
  if (success) {
    saveSuccess.value = true
    form.value = { ...store.policyConfig }
    setTimeout(() => {
      saveSuccess.value = false
    }, 3000)
  } else {
    saveError.value = store.policyError
  }
}

watch(
  () => store.policyConfig,
  (value) => {
    if (value && !form.value) {
      form.value = { ...value }
    }
  },
)

onMounted(load)
</script>

<style scoped>
.policy-card {
  background: rgba(15, 23, 42, 0.65) !important;
  backdrop-filter: blur(16px);
  -webkit-backdrop-filter: blur(16px);
  border: 1px solid rgba(148, 163, 184, 0.12);
}

.dark-field :deep(.v-field) {
  background-color: rgba(7, 16, 24, 0.6) !important;
  border-radius: 8px;
}

.dark-field :deep(.v-field__outline) {
  --v-field-border-opacity: 0.15;
}

/* Fix floating outline label truncation on Vuetify dark fields */
.dark-field :deep(.v-field--label-floating .v-label) {
  background-color: #0f172a !important;
  padding: 0 6px;
  border-radius: 4px;
}

.state-panel {
  min-height: 200px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
}

.leading-tight { line-height: 1.15; }

.font-mono {
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace !important;
}
</style>