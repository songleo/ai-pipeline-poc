<script setup lang="ts">
import { Handle, Position } from '@vue-flow/core'
import type { PipelineNodeData } from '../../utils/pipeline'

defineProps<{ data: PipelineNodeData; selected?: boolean }>()
</script>

<template>
  <div class="pipeline-node" :class="[`status-${data.status.toLowerCase()}`, { selected, 'validation-error': data.validationError }]">
    <Handle v-for="(port, index) in data.definition.inputPorts" :id="port.name" :key="`in-${port.name}`" type="target" :position="Position.Left" :style="{ top: `${((index + 1) * 100) / (data.definition.inputPorts.length + 1)}%` }" :title="`${port.name}: ${port.type}`" />
    <div class="node-category">{{ data.definition.category }}</div>
    <strong>{{ data.pipelineNode.name || data.definition.displayName }}</strong>
    <div class="node-type">{{ data.definition.type }} · {{ data.status }}</div>
    <Handle v-for="(port, index) in data.definition.outputPorts" :id="port.name" :key="`out-${port.name}`" type="source" :position="Position.Right" :style="{ top: `${((index + 1) * 100) / (data.definition.outputPorts.length + 1)}%` }" :title="`${port.name}: ${port.type}`" />
  </div>
</template>
