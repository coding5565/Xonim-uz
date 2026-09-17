<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { CheckCircle2, ChefHat, Clock3, RefreshCw, Utensils } from '@lucide/vue'
import { api } from '../api'
import type { Order } from '../types'
import KitchenTicket from '../components/KitchenTicket.vue'

const orders=ref<Order[]>([]), loading=ref(true), busy=ref<number>(), error=ref(''), updated=ref<Date>()
let timer:number|undefined
const queued=computed(()=>orders.value.filter(order=>order.preparation_status==='queued'))
const preparing=computed(()=>orders.value.filter(order=>order.preparation_status==='preparing'))
const ready=computed(()=>orders.value.filter(order=>order.preparation_status==='ready'))

async function load(silent=false){
  if(!silent)loading.value=true
  try{orders.value=await api<Order[]>('kitchen/orders/');updated.value=new Date();error.value=''}
  catch(e){error.value=(e as Error).message}
  finally{loading.value=false}
}
async function advance(order:Order){
  const next=order.preparation_status==='queued'?'preparing':order.preparation_status==='preparing'?'ready':'served'
  busy.value=order.id;error.value=''
  try{await api(`kitchen/orders/${order.id}/status/`,{method:'POST',body:JSON.stringify({status:next})});await load(true)}
  catch(e){error.value=(e as Error).message;await load(true)}
  finally{busy.value=undefined}
}
const actionLabel=(status:string)=>status==='queued'?'Tayyorlashni boshlash':status==='preparing'?'Tayyor bo‘ldi':'Mijozga topshirildi'
onMounted(()=>{load();timer=window.setInterval(()=>load(true),4000)})
onUnmounted(()=>timer&&window.clearInterval(timer))
</script>

<template>
  <div class="page-heading kitchen-heading"><div><span class="eyebrow">JONLI OSHXONA EKRANI</span><h1>Oshxona<span class="heading-dot">.</span></h1><p>Kassadan tushgan buyurtmalar har 4 soniyada avtomatik yangilanadi.</p></div><button class="button secondary" :disabled="loading" @click="load()"><RefreshCw :size="17" :class="{spin:loading}"/>Yangilash</button></div>
  <p v-if="error" class="alert error">{{ error }}</p>
  <div class="kitchen-summary"><div><span class="kitchen-dot queued"/><strong>{{ queued.length }}</strong><small>Yangi</small></div><div><span class="kitchen-dot preparing"/><strong>{{ preparing.length }}</strong><small>Tayyorlanmoqda</small></div><div><span class="kitchen-dot ready"/><strong>{{ ready.length }}</strong><small>Tayyor</small></div><span v-if="updated">Yangilandi: {{ updated.toLocaleTimeString('uz-UZ',{hour:'2-digit',minute:'2-digit',second:'2-digit'}) }}</span></div>
  <div class="kitchen-board">
    <section class="kitchen-column queued"><header><Clock3 :size="19"/><div><h2>Yangi buyurtmalar</h2><p>Tayyorlashni boshlash kerak</p></div><strong>{{ queued.length }}</strong></header><div class="kitchen-cards"><article v-for="order in queued" :key="order.id" class="kitchen-ticket is-new"><KitchenTicket :order="order"/><button class="button kitchen-action" :disabled="busy===order.id" @click="advance(order)"><ChefHat :size="17"/>{{ busy===order.id?'Saqlanmoqda…':actionLabel(order.preparation_status) }}</button></article><div v-if="!queued.length" class="kitchen-empty"><CheckCircle2/><span>Yangi buyurtma yo‘q</span></div></div></section>
    <section class="kitchen-column preparing"><header><ChefHat :size="19"/><div><h2>Tayyorlanmoqda</h2><p>Oshpaz ishlayotgan buyurtmalar</p></div><strong>{{ preparing.length }}</strong></header><div class="kitchen-cards"><article v-for="order in preparing" :key="order.id" class="kitchen-ticket"><KitchenTicket :order="order"/><button class="button kitchen-action" :disabled="busy===order.id" @click="advance(order)"><CheckCircle2 :size="17"/>{{ busy===order.id?'Saqlanmoqda…':actionLabel(order.preparation_status) }}</button></article><div v-if="!preparing.length" class="kitchen-empty"><ChefHat/><span>Jarayonda buyurtma yo‘q</span></div></div></section>
    <section class="kitchen-column ready"><header><CheckCircle2 :size="19"/><div><h2>Tayyor</h2><p>Mijozga berilishi kerak</p></div><strong>{{ ready.length }}</strong></header><div class="kitchen-cards"><article v-for="order in ready" :key="order.id" class="kitchen-ticket"><KitchenTicket :order="order"/><button class="button kitchen-action" :disabled="busy===order.id" @click="advance(order)"><Utensils :size="17"/>{{ busy===order.id?'Saqlanmoqda…':actionLabel(order.preparation_status) }}</button></article><div v-if="!ready.length" class="kitchen-empty"><Utensils/><span>Tayyor buyurtma yo‘q</span></div></div></section>
  </div>
</template>
