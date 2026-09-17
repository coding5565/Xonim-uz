<script setup lang="ts">
import { dateLabel } from '../api'
import type { Order } from '../types'
defineProps<{order:Order}>()
</script>
<template><div class="ticket-body"><div class="ticket-top"><strong>#{{ String(order.id).padStart(4,'0') }}</strong><time>{{ dateLabel(order.created_at) }}</time></div><div class="ticket-place">{{ order.table?`${order.table}-stol · ${order.waiter||'Ofitsiant'}`:'Tezkor savdo' }}</div><div class="ticket-lines"><div v-for="line in order.lines" :key="line.id" class="ticket-line"><strong>{{ line.quantity }} × {{ line.name }}</strong><p v-if="line.note">Izoh: {{ line.note }}</p></div></div><small>Kiritgan: {{ order.cashier_name||'Kassa' }}</small></div></template>
