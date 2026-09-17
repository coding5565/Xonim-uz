<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { BarChart3, ChefHat, CircleAlert, Coins, PackageCheck, Pencil, Plus, RefreshCw, Trash2 } from '@lucide/vue'
import { api, list, money } from '../api'
import type { Dish, Ingredient, Recipe } from '../types'
import AppModal from '../components/AppModal.vue'

const recipes = ref<Recipe[]>([]), dishes = ref<Dish[]>([]), ingredients = ref<Ingredient[]>([])
const error = ref(''), formError = ref(''), loading = ref(false), busy = ref(false), recipeModal = ref(false), itemModal = ref(false), editId = ref<number>()
const form = reactive({ dish: 0 as number | null, name: '', yield_quantity: '1', yield_unit: 'porsiya', selling_price: '0', active: true, lines: [] as { ingredient:number; quantity:string; batch_cost:string }[] })
const item = reactive({ name: '', unit: 'kg', minimum: '0' })
const linked = computed(() => recipes.value.filter(item => item.dish).length)
const batchProfit = computed(() => recipes.value.reduce((total, item) => total + Number(item.gross_profit) * Number(item.yield_quantity), 0))
const wholeMoney = (value: string | number) => money(Math.round(Number(value)))
const yieldLabel = (value: string) => Number(value).toLocaleString('uz-UZ', { maximumFractionDigits: 3 })

async function load() {
  loading.value = true; error.value = ''
  try { [recipes.value, dishes.value, ingredients.value] = await Promise.all([list<Recipe>('recipes/'), list<Dish>('dishes/'), list<Ingredient>('ingredients/')]) }
  catch (exception) { error.value = (exception as Error).message }
  finally { loading.value = false }
}
function openRecipe(recipe?: Recipe) {
  formError.value = ''; editId.value = recipe?.id
  Object.assign(form, recipe ? { dish: recipe.dish, name: recipe.name, yield_quantity: String(Number(recipe.yield_quantity)), yield_unit: recipe.yield_unit, selling_price: String(Number(recipe.selling_price)), active: recipe.active, lines: recipe.lines.map(line => ({ ingredient: line.ingredient, quantity: String(Number(line.quantity)), batch_cost: String(Number(line.batch_cost)) })) } : { dish: null, name: '', yield_quantity: '1', yield_unit: 'porsiya', selling_price: '0', active: true, lines: ingredients.value.length ? [{ ingredient: ingredients.value[0].id, quantity: '', batch_cost: '' }] : [] })
  recipeModal.value = true
}
function addLine() { if (ingredients.value.length) form.lines.push({ ingredient: ingredients.value[0].id, quantity: '', batch_cost: '' }) }
function removeLine(index: number) { form.lines.splice(index, 1) }
async function saveRecipe() {
  busy.value = true; formError.value = ''
  try {
    const body = { ...form, dish: form.dish || null, lines: form.lines.map(line => ({ ...line, quantity: Number(line.quantity), batch_cost: Number(line.batch_cost) })) }
    await api(`recipes/${editId.value ? `${editId.value}/` : ''}`, { method: editId.value ? 'PATCH' : 'POST', body: JSON.stringify(body) })
    recipeModal.value = false; await load()
  } catch (exception) { formError.value = (exception as Error).message }
  finally { busy.value = false }
}
async function saveItem() {
  busy.value = true; formError.value = ''
  try { await api('ingredients/', { method: 'POST', body: JSON.stringify(item) }); itemModal.value = false; await load(); if (ingredients.value.length && !form.lines.length) addLine() }
  catch (exception) { formError.value = (exception as Error).message }
  finally { busy.value = false }
}
onMounted(load)
</script>

