<template>
  <v-app>
    <SystemHeader />
    <v-main>
      <router-view />
    </v-main>
  </v-app>
</template>

<script setup>
import { onMounted } from 'vue'
import { useNetworkStore } from '@/stores/network'
import SystemHeader from '@/components/SystemHeader.vue'

const store = useNetworkStore()

onMounted(() => {
  store.checkAuth()
})
</script>

<style>
.v-application {
  background-color: #0f172a !important;
}
</style>
