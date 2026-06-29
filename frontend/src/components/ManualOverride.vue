<template>
  <v-card color="surface" elevation="2" v-if="store.openIncidents > 0">
    <v-card-title>
      <v-icon icon="mdi-account-check" class="mr-2 text-warning"></v-icon>
      Manual Override
    </v-card-title>
    <v-card-text>
      <p v-if="hasManualReview" class="text-body-2">
        An incident requires your attention. Use the buttons in the <strong>Latest Incidents</strong> panel to approve or reject the healing action.
      </p>
      <p v-else class="text-secondary text-body-2">
        No manual review needed – all incidents are being handled automatically.
      </p>
    </v-card-text>
  </v-card>
</template>

<script setup>
import { computed } from 'vue'
import { useNetworkStore } from '@/stores/network'

const store = useNetworkStore()
const hasManualReview = computed(() =>
  store.latestIncidents.some(i => i.status === 'Manual Review')
)
</script>