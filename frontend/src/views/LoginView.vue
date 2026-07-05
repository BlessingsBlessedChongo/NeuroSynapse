<template>
  <v-container fluid class="login-page fill-height">
    <v-row align="center" justify="center" class="fill-height">
      <v-col cols="12" sm="10" md="6" lg="5" xl="4">
        <v-sheet class="login-card pa-8 pa-sm-10 rounded-xl" elevation="0">
          <div class="text-center mb-8">
            <v-img
              :src="logoUrl"
              alt="NeuroSynapse"
              max-height="160"
              contain
              class="mx-auto login-logo"
            />
          </div>

          <div class="text-center mb-2">
            <p class="text-subtitle-1 font-weight-medium text-medium-emphasis login-tagline">
              An AI-Powered Self-Healing Network Intelligent System
            </p>
          </div>

          <div class="text-center mb-8">
            <h1 class="text-h5 font-weight-bold text-primary">Administrator Login</h1>
          </div>

          <v-form @submit.prevent="submitLogin">
            <v-text-field
              v-model="username"
              label="Username"
              variant="outlined"
              color="primary"
              prepend-inner-icon="mdi-account"
              autocomplete="username"
              required
              class="mb-2"
              hide-details="auto"
            />

            <v-text-field
              v-model="password"
              label="Password"
              variant="outlined"
              color="primary"
              prepend-inner-icon="mdi-lock"
              :append-inner-icon="showPassword ? 'mdi-eye-off' : 'mdi-eye'"
              :type="showPassword ? 'text' : 'password'"
              autocomplete="current-password"
              required
              class="mb-4"
              hide-details="auto"
              @click:append-inner="showPassword = !showPassword"
            />

            <v-alert
              v-if="store.authError"
              type="error"
              variant="tonal"
              density="comfortable"
              class="mb-4"
              prominent
            >
              {{ store.authError }}
            </v-alert>

            <v-btn
              type="submit"
              block
              size="large"
              class="login-btn text-white font-weight-bold mb-4"
              :loading="store.authenticating"
              :disabled="store.authenticating"
            >
              Sign In
            </v-btn>

            <p class="text-caption text-center text-medium-emphasis">
              Use an administrator account to access the self-healing network dashboard.
            </p>
          </v-form>
        </v-sheet>
      </v-col>
    </v-row>
  </v-container>
</template>

<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { useNetworkStore } from '@/stores/network'
import logoUrl from '@/assets/NeuroSynapse-web-logo.png'

const router = useRouter()
const store = useNetworkStore()

const username = ref('')
const password = ref('')
const showPassword = ref(false)

async function submitLogin() {
  const success = await store.login(username.value, password.value)
  if (success) {
    router.push({ name: 'dashboard' })
  }
}
</script>

<style scoped>
.login-page {
  min-height: 100vh;
  background:
    radial-gradient(ellipse at 20% 20%, rgba(0, 229, 255, 0.08) 0%, transparent 50%),
    radial-gradient(ellipse at 80% 80%, rgba(224, 64, 251, 0.06) 0%, transparent 50%),
    linear-gradient(180deg, #0f172a 0%, #070b14 100%);
}

.login-card {
  background: rgba(15, 23, 42, 0.55);
  backdrop-filter: blur(20px);
  -webkit-backdrop-filter: blur(20px);
  border: 1px solid rgba(148, 163, 184, 0.18);
  box-shadow:
    0 8px 32px rgba(0, 0, 0, 0.4),
    inset 0 1px 0 rgba(255, 255, 255, 0.05);
}

.login-logo {
  filter: drop-shadow(0 4px 24px rgba(0, 229, 255, 0.15));
}

.login-tagline {
  letter-spacing: 0.4px;
  line-height: 1.6;
}

.login-btn {
  background: linear-gradient(135deg, #00e5ff 0%, #38bdf8 50%, #0284c7 100%) !important;
  box-shadow: 0 4px 20px rgba(0, 229, 255, 0.35);
  letter-spacing: 0.5px;
  text-transform: none;
}

.login-btn:hover {
  box-shadow: 0 6px 28px rgba(0, 229, 255, 0.45);
}
</style>
