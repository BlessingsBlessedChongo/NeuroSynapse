<template>
  <v-container fluid class="login-page">
    <v-row align="center" justify="center" class="fill-height">
      <v-col cols="12" sm="8" md="5">
        <v-sheet class="pa-8 rounded-lg login-sheet" elevation="12">
          <!-- Logo Element (Top) -->
          <div class="text-center mb-6">
            <v-img 
              :src="logoUrl"
              alt="NeuroSynapse" 
              max-height="160px" 
              contain 
              class="mx-auto"
            />
          </div>

          <!-- Subtitle Typography (Middle) -->
          <div class="text-center mb-4">
            <div class="text-subtitle-1 font-weight-bold text-white" style="letter-spacing: 0.5px; line-height: 1.6;">
              An AI Powered Self-Healing Network Intelligent System
            </div>
          </div>

          <!-- Title (Bottom of Header) -->
          <div class="text-center mb-8">
            <div class="text-h5 font-weight-bold text-primary">Administrator Login</div>
          </div>

          <v-form @submit.prevent="submitLogin" ref="loginForm">
            <v-text-field
              label="Username"
              v-model="username"
              dense
              outlined
              rounded
              prepend-inner-icon="mdi-account"
              autocomplete="username"
              required
            />

            <v-text-field
              label="Password"
              v-model="password"
              :type="showPassword ? 'text' : 'password'"
              dense
              outlined
              rounded
              prepend-inner-icon="mdi-lock"
              :append-inner-icon="showPassword ? 'mdi-eye' : 'mdi-eye-off'"
              @click:append-inner="showPassword = !showPassword"
              autocomplete="current-password"
              required
            />

            <v-alert v-if="store.authError" type="error" prominent class="mb-4">
              {{ store.authError }}
            </v-alert>

            <v-btn
              type="submit"
              color="primary"
              class="mb-4"
              block
              :loading="store.authenticating"
            >
              Sign in
            </v-btn>

            <div class="text-caption text-secondary text-center">
              Use an administrator account to access the self-healing network dashboard.
            </div>
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

const submitLogin = async () => {
  const success = await store.login(username.value, password.value)
  if (success) {
    router.push({ name: 'dashboard' })
  }
}
</script>

<style scoped>
.login-page {
  min-height: calc(100vh - 64px);
  background: linear-gradient(180deg, rgba(15, 23, 42, 0.95) 0%, rgba(7, 11, 20, 0.95) 100%);
}

.login-sheet {
  background: rgba(18, 25, 40, 0.96);
  border: 1px solid rgba(148, 163, 184, 0.12);
}
</style>
