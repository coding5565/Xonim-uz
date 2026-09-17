<script setup lang="ts">
import { ref, watch, nextTick, onBeforeUnmount } from 'vue'
import { X } from '@lucide/vue'
const props = defineProps<{open: boolean; title: string}>()
const emit = defineEmits<{close: []}>()
const dialog = ref<HTMLDialogElement>()
watch(() => props.open, async value => { await nextTick(); if (value) dialog.value?.showModal(); else dialog.value?.close() }, {immediate: true})
onBeforeUnmount(() => dialog.value?.close())
</script>
<template><dialog ref="dialog" class="modal" aria-labelledby="modal-title" @cancel.prevent="emit('close')"><header><div><span class="eyebrow">HONIM • BOSHQARUV</span><h2 id="modal-title">{{ title }}</h2></div><button class="icon-button" aria-label="Yopish" @click="emit('close')"><X :size="20"/></button></header><slot/></dialog></template>
