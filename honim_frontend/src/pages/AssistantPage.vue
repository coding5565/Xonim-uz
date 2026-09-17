<script setup lang="ts">
import { computed, ref } from 'vue'
import { ArrowUpRight, Bot, LoaderCircle, Send, Sparkles, TrendingDown, TrendingUp } from '@lucide/vue'
import { api, money } from '../api'

type Chart = { title:string; labels:string[]; values:string[] }
type Message = { role:'user'|'assistant'; text:string; charts?:Chart[] }
const message=ref(''), sending=ref(false), error=ref('')
const messages=ref<Message[]>([{role:'assistant',text:'Salom! Men Honim AI yordamchisiman. Restorandagi savdo, xarajat, ombor, xodimlar va buyurtmalar bo‘yicha savol bering.'}])
const prompts=['Bugun qanday o‘tdi?','Bugun kechaga nisbatan o‘sdimi?','Oxirgi 7 kun tahlili','Qaysi taomlar ko‘p sotildi?','Omborda nima kamaygan?','Xarajatlar qayerga ketdi?']
const maxValue=(chart:Chart)=>Math.max(1,...chart.values.map(Number))
function formatAnswer(value:string){return value.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/\*\*(.+?)\*\*/g,'<strong>$1</strong>').replace(/\n/g,'<br>')}

async function send(text=message.value){
  const question=text.trim(); if(!question||sending.value)return
  messages.value.push({role:'user',text:question});message.value='';sending.value=true;error.value=''
  try{const result=await api<{answer:string;charts:Chart[]}>('assistant/chat/',{method:'POST',body:JSON.stringify({question})});messages.value.push({role:'assistant',text:result.answer,charts:result.charts})}
  catch(e){error.value=(e as Error).message}
  finally{sending.value=false}
}
const suggested=computed(()=>prompts)
</script>

<template>
  <div class="page-heading assistant-heading"><div><span class="eyebrow">HONIM AI</span><h1>AI yordamchi<span class="heading-dot">.</span></h1><p>Restoraningizdagi raqamlarni so‘rang, aniq tahlil oling.</p></div><span class="assistant-status"><span/>Tizim ma’lumotlari himoyalangan</span></div>
  <section class="assistant-panel panel">
    <header><div class="assistant-avatar"><Bot :size="24"/></div><div><h2>Restoran tahlilchisi</h2><p>Faqat Super Admin uchun</p></div></header>
    <div class="chat-thread" aria-live="polite"><article v-for="(item,index) in messages" :key="index" :class="['chat-message',item.role]"><span v-if="item.role==='assistant'" class="chat-bot"><Bot :size="16"/></span><div><p v-html="formatAnswer(item.text)"/><div v-for="chart in item.charts" :key="chart.title" class="chat-chart"><strong>{{ chart.title }}</strong><div v-for="(label,chartIndex) in chart.labels" :key="label" class="chat-chart-row"><span>{{ label }}</span><div><i :style="{width:`${Number(chart.values[chartIndex])/maxValue(chart)*100}%`}"/></div><b>{{ money(chart.values[chartIndex]) }} so‘m</b></div></div></div></article><article v-if="sending" class="chat-message assistant"><span class="chat-bot"><Bot :size="16"/></span><div class="typing"><LoaderCircle :size="16" class="spin"/>Tahlil qilinmoqda…</div></article></div>
    <p v-if="error" class="alert error">{{ error }}</p>
    <form class="assistant-input" @submit.prevent="send()"><div class="quick-prompts"><span>Tezkor savollar</span><div><button v-for="prompt in suggested" :key="prompt" type="button" :disabled="sending" @click="send(prompt)"><Sparkles :size="13"/>{{ prompt }}</button></div></div><div class="assistant-compose"><textarea v-model="message" rows="2" maxlength="800" placeholder="Masalan: bugun tushum kechagiga nisbatan necha foiz o‘zgardi?"/><button class="button primary" :disabled="!message.trim()||sending" aria-label="Savolni yuborish"><Send :size="18"/>Yuborish</button></div></form>
  </section>
</template>