<template>
  <div class="page-heading"><div><span class="eyebrow">TANNARX VA MARJA</span><h1>Retseptlar va foyda<span class="heading-dot">.</span></h1><p>Har taomning batch tannarxi, porsiya tannarxi va yalpi foydasi.</p></div><div class="heading-actions"><button class="button secondary" @click="itemModal=true; formError=''; Object.assign(item,{name:'',unit:'kg',minimum:'0'})"><Plus :size="17"/>Mahsulot</button><button class="button primary" :disabled="!ingredients.length" @click="openRecipe()"><Plus :size="17"/>Retsept</button><button class="button secondary icon-button" :disabled="loading" aria-label="Yangilash" @click="load"><RefreshCw :size="17" :class="{ spin: loading }"/></button></div></div>
  <p v-if="error" class="alert error">{{ error }}</p>
  <div class="recipe-summary"><article><ChefHat :size="21"/><div><small>Retseptlar</small><strong>{{ recipes.length }} ta</strong></div></article><article><PackageCheck :size="21"/><div><small>Menyuga bog‘langan</small><strong>{{ linked }} ta</strong></div></article><article><Coins :size="21"/><div><small>Batchlardagi yalpi foyda</small><strong>{{ wholeMoney(batchProfit) }} so‘m</strong></div></article></div>
  <div v-if="loading && !recipes.length" class="empty-state">Retseptlar yuklanmoqda…</div>
  <section v-for="recipe in recipes" :key="recipe.id" class="panel recipe-card"><header><div><span class="eyebrow">{{ recipe.dish_name || 'MENYUGA HALI BOG‘LANMAGAN' }}</span><h2>{{ recipe.name }}</h2><p>{{ yieldLabel(recipe.yield_quantity) }} {{ recipe.yield_unit }} · sotuv narxi {{ wholeMoney(recipe.selling_price) }} so‘m</p></div><div class="recipe-card-actions"><span class="status" :class="recipe.dish ? 'paid' : 'open'">{{ recipe.dish ? 'Faol' : 'Draft' }}</span><button class="icon-button" :aria-label="`${recipe.name} tahrirlash`" @click="openRecipe(recipe)"><Pencil :size="17"/></button></div></header><div class="recipe-metrics"><div><small>Batch tannarxi</small><strong>{{ wholeMoney(recipe.batch_cost) }} so‘m</strong></div><div><small>1 {{ recipe.yield_unit }} tannarxi</small><strong>{{ wholeMoney(recipe.unit_cost) }} so‘m</strong></div><div><small>1 birlik yalpi foyda</small><strong class="profit">{{ wholeMoney(recipe.gross_profit) }} so‘m</strong></div></div><div class="table-wrap"><table><thead><tr><th>MASALLIQ</th><th>MIQDOR</th><th>BATCH XARAJATI</th></tr></thead><tbody><tr v-for="line in recipe.lines" :key="line.id"><td><strong>{{ line.ingredient_name }}</strong></td><td>{{ yieldLabel(line.quantity) }} {{ line.unit }}</td><td class="number">{{ wholeMoney(line.batch_cost) }} so‘m</td></tr></tbody></table></div></section>
  <p v-if="recipes.some(recipe => !recipe.dish)" class="data-note"><CircleAlert :size="15"/>Bulyon kalkulyatsiyasi saqlandi, ammo menyuda Bulyon taomi yo‘q. Uni menyuga qo‘shgach retseptga bog‘lanadi.</p><p class="data-note">Yalpi foyda sotuv narxidan retsept tannarxi ayirilgan qiymat. Ijara, oylik va umumiy xarajatlar sof foydada alohida hisoblanadi.</p>
  <AppModal :open="recipeModal" :title="editId ? 'Retseptni tahrirlash' : 'Yangi retsept'" @close="!busy && (recipeModal=false)"><form @submit.prevent="saveRecipe"><fieldset :disabled="busy"><div class="form-row"><label>Retsept nomi<input v-model="form.name" required maxlength="120" placeholder="Masalan, Mastava"></label><label>Menyu taomi<select v-model="form.dish"><option :value="null">Hali bog‘lanmagan</option><option v-for="dish in dishes" :key="dish.id" :value="dish.id">{{ dish.name }}</option></select></label></div><div class="form-row"><label>Batch chiqimi<input v-model="form.yield_quantity" required type="number" min="0.001" step="0.001"></label><label>Birlik<select v-model="form.yield_unit"><option>dona</option><option>porsiya</option></select></label><label>1 birlik sotuv narxi<input v-model="form.selling_price" required type="number" min="0" step="1"></label></div><div class="recipe-form-lines"><div class="recipe-line-head"><strong>Masalliqlar</strong><button type="button" class="text-link" @click="addLine"><Plus :size="15"/>Qator</button></div><div v-for="(line,index) in form.lines" :key="index" class="recipe-form-line"><select v-model="line.ingredient" required><option v-for="ingredient in ingredients" :key="ingredient.id" :value="ingredient.id">{{ ingredient.name }} · {{ ingredient.unit }}</option></select><input v-model="line.quantity" required type="number" min="0.001" step="0.001" placeholder="Miqdor"><input v-model="line.batch_cost" required type="number" min="0" step="1" placeholder="Xarajat, so‘m"><button type="button" class="icon-button" :disabled="form.lines.length===1" aria-label="Qatorni o‘chirish" @click="removeLine(index)"><Trash2 :size="16"/></button></div></div><label class="checkbox"><input v-model="form.active" type="checkbox">Retsept faol</label></fieldset><p v-if="formError" class="alert error">{{ formError }}</p><button class="button primary full" :disabled="busy || !form.lines.length">{{ busy ? 'Saqlanmoqda…' : 'Retseptni saqlash' }}</button></form></AppModal>
  <AppModal :open="itemModal" title="Yangi mahsulot" @close="!busy && (itemModal=false)"><form @submit.prevent="saveItem"><fieldset :disabled="busy"><label>Mahsulot nomi<input v-model="item.name" required maxlength="100" placeholder="Masalan, Pomidor"></label><div class="form-row"><label>Birlik<select v-model="item.unit"><option>kg</option><option>l</option><option>dona</option></select></label><label>Minimal qoldiq<input v-model="item.minimum" required type="number" min="0" step="0.001"></label></div></fieldset><p class="alert">Mahsulot qo‘shilgach uning boshlang‘ich qoldig‘ini «Ombor va sarf» bo‘limidagi Kirim orqali kiriting.</p><p v-if="formError" class="alert error">{{ formError }}</p><button class="button primary full" :disabled="busy">{{ busy ? 'Saqlanmoqda…' : 'Mahsulotni saqlash' }}</button></form></AppModal>
</template>
