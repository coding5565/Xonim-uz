<script setup lang="ts">
import { UtensilsCrossed, Coffee, Leaf, Wheat } from '@lucide/vue'
defineProps<{name: string; category: string; image?: string | null}>()
</script>
<template><div class="dish-art" :class="{'art-green': category.includes('Salat'), 'art-tea': category.includes('Ichimlik'), 'art-bread': category.includes('Non')}"><img v-if="image" :src="image" :alt="name" loading="lazy"><template v-else><span class="plate"><component :is="category.includes('Salat') ? Leaf : category.includes('Ichimlik') ? Coffee : category.includes('Non') ? Wheat : UtensilsCrossed" :size="34" :stroke-width="1.25"/></span><small>HONIM KITCHEN</small></template></div></template>
