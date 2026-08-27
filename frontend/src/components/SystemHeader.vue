<template>
  <v-app-bar v-if="store.authenticated" flat density="comfortable" class="header-bar px-2">
    <!-- Brand Identity Logo + Styled Typography -->
    <div class="d-flex align-center cursor-pointer ml-2 mr-6" @click="router.push({ name: 'dashboard' })">
      <v-img
        :src="logoUrl"
        alt="NeuroSynapse"
        max-height="36"
        max-width="36"
        contain
        class="mr-3 brand-logo"
      />
      <div class="brand-text text-h6 font-weight-bold">
        <span class="text-white">Neuro</span><span class="brand-cyan">Synapse</span>
      </div>
    </div>

    <v-spacer />

    <!-- Status Indicators & User Profile -->
    <div class="d-flex align-center ga-2 ga-sm-3 mr-2">
      <v-chip
        :color="healthChipColor"
        size="small"
        variant="tonal"
        class="font-weight-semibold status-chip"
        prepend-icon="mdi-heart-pulse"
      >
        {{ healthChipLabel }}
      </v-chip>

      <v-chip
        :color="store.openIncidents > 0 ? 'error' : 'success'"
        size="small"
        variant="tonal"
        class="font-weight-semibold status-chip"
        prepend-icon="mdi-alert-octagon-outline"
      >
        {{ store.openIncidents }} Open
      </v-chip>

      <v-chip
        color="cyan-accent-2"
        size="small"
        variant="tonal"
        class="font-weight-semibold status-chip d-none d-sm-flex"
        prepend-icon="mdi-check-decagram-outline"
      >
        {{ store.resolvedIncidents }} Resolved
      </v-chip>

      <v-divider vertical class="mx-1 d-none d-md-flex opacity-20" />

      <v-chip
        size="small"
        variant="outlined"
        color="slate-300"
        class="d-none d-md-flex font-weight-medium user-role-chip"
        prepend-icon="mdi-shield-account-outline"
      >
        {{ roleLabel }}
      </v-chip>

      <div class="d-none d-md-flex align-center text-body-2 text-slate-300 ml-1">
        <v-icon icon="mdi-account-circle-outline" size="20" class="mr-1 text-cyan-accent-2" />
        <span class="text-truncate font-weight-medium" style="max-width: 130px">{{ store.username }}</span>
      </div>

      <v-btn
        icon="mdi-logout-variant"
        variant="text"
        color="slate-400"
        density="comfortable"
        class="logout-btn"
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
    case 'HEALTHY': return 'success'
    case 'WARNING': return 'warning'
    case 'CRITICAL': return 'error'
    default: return 'secondary'
  }
})

const healthChipLabel = computed(() => {
  switch (store.overallHealth) {
    case 'HEALTHY': return 'Telemetry Healthy'
    case 'WARNING': return 'Telemetry Degraded'
    case 'CRITICAL': return 'Incident Active'
    default: return 'Status Unknown'
  }
})

const roleLabel = computed(() => {
  switch (store.role) {
    case 'SUPER_ADMIN': return 'Super Administrator'
    case 'ADMIN': return 'Network Administrator'
    case 'VIEWER': return 'Read-Only Viewer'
    default: return 'Administrator'
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
  background: rgba(15, 23, 42, 0.75) !important;
  backdrop-filter: blur(16px);
  -webkit-backdrop-filter: blur(16px);
  border-bottom: 1px solid rgba(0, 229, 255, 0.12);
}

.brand-logo {
  filter: drop-shadow(0 0 10px rgba(0, 229, 255, 0.3));
}

.brand-text {
  letter-spacing: -0.2px;
}

.brand-cyan {
  color: #00e5ff;
  text-shadow: 0 0 12px rgba(0, 229, 255, 0.4);
}

.status-chip {
  backdrop-filter: blur(8px);
  border: 1px solid rgba(255, 255, 255, 0.05);
}

.user-role-chip {
  border-color: rgba(148, 163, 184, 0.2);
  background: rgba(15, 23, 42, 0.4);
}

.logout-btn:hover {
  color: #f43f5e !important;
  background: rgba(244, 63, 94, 0.1);
}
</style>