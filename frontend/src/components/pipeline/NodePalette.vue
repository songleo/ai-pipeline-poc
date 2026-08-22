<script setup lang="ts">
import { computed, ref } from 'vue'
import type { NodeTypeDefinition } from '../../types/pipeline'
import type { PaletteCompatibility } from '../../utils/connectionGuide'

const props = defineProps<{ nodeTypes: NodeTypeDefinition[]; compatibility?: Record<string, PaletteCompatibility>; guidanceActive?: boolean }>()
const advancedOpen = ref(false)
const basic = computed(() => props.nodeTypes.filter(item => item.level === 'basic'))
const advancedGroups = computed(() => props.nodeTypes.filter(item => item.level === 'advanced').reduce<Record<string, NodeTypeDefinition[]>>((result, item) => {
  ;(result[item.category] ??= []).push(item)
  return result
}, {}))
const advancedCompatibleCount = computed(() => props.nodeTypes.filter(item => item.level === 'advanced' && props.compatibility?.[item.type]).length)
function itemClass(item: NodeTypeDefinition) {
  const compatible = props.compatibility?.[item.type]
  return { compatible: !!compatible, incompatible: !!props.guidanceActive && !compatible }
}
function compatibilityLabel(item: NodeTypeDefinition) {
  const value = props.compatibility?.[item.type]
  if (!value) return ''
  if (value.downstream && value.upstream) return '可上游 / 下游'
  return value.downstream ? '可作为下游' : '可补充输入'
}
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
      <div v-for="item in basic" :key="item.type" class="palette-item" :class="itemClass(item)" draggable="true" @dragstart="drag($event, item.type)">
        <strong>{{ item.displayName }}</strong><small>{{ item.type }}</small><span v-if="compatibilityLabel(item)" class="compatibility-badge">{{ compatibilityLabel(item) }}</span>
      </div>
    </section>
    <button class="advanced-toggle" type="button" :aria-expanded="advancedOpen" @click="advancedOpen = !advancedOpen">
      <span>高级组件 · {{ nodeTypes.length - basic.length }}<em v-if="guidanceActive && advancedCompatibleCount">（{{ advancedCompatibleCount }} 个兼容）</em></span><span>{{ advancedOpen ? '收起' : '展开' }}</span>
    </button>
    <template v-if="advancedOpen">
      <section v-for="(items, category) in advancedGroups" :key="category">
        <div class="category-title">{{ category }}</div>
        <div v-for="item in items" :key="item.type" class="palette-item advanced" :class="itemClass(item)" draggable="true" @dragstart="drag($event, item.type)">
          <strong>{{ item.displayName }}</strong><small>{{ item.type }}</small><span v-if="compatibilityLabel(item)" class="compatibility-badge">{{ compatibilityLabel(item) }}</span>
        </div>
      </section>
    </template>
  </aside>
</template>
