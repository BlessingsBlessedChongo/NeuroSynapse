<template>
  <v-app-bar v-if="store.authenticated" flat density="comfortable" class="header-bar">
    <v-img
      :src="logoUrl"
      alt="NeuroSynapse"
      max-height="40"
      max-width="120"
      contain
      class="ml-4 mr-2 flex-grow-0"
    />

    <span class="text-h6 font-weight-bold text-primary text-no-wrap">NeuroSynapse</span>

    <v-spacer />

    <div class="d-flex align-center ga-2 ga-sm-3 mr-3 mr-sm-4">
      <v-chip
        :color="healthChipColor"
        size="small"
        variant="tonal"
        class="font-weight-medium"
        prepend-icon="mdi-heart-pulse"
      >
        {{ healthChipLabel }}
      </v-chip>

      <v-chip
        :color="store.openIncidents > 0 ? 'error' : 'success'"
        size="small"
        variant="tonal"
        class="font-weight-medium"
        prepend-icon="mdi-alert-octagon-outline"
      >
        {{ store.openIncidents }} Open
      </v-chip>

      <v-chip
        color="cyan"
        size="small"
        variant="tonal"
        class="font-weight-medium d-none d-sm-flex"
        prepend-icon="mdi-check-decagram"
      >
        {{ store.healedToday }} Healed Today
      </v-chip>

      <v-divider vertical class="mx-1 d-none d-md-flex" />

      <div class="d-none d-md-flex align-center text-body-2 text-medium-emphasis">
        <v-icon icon="mdi-account-circle" size="20" class="mr-1" />
        <span class="text-truncate" style="max-width: 140px">{{ store.username }}</span>
      </div>

      <v-btn
        icon="mdi-logout"
        variant="text"
        color="secondary"
        density="comfortable"
        aria-label="Sign out"
        @click="handleLogout"
      />
    </div>
  </v-app-bar>
</template>

<script setup>
import { computed } from 'vue'
import { useRouter } from 'vue-router'
import { useNetworkStore } from '@/stores/network'
import logoUrl from '@/assets/NeuroSynapse-web-logo.png'

const store = useNetworkStore()
const router = useRouter()

const healthChipColor = computed(() => {
  switch (store.overallHealth) {
    case 'HEALTHY':
      return 'success'
    case 'WARNING':
      return 'warning'
    case 'CRITICAL':
      return 'error'
    default:
      return 'secondary'
  }
})

const healthChipLabel = computed(() => {
  switch (store.overallHealth) {
    case 'HEALTHY':
      return 'Telemetry Healthy'
    case 'WARNING':
      return 'Telemetry Degraded'
    case 'CRITICAL':
      return 'Incident Active'
    default:
      return 'Status Unknown'
  }
})

async function handleLogout() {
  store.stopAutoRefresh()
  await store.logout()
  router.push({ name: 'login' })
}
</script>

<style scoped>
.header-bar {
  background: rgba(11, 18, 32, 0.95) !important;
  backdrop-filter: blur(12px);
  border-bottom: 1px solid rgba(148, 163, 184, 0.12);
}
</style>
