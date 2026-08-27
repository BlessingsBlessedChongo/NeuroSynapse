<template>
  <v-container fluid class="login-page fill-height pa-0">
    <v-row align="center" justify="center" class="fill-height ma-0">
      <v-col cols="12" sm="8" md="6" lg="4" xl="3">
        <!-- Login Card with entrance animation -->
        <v-sheet class="login-card pa-8 pa-sm-10 rounded-xl animate-fade-in" elevation="0">
          
          <!-- Logo Header -->
          <div class="text-center mb-6">
            <v-img
              :src="logoUrl"
              alt="NeuroSynapse"
              max-height="130"
              contain
              class="mx-auto login-logo"
            />
          </div>

          <!-- Refined Typography Hierarchy -->
          <div class="text-center mb-1">
            <p class="login-tagline text-overline text-slate-400 font-weight-medium">
              An AI-Powered Self-Healing Network Intelligent System
            </p>
          </div>

          <div class="text-center mb-6">
            <h1 class="login-title text-h5 font-weight-bold">Administrator Login</h1>
          </div>

          <!-- Form Area -->
          <v-form @submit.prevent="submitLogin">
            <v-text-field
              v-model="username"
              label="Username"
              variant="outlined"
              color="cyan-accent-2"
              prepend-inner-icon="mdi-account-outline"
              autocomplete="username"
              required
              class="custom-field mb-4"
              hide-details="auto"
            />

            <v-text-field
              v-model="password"
              label="Password"
              variant="outlined"
              color="cyan-accent-2"
              prepend-inner-icon="mdi-lock-outline"
              :append-inner-icon="showPassword ? 'mdi-eye-off-outline' : 'mdi-eye-outline'"
              :type="showPassword ? 'text' : 'password'"
              autocomplete="current-password"
              required
              class="custom-field mb-5"
              hide-details="auto"
              @click:append-inner="showPassword = !showPassword"
            />

            <!-- Animated Error State -->
            <v-slide-y-transition>
              <v-alert
                v-if="store.authError"
                type="error"
                variant="tonal"
                density="comfortable"
                class="mb-5 rounded-lg border-error"
                prominent
              >
                {{ store.authError }}
              </v-alert>
            </v-slide-y-transition>

            <!-- Action Button -->
            <v-btn
              type="submit"
              block
              size="x-large"
              class="login-btn font-weight-bold mb-6 rounded-lg text-slate-950"
              :loading="store.authenticating"
              :disabled="store.authenticating"
            >
              Sign In
            </v-btn>

            <p class="login-footer-text text-caption text-center">
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
/* Prevent unwanted browser scrollbars while keeping full screen height */
.login-page {
  min-height: 100vh;
  height: 100vh;
  overflow: hidden;
  background:
    radial-gradient(ellipse at 20% 20%, rgba(0, 229, 255, 0.1) 0%, transparent 50%),
    radial-gradient(ellipse at 80% 80%, rgba(168, 85, 247, 0.10) 0%, transparent 50%),
    linear-gradient(180deg, #0f172a 0%, #070b14 100%);
}

/* Glassmorphism Card Container */
.login-card {
  background: rgba(15, 23, 42, 0.65) !important;
  backdrop-filter: blur(24px);
  -webkit-backdrop-filter: blur(24px);
  border: 1px solid rgba(0, 229, 255, 0.15);
  box-shadow:
    0 20px 50px rgba(0, 0, 0, 0.6),
    inset 0 1px 0 rgba(255, 255, 255, 0.08);
  transition: transform 0.3s cubic-bezier(0.16, 1, 0.3, 1), box-shadow 0.3s ease;
}

.login-card:hover {
  border-color: rgba(0, 229, 255, 0.25);
  box-shadow:
    0 24px 60px rgba(0, 0, 0, 0.7),
    0 0 30px rgba(0, 229, 255, 0.08);
}

/* Typography Hierarchy Enhancements */
.login-tagline {
  letter-spacing: 1px !important;
  color: #94a3b8;
  font-size: 0.7rem !important;
  line-height: 1.4;
}

.login-title {
  color: #00e5ff;
  letter-spacing: 0.2px;
}

.login-footer-text {
  color: #64748b;
  line-height: 1.5;
}

/* Logo Ambient Glow */
.login-logo {
  filter: drop-shadow(0 6px 20px rgba(0, 229, 255, 0.22));
  transition: transform 0.4s ease, filter 0.4s ease;
}

.login-card:hover .login-logo {
  transform: scale(1.02);
  filter: drop-shadow(0 8px 28px rgba(0, 229, 255, 0.35));
}

/* Primary Cyan Action Button with High Contrast Text */
.login-btn {
  background: linear-gradient(135deg, #00e5ff 0%, #38bdf8 60%, #0284c7 100%) !important;
  color: #020617 !important; /* Dark text for WCAG AAA compliance against bright cyan */
  box-shadow: 0 4px 20px rgba(0, 229, 255, 0.3);
  letter-spacing: 0.5px;
  text-transform: none;
  transition: all 0.25s cubic-bezier(0.16, 1, 0.3, 1);
}

.login-btn:hover {
  transform: translateY(-2px);
  box-shadow: 0 8px 30px rgba(0, 229, 255, 0.5) !important;
}

.login-btn:active {
  transform: translateY(0);
}

/* Error Alert Formatting */
.border-error {
  border: 1px solid rgba(244, 63, 94, 0.3);
}

/* entrance animation */
.animate-fade-in {
  animation: cardEntrance 0.7s cubic-bezier(0.16, 1, 0.3, 1) forwards;
}

@keyframes cardEntrance {
  from {
    opacity: 0;
    transform: scale(0.96) translateY(12px);
  }
  to {
    opacity: 1;
    transform: scale(1) translateY(0);
  }
}
</style>