<template>
  <v-card color="surface" elevation="2">
    <v-card-title class="d-flex align-center">
      <v-icon icon="mdi-router-network" class="mr-2"></v-icon>
      Network Devices
      <v-spacer></v-spacer>
      <span class="text-caption text-secondary">
        Last updated: {{ lastUpdated }}
      </span>
    </v-card-title>

    <v-list bg-color="transparent">
      <v-list-item
        v-for="device in store.devices"
        :key="device.id"
        :value="device.id"
        color="primary"
      >
        <template v-slot:prepend>
          <v-icon :icon="statusDot(device.status)" :color="statusColor(device.status)" size="12"></v-icon>
        </template>

        <v-list-item-title>
          <strong>{{ device.name }}</strong>
          <span class="text-secondary text-caption ml-2">{{ device.ip }}</span>
        </v-list-item-title>

        <v-list-item-subtitle>
          <v-chip
            :color="statusColor(device.status)"
            size="x-small"
            variant="flat"
            class="mr-1"
          >
            {{ device.status }}
          </v-chip>
        </v-list-item-subtitle>

        <template v-slot:append>
          <div class="text-caption text-secondary text-right">
            <div>CPU: {{ formatValue(device.cpu) }}%</div>
            <div>Mem: {{ formatValue(device.memory) }}%</div>
            <div>Loss: {{ formatValue(device.packet_loss) }}%</div>
          </div>
        </template>
      </v-list-item>

      <v-list-item v-if="store.devices.length === 0">
        <v-list-item-title class="text-secondary text-center">
          No devices connected
        </v-list-item-title>
      </v-list-item>
    </v-list>
  </v-card>
</template>

<script setup>
import { computed } from 'vue'
import { useNetworkStore } from '@/stores/network'

const store = useNetworkStore()

const lastUpdated = computed(() => {
  if (!store.lastUpdated) return '--'
  return store.lastUpdated.toLocaleTimeString()
})

function statusColor(status) {
  switch (status) {
    case 'HEALTHY': return 'success'
    case 'WARNING': return 'warning'
    case 'CRITICAL': return 'error'
    default: return 'secondary'
  }
}

function statusDot(status) {
  switch (status) {
    case 'HEALTHY': return 'mdi-circle'
    case 'WARNING': return 'mdi-circle'
    case 'CRITICAL': return 'mdi-circle'
    default: return 'mdi-circle-outline'
  }
}

function formatValue(val) {
  if (val === null || val === undefined) return '--'
  return val.toFixed(1)
}
</script>