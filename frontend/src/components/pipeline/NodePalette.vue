<script setup lang="ts">
import { computed } from 'vue'
import type { NodeTypeDefinition } from '../../types/pipeline'

const props = defineProps<{ nodeTypes: NodeTypeDefinition[] }>()
const groups = computed(() => props.nodeTypes.reduce<Record<string, NodeTypeDefinition[]>>((result, item) => {
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
    <h3>节点</h3>
    <section v-for="(items, category) in groups" :key="category">
      <div class="category-title">{{ category }}</div>
      <div v-for="item in items" :key="item.type" class="palette-item" draggable="true" @dragstart="drag($event, item.type)">
        <strong>{{ item.displayName }}</strong><small>{{ item.type }}</small>
      </div>
    </section>
  </aside>
</template>
