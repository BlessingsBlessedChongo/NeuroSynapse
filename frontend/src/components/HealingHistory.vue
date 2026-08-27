<template>
  <v-card class="healing-card rounded-xl pa-2 h-100 d-flex flex-column" elevation="0">
    <v-card-title class="d-flex align-center py-3 px-4 flex-shrink-0">
      <div class="d-flex align-center ga-2">
        <v-avatar color="cyan-accent-4" variant="tonal" size="36" class="mr-1">
          <v-icon icon="mdi-medical-bag" size="20" />
        </v-avatar>
        <div>
          <span class="text-h6 font-weight-bold text-slate-100">Self-Healing Event Log</span>
          <p class="text-caption text-slate-400 mb-0 font-weight-regular">
            Chronological record of automated mitigations — click row for output
          </p>
        </div>
      </div>
    </v-card-title>

    <v-card-text class="pa-2 flex-grow-1 d-flex flex-column overflow-hidden" style="min-height: 0;">
      <!-- Empty State -->
      <div v-if="store.recentHealings.length === 0" class="empty-state text-center py-12 px-4 my-auto">
        <v-icon icon="mdi-history" size="48" color="slate-600" class="mb-3" />
        <p class="text-body-1 font-weight-semibold text-slate-300 mb-0">No self-healing events logged</p>
        <p class="text-caption text-slate-400">Events will populate here as agents execute network remediations</p>
      </div>

      <!-- Scrollable Container -->
      <div v-else class="scrollable-log-container pr-1">
        <v-list bg-color="transparent" class="py-0">
          <template v-for="healing in store.recentHealings" :key="healing.id">
            <v-list-item class="healing-item rounded-lg px-3 py-3 mb-2" @click="toggleExpand(healing.id)">
              <template #prepend>
                <v-avatar
                  :color="runtimeStatusColor(healing.status)"
                  variant="tonal"
                  size="36"
                  rounded="lg"
                  class="mr-3"
                >
                  <v-icon :icon="runtimeStatusIcon(healing.status)" size="20" />
                </v-avatar>
              </template>

              <v-list-item-title class="font-weight-bold text-body-2 text-slate-100">
                {{ healing.action_type_display || healing.action_type }}
              </v-list-item-title>

              <v-list-item-subtitle class="text-slate-400 font-mono text-caption">
                Incident #{{ healing.incident_id || healing.incident }}
                <span v-if="healing.sandbox_result" class="mx-1">·</span>
                <span v-if="healing.sandbox_result" class="text-cyan-accent-2">
                  Sandbox: {{ healing.sandbox_result }}
                </span>
              </v-list-item-subtitle>

              <template #append>
                <div class="text-right d-flex align-center ga-3">
                  <div>
                    <v-chip
                      size="x-small"
                      :color="runtimeStatusColor(healing.status)"
                      variant="flat"
                      class="font-weight-bold mb-1 text-uppercase"
                    >
                      {{ runtimeStatusLabel(healing.status) }}
                    </v-chip>
                    <div class="text-caption text-slate-400 font-mono">
                      {{ formatTimestamp(healing.created_at) }}
                    </div>
                  </div>
                  <v-icon
                    :icon="expandedId === healing.id ? 'mdi-chevron-up' : 'mdi-chevron-down'"
                    size="20"
                    color="slate-400"
                  />
                </div>
              </template>
            </v-list-item>

            <!-- Expansion Panel -->
            <v-expand-transition>
              <div v-if="expandedId === healing.id" class="expand-panel px-3 pb-3 pt-1 mb-2">
                <v-sheet rounded="lg" class="pa-3 console-panel">
                  <p class="text-caption text-cyan-accent-2 font-weight-bold text-uppercase mb-1 font-mono">
                    > Executed Command
                  </p>
                  <pre class="code-block mb-3 font-mono">{{ healing.command || 'No command recorded' }}</pre>

                  <p class="text-caption text-cyan-accent-2 font-weight-bold text-uppercase mb-1 font-mono">
                    > Terminal Output
                  </p>
                  <pre class="code-block mb-0 font-mono">{{ healing.execution_output || 'No output captured.' }}</pre>
                </v-sheet>

                <div class="mt-3">
                  <v-btn
                    size="small"
                    variant="tonal"
                    color="violet-accent"
                    prepend-icon="mdi-brain"
                    class="font-weight-semibold"
                    :loading="explainingId === healing.id"
                    @click.stop="loadExplanation(healing.id)"
                  >
                    Explain Action
                  </v-btn>
                </div>

                <v-sheet
                  v-if="explanations[healing.id]"
                  rounded="lg"
                  class="pa-3 mt-3 xai-explanation-panel"
                >
                  <p class="text-body-2 font-weight-semibold text-slate-200 mb-1">
                    {{ explanations[healing.id].summary }}
                  </p>
                  <p class="text-caption text-slate-300 mb-2">
                    <strong>Rationale:</strong> {{ explanations[healing.id].why_this_action }}
                  </p>
                  <p v-if="explanations[healing.id].rl_context" class="text-caption text-violet-accent mb-0 font-mono">
                    <v-icon icon="mdi-robot" size="14" class="mr-1" />
                    {{ explanations[healing.id].rl_context }}
                  </p>
                </v-sheet>
              </div>
            </v-expand-transition>
          </template>
        </v-list>
      </div>
    </v-card-text>
  </v-card>
