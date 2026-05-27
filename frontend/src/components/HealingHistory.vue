<template>
  <v-card color="surface" elevation="2" class="h-100">
    <v-card-title>
      <v-icon icon="mdi-bandage" class="mr-2 text-info"></v-icon>
      Recent Healing Actions
    </v-card-title>

    <v-list bg-color="transparent" max-height="400" class="overflow-y-auto">
      <v-list-item
        v-for="healing in store.recentHealings"
        :key="healing.id"
        :value="healing.id"
      >
        <template v-slot:prepend>
          <v-chip
            :color="healing.status === 'Executed' ? 'success' : 'error'"
            size="x-small"
            variant="flat"
          >
            {{ healing.action }}
          </v-chip>
        </template>

        <v-list-item-title class="text-body-2">
          Incident #{{ healing.incident_id }}
        </v-list-item-title>

        <v-list-item-subtitle class="text-caption">
          {{ healing.status }}
          <span class="mx-1">|</span>
          {{ formatTime(healing.created_at) }}
        </v-list-item-subtitle>
      </v-list-item>

      <v-list-item v-if="store.recentHealings.length === 0">
        <v-list-item-title class="text-secondary text-center py-4">
          <v-icon icon="mdi-clock-outline" size="40"></v-icon>
          <div class="mt-2">No healing actions yet</div>
        </v-list-item-title>
      </v-list-item>
    </v-list>
  </v-card>
</template>

<script setup>
import { useNetworkStore } from '@/stores/network'

const store = useNetworkStore()

function formatTime(isoString) {
  if (!isoString) return '--'
  return new Date(isoString).toLocaleTimeString()
}
</script>