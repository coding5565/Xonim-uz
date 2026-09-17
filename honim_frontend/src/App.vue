<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ArrowUpRight, BarChart3, Bot, ChefHat, ChevronRight, Command, LayoutDashboard, LogOut, Menu, Moon, Package, PanelLeftClose, ReceiptText, Settings2, ShoppingBag, Sun, Users, UtensilsCrossed, Wallet } from '@lucide/vue'
import { api, session } from './api'

const route=useRoute(), router=useRouter(), collapsed=ref(false), error=ref(''), darkMode=ref(localStorage.getItem('honim-theme')==='dark')
const publicPage=computed(()=>route.meta.public)
const nav=computed(()=>[
  {path:'/',name:'Umumiy holat',icon:LayoutDashboard,visible:session.user?.role==='owner'},
  {path:'/pos',name:'Kassa',icon:ShoppingBag,visible:['owner','admin','cashier'].includes(session.user?.role||'')},
  {path:'/orders',name:'Buyurtmalar',icon:ReceiptText,visible:['owner','admin','cashier'].includes(session.user?.role||'')},
  {path:'/reports',name:'Savdo hisobotlari',icon:BarChart3,visible:['owner','admin'].includes(session.user?.role||'')},
  {path:'/assistant',name:'AI yordamchi',icon:Bot,visible:session.user?.role==='owner'},
  {path:'/kitchen',name:'Oshxona',icon:ChefHat,visible:['owner','admin','kitchen'].includes(session.user?.role||'')},
  {path:'/catalog',name:'Menyu boshqaruvi',icon:UtensilsCrossed,visible:['owner','admin'].includes(session.user?.role||'')},
  {path:'/expenses',name:'Xarajatlar',icon:Wallet,visible:['owner','admin'].includes(session.user?.role||'')},
  {path:'/inventory',name:'Ombor va sarf',icon:Package,visible:['owner','admin'].includes(session.user?.role||'')},
  {path:'/recipes',name:'Retsept va foyda',icon:BarChart3,visible:['owner','admin'].includes(session.user?.role||'')},
  {path:'/staff',name:'Xodimlar',icon:Users,visible:session.user?.role==='owner'},
].filter(item=>item.visible))
const title=computed(()=>nav.value.find(item=>item.path===route.path)?.name||'Sozlamalar')
const roleName=computed(()=>session.user?.role==='owner'?'Superadmin':session.user?.role==='admin'?'Admin':session.user?.role==='kitchen'?'Oshxona':'Kassir')
function closeMobileNav(){ if(window.matchMedia('(max-width: 950px)').matches) collapsed.value=false }
function applyTheme(){ document.documentElement.classList.toggle('theme-dark',darkMode.value); localStorage.setItem('honim-theme',darkMode.value?'dark':'light') }
function toggleTheme(){ darkMode.value=!darkMode.value }
onMounted(applyTheme); watch(darkMode,applyTheme)
async function logout(){try{await api('auth/logout/',{method:'POST'});session.user=null;session.ready=false;await router.push('/login')}catch(e){error.value=(e as Error).message}}
</script>

<template>
  <RouterView v-if="publicPage"/>
  <div v-else class="app-shell" :class="{collapsed}">
    <button v-if="collapsed" class="sidebar-backdrop" aria-label="Menyuni yopish" @click="closeMobileNav"/><aside class="sidebar">
      <RouterLink to="/" class="brand"><span class="brand-mark">h<span>•</span></span><span class="brand-text">honim<span>RESTAURANT WORKSPACE</span></span></RouterLink>
      <div class="workspace"><span class="workspace-avatar">H</span><div><strong>Honim Restaurant</strong><small>Asosiy restoran</small></div><ChevronRight :size="14"/></div>
      <p class="nav-caption">ISH MAYDONI</p>
      <nav><RouterLink v-for="item in nav" :key="item.path" :to="item.path" :class="{active:route.path===item.path}" @click="closeMobileNav"><component :is="item.icon" :size="20"/><span>{{ item.name }}</span><span v-if="item.path==='/pos'" class="nav-badge">POS</span><span v-if="item.path==='/kitchen'" class="nav-badge">KDS</span></RouterLink></nav>
      <div class="sidebar-bottom">
        <div class="menu-promo"><span class="promo-icon"><UtensilsCrossed :size="20"/></span><strong>Mehmonlar uchun menyu</strong><p>Taomlaringiz bir skan masofada.</p><RouterLink to="/menu" target="_blank" @click="closeMobileNav">Menyuni ochish <ArrowUpRight :size="16"/></RouterLink></div>
        <RouterLink v-if="session.user?.role!=='kitchen'" to="/settings" class="settings-link" @click="closeMobileNav"><Settings2 :size="19"/>Sozlamalar va QR</RouterLink>
        <button class="profile" @click="logout" title="Tizimdan chiqish"><span class="avatar">{{ session.user?.name.charAt(0) }}</span><span><strong>{{ session.user?.name }}</strong><small>{{ roleName }}</small></span><LogOut :size="17"/></button>
      </div>
    </aside>
    <div class="main-shell">
      <header class="topbar"><div class="breadcrumb"><button class="icon-button" aria-label="Menyuni ochish/yopish" @click="collapsed=!collapsed"><Menu v-if="collapsed" :size="19"/><PanelLeftClose v-else :size="19"/></button><span class="breadcrumb-home">Ish maydoni</span><ChevronRight :size="14"/><strong>{{ title }}</strong></div><div class="topbar-right"><span class="local-badge"><span/>Localhost · Sinov versiyasi</span><span class="top-date">{{ new Intl.DateTimeFormat('uz-UZ',{day:'numeric',month:'long'}).format(new Date()) }}</span><button class="theme-toggle" :aria-label="darkMode ? 'Yorug‘ rejimga o‘tish' : 'Tungi rejimga o‘tish'" :title="darkMode ? 'Yorug‘ rejim' : 'Tungi rejim'" @click="toggleTheme"><Sun v-if="darkMode" :size="17"/><Moon v-else :size="17"/></button><span class="top-avatar"><Command :size="18"/></span></div></header>
      <p v-if="error" class="alert error">{{ error }}</p><main class="main-content"><RouterView/></main><footer class="app-footer">HONIM WORKSPACE <span>Mahalliy sinov • ma’lumotlar ushbu kompyuterda saqlanadi</span></footer>
    </div>
  </div>
</template>