</template>

<script setup>
import { reactive, ref } from 'vue'
import { useNetworkStore } from '@/stores/network'

const store = useNetworkStore()
const expandedId = ref(null)
const explainingId = ref(null)
const explanations = reactive({})

function toggleExpand(id) {
  expandedId.value = expandedId.value === id ? null : id
}

function runtimeStatusLabel(status) {
  switch (status) {
    case 'EXECUTED':
      return 'Success'
    case 'EXECUTING':
      return 'Running'
    case 'SANDBOXING':
      return 'Sandboxing'
    case 'VERIFICATION':
      return 'Verification'
    case 'ROLLBACK':
      return 'Rolled Back'
    case 'PENDING':
      return 'Pending'
    default:
      return status || 'Unknown'
  }
}

function runtimeStatusColor(status) {
  switch (status) {
    case 'EXECUTED':
      return 'emerald-accent-4'
    case 'EXECUTING':
      return 'cyan-accent-3'
    case 'SANDBOXING':
      return 'amber-accent-3'
    case 'VERIFICATION':
      return 'blue-accent-2'
    case 'ROLLBACK':
      return 'violet'
    case 'PENDING':
      return 'slate-400'
    default:
      return 'slate-400'
  }
}

function runtimeStatusIcon(status) {
  switch (status) {
    case 'EXECUTED':
      return 'mdi-check-circle'
    case 'EXECUTING':
      return 'mdi-loading'
    case 'SANDBOXING':
      return 'mdi-shield-search'
    case 'VERIFICATION':
      return 'mdi-magnify'
    case 'ROLLBACK':
      return 'mdi-backup-restore'
    case 'PENDING':
      return 'mdi-clock-outline'
    default:
      return 'mdi-clock-outline'
  }
}

function formatTimestamp(isoString) {
  if (!isoString) return '--'
  try {
    return new Date(isoString).toLocaleString([], {
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
    })
  } catch {
    return '--'
  }
}

async function loadExplanation(healingId) {
  explainingId.value = healingId
  try {
    const detail = await store.fetchHealingActionDetail(healingId)
    if (detail?.xai_explanation) {
      explanations[healingId] = detail.xai_explanation
    } else if (detail) {
      // Fallback: build a basic explanation from the action data
      explanations[healingId] = {
        summary: `${detail.action_type_display || detail.action_type} was executed on this incident.`,
        why_this_action: 'This action was selected based on the AI diagnosis and RL policy.',
        what_happened: detail.execution_output || 'No output captured.',
        rl_context: null,
      }
    }
  } catch (error) {
    console.error('Failed to load healing explanation:', error)
  } finally {
    explainingId.value = null
  }
}
</script>

<style scoped>
.healing-card {
  background: rgba(15, 23, 42, 0.65) !important;
  backdrop-filter: blur(16px);
  -webkit-backdrop-filter: blur(16px);
  border: 1px solid rgba(148, 163, 184, 0.12);
}

.scrollable-log-container {
  height: 0;
  flex: 1 1 auto;
  overflow-y: auto;
}

.scrollable-log-container::-webkit-scrollbar {
  width: 6px;
}

.scrollable-log-container::-webkit-scrollbar-track {
  background: rgba(15, 23, 42, 0.2);
  border-radius: 4px;
}

.scrollable-log-container::-webkit-scrollbar-thumb {
  background: rgba(148, 163, 184, 0.25);
  border-radius: 4px;
}

.scrollable-log-container::-webkit-scrollbar-thumb:hover {
  background: rgba(0, 229, 255, 0.4);
}

.healing-item {
  background: rgba(30, 41, 59, 0.4);
  border: 1px solid rgba(148, 163, 184, 0.08);
  cursor: pointer;
  transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1);
}

.healing-item:hover {
  background: rgba(30, 41, 59, 0.75);
  border-color: rgba(0, 229, 255, 0.3);
}

.console-panel {
  background: rgba(7, 16, 24, 0.8) !important;
  border: 1px solid rgba(0, 229, 255, 0.15);
}

.xai-explanation-panel {
  background: rgba(30, 41, 59, 0.6) !important;
  border: 1px solid rgba(224, 64, 251, 0.2);
}

.empty-state {
  min-height: 220px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
}

.code-block {
  color: #a7f3d0;
  font-size: 0.78rem;
  margin: 0;
  white-space: pre-wrap;
  word-break: break-word;
  max-height: 180px;
  overflow-y: auto;
}

.font-mono {
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace !important;
}
</style>