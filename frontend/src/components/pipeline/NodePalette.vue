<script setup lang="ts">
import { computed, ref } from 'vue'
import type { NodeTypeDefinition } from '../../types/pipeline'

const props = defineProps<{ nodeTypes: NodeTypeDefinition[] }>()
const advancedOpen = ref(false)
const basic = computed(() => props.nodeTypes.filter(item => item.level === 'basic'))
const advancedGroups = computed(() => props.nodeTypes.filter(item => item.level === 'advanced').reduce<Record<string, NodeTypeDefinition[]>>((result, item) => {
  ;(result[item.category] ??= []).push(item)
  return result
}, {}))
function drag(event: DragEvent, type: string) {
  event.dataTransfer?.setData('application/vueflow', type)
  if (event.dataTransfer) event.dataTransfer.effectAllowed = 'move'
}
</script>

<template>
  <aside class="palette">
    <h3>组件库</h3>
    <p class="palette-hint">拖拽基础组件即可完成首次编排</p>
    <section>
      <div class="category-title">基础组件 · {{ basic.length }}</div>
      <div v-for="item in basic" :key="item.type" class="palette-item" draggable="true" @dragstart="drag($event, item.type)">
        <strong>{{ item.displayName }}</strong><small>{{ item.type }}</small>
      </div>
    </section>
    <button class="advanced-toggle" type="button" :aria-expanded="advancedOpen" @click="advancedOpen = !advancedOpen">
      <span>高级组件 · {{ nodeTypes.length - basic.length }}</span><span>{{ advancedOpen ? '收起' : '展开' }}</span>
    </button>
    <template v-if="advancedOpen">
      <section v-for="(items, category) in advancedGroups" :key="category">
        <div class="category-title">{{ category }}</div>
        <div v-for="item in items" :key="item.type" class="palette-item advanced" draggable="true" @dragstart="drag($event, item.type)">
          <strong>{{ item.displayName }}</strong><small>{{ item.type }}</small>
        </div>
      </section>
    </template>
  </aside>
</template>
