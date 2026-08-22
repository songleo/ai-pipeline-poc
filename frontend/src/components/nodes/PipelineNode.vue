<script setup lang="ts">
import { Handle, Position } from '@vue-flow/core'
import { inject } from 'vue'
import type { PortDefinition } from '../../types/pipeline'
import { connectionHintKey } from '../../utils/connectionGuide'
import type { PipelineNodeData } from '../../utils/pipeline'

defineProps<{ data: PipelineNodeData; selected?: boolean }>()
const connectionHint = inject(connectionHintKey)
function handleClass(port: PortDefinition, handleType: 'source' | 'target') {
  const hint = connectionHint?.value
  if (!hint || hint.handleType === handleType) return undefined
  return port.type === hint.artifactType ? 'connection-compatible' : 'connection-incompatible'
}
function handleTitle(port: PortDefinition, handleType: 'source' | 'target') {
  const hint = connectionHint?.value
  if (!hint || hint.handleType === handleType) return `${port.name}: ${port.type}`
  return port.type === hint.artifactType
    ? `可连接：${port.name} · ${port.type}`
    : `不可连接：当前为 ${hint.artifactType}，此端口需要 ${port.type}`
}
</script>

<template>
  <div class="pipeline-node" :class="[`status-${data.status.toLowerCase()}`, { selected, 'validation-error': data.validationError }]">
    <Handle v-for="(port, index) in data.definition.inputPorts" :id="port.name" :key="`in-${port.name}`" type="target" :position="Position.Left" :class="handleClass(port, 'target')" :style="{ top: `${((index + 1) * 100) / (data.definition.inputPorts.length + 1)}%` }" :title="handleTitle(port, 'target')" />
    <div class="node-category">{{ data.definition.category }}</div>
    <strong>{{ data.pipelineNode.name || data.definition.displayName }}</strong>
    <div class="node-type">{{ data.definition.type }} · {{ data.status }}</div>
    <Handle v-for="(port, index) in data.definition.outputPorts" :id="port.name" :key="`out-${port.name}`" type="source" :position="Position.Right" :class="handleClass(port, 'source')" :style="{ top: `${((index + 1) * 100) / (data.definition.outputPorts.length + 1)}%` }" :title="handleTitle(port, 'source')" />
  </div>
</template>
