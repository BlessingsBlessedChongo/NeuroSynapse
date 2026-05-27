<template>
  <v-app>
    <SystemHeader />
    <v-main>
      <router-view />
    </v-main>
  </v-app>
</template>

<script setup>
import SystemHeader from '@/components/SystemHeader.vue'
</script>

<style>
.v-application {
  background-color: #0f172a !important;
}
</style>