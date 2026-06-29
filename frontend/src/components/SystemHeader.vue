<template>
  <!-- 1. Entire app bar hidden until authentication is verified -->
  <v-app-bar v-if="store.authenticated" flat density="comfortable" class="header-bar">
    
    <!-- 2. Branded Logo Framing: Directly embedded (Avatar removed) -->
    <v-img
      :src="logoUrl"
      alt="NeuroSynapse"
      max-height="50"
      max-width="140"
      contain
      class="ml-3"
    />

    <!-- 3. Centered Operator Profile: Minimalist icon + username -->
    <div class="center-content d-flex align-center">
      <v-icon icon="mdi-account-circle" class="me-2" />
      <span class="text-body-2 text-truncate" style="max-width: 200px; max-height: 60px;">
        {{ store.username }}
      </span>
    </div>

    <!-- 4. Action Navigation (Right-Aligned) -->
    <v-spacer />
    <div class="d-flex align-center ga-3 me-3">
      <v-chip 
        :color="statusColor" 
        text-color="white" 
        size="small" 
        variant="tonal"
        class="text-uppercase font-weight-medium"
      >
        <v-icon start :icon="statusIcon" size="18"></v-icon>
        {{ statusText }}
      </v-chip>
      
      <!-- Explicit, clean Sign Out icon button -->
      <v-btn 
        icon="mdi-logout" 
        variant="text" 
        color="white" 
        density="compact" 
        @click="handleLogout"
      />
    </div>

  </v-app-bar>
</template>

<script setup>
import { computed, nextTick } from 'vue' // Added nextTick
import { useRouter } from 'vue-router'
import { useNetworkStore } from '@/stores/network'
import logoUrl from '@/assets/NeuroSynapse-web-logo.png'

const store = useNetworkStore()
const router = useRouter()

const statusColor = computed(() => {
  switch (store.overallHealth) {
    case 'HEALTHY': return 'cyan accent-4'
    case 'WARNING': return 'amber accent-4'
    case 'CRITICAL': return 'red darken-2'
    default: return 'grey'
  }
})

const statusIcon = computed(() => {
  switch (store.overallHealth) {
    case 'HEALTHY': return 'mdi-check-circle'
    case 'WARNING': return 'mdi-alert'
    case 'CRITICAL': return 'mdi-alert-circle'
    default: return 'mdi-help-circle'
  }
})

const statusText = computed(() => {
  switch (store.overallHealth) {
    case 'HEALTHY': return 'SYSTEM HEALTHY'
    case 'WARNING': return 'WARNING'
    case 'CRITICAL': return 'INCIDENT ACTIVE'
    default: return 'UNKNOWN'
  }
})

// Fixed Logout Logic
async function handleLogout() {
  // Step 1: Force clear local storage/persisted state manually (Prevents pinia re-hydration)
  localStorage.removeItem('YOUR_AUTH_TOKEN_NAME') // IMPORTANT: Replace with your actual localStorage key
  sessionStorage.clear()

  // Step 2: Execute store logout
  await store.logout()

  // Step 3: Wait for Vue to flush the v-if reactivity
  await nextTick()

  // Step 4: Route to login
  router.push({ name: 'login' })

  // OPTIONAL (GUARANTEED FIX):
  // If the above still forces you to refresh, uncomment the line below. 
  // This is the most reliable way to completely clean an SPA session on logout:
  // window.location.reload() 
}
</script>

<style scoped>
.header-bar {
  /* Use !important to override potential Vuetify theme defaults */
  background: #0b1220 !important; 
  border-bottom: 1px solid rgba(148, 163, 184, 0.12);
  position: relative;
}

.center-content {
  position: absolute;
  left: 50%;
  transform: translateX(-50%);
  color: #ffffff;
  z-index: 1; /* Ensure it sits above potential overlay overlaps */
  pointer-events: none; /* Prevents the text from blocking the click on the header itself */
}
</style>