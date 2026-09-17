<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { Search, Leaf, ArrowUpRight, Clock3, MapPin, Sparkles, UtensilsCrossed } from '@lucide/vue'
import { api, money } from '../api'
import type { Category, Dish } from '../types'
import DishArt from '../components/DishArt.vue'

const data = ref<{ name: string; categories: Category[]; dishes: Dish[] }>()
const category = ref(0)
const search = ref('')
const error = ref('')
const visible = computed(() => data.value?.dishes.filter(d =>
  (!category.value || d.category === category.value) && d.name.toLocaleLowerCase().includes(search.value.toLocaleLowerCase()),
) || [])
const activeCategory = computed(() => data.value?.categories.find(item => item.id === category.value)?.name || 'Barcha taomlar')

async function load() {
  error.value = ''
  try { data.value = await api('public/menu/honim/') }
  catch (exception) { error.value = (exception as Error).message }
}

onMounted(load)
</script>

<template>
  <div class="public-menu">
    <header class="public-header">
      <RouterLink to="/menu" class="brand"><span class="brand-mark">h<span>•</span></span><span class="brand-text">honim<span>RESTORAN MENYUSI</span></span></RouterLink>
      <div class="public-header-meta"><span class="open-badge"><i /> Bugun ochiq</span><span class="public-language">O‘zbekcha</span></div>
    </header>
    <section class="menu-hero">
      <div class="hero-copy"><span class="eyebrow"><Sparkles :size="13" /> DID BILAN TAYYORLANGAN</span><h1>Ta’mlar<br><em>bir dasturxonda.</em></h1><p>Sevimli taomlaringizni tanlang.<br>Buyurtmani ofitsiantga ayting.</p><div class="hero-details"><span><UtensilsCrossed :size="15" /> {{ data?.dishes.length || 0 }} ta taom</span><span><Clock3 :size="15" /> Har kuni xizmatda</span></div></div>
      <div class="hero-ornament"><Leaf :size="142" :stroke-width="0.8" /><span>HONIM<br>RESTAURANT</span></div>
    </section>
    <main class="public-content">
      <div class="menu-intro"><div><span class="eyebrow">MENYU</span><h2>{{ activeCategory }}</h2></div><span class="menu-count">{{ visible.length }} ta tanlov</span></div>
      <div class="public-controls"><div class="tabs" aria-label="Taom kategoriyalari"><button :class="{ selected: !category }" @click="category = 0">Barchasi</button><button v-for="item in data?.categories" :key="item.id" :class="{ selected: category === item.id }" @click="category = item.id">{{ item.name }}</button></div><div class="search-field"><Search :size="18" /><input v-model="search" placeholder="Taom qidiring" aria-label="Taom qidirish"></div></div>
      <p v-if="error" class="alert error">{{ error }} <button class="text-link" @click="load">Qayta urinish</button></p>
      <div v-if="!data && !error" class="empty-state">Menyu tayyorlanmoqda…</div>
      <div class="dish-grid"><article v-for="dish in visible" :key="dish.id" class="dish-card"><div class="dish-image-wrap"><DishArt :name="dish.name" :category="dish.category_name" :image="dish.image" /><span v-if="!dish.available" class="dish-state unavailable">Hozir mavjud emas</span></div><div class="dish-details"><span class="eyebrow">{{ dish.category_name }}</span><h3>{{ dish.name }}</h3><p v-if="dish.description">{{ dish.description }}</p><footer><strong>{{ money(dish.price) }} <small>so‘m</small></strong><span>{{ dish.portion }}</span></footer></div></article></div>
      <p v-if="data && !visible.length" class="empty-state">Qidiruv bo‘yicha taom topilmadi.</p>
    </main>
    <footer class="public-footer"><div class="footer-mark">h<span>•</span></div><strong>honim.</strong><p><MapPin :size="14" /> Buyurtma berish uchun ofitsiantga murojaat qiling.</p><RouterLink to="/login">Xodimlar uchun kirish <ArrowUpRight :size="14" /></RouterLink></footer>
  </div>
</template>
