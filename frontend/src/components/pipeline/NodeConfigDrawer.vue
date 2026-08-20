<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import type { RunNode } from '../../types/pipeline'
import type { PipelineNodeData } from '../../utils/pipeline'

const props = defineProps<{ modelValue: boolean; data?: PipelineNodeData; runtime?: RunNode; logs: string; output: Record<string, unknown> }>()
const emit = defineEmits<{ 'update:modelValue': [value: boolean]; changed: [] }>()
const opened = computed({ get: () => props.modelValue, set: value => emit('update:modelValue', value) })
const active = ref('config')
watch(() => props.data?.pipelineNode.id, () => { active.value = 'config' })
</script>

<template>
  <el-drawer v-model="opened" title="节点配置" size="410px">
    <template v-if="data">
      <h3>{{ data.pipelineNode.name || data.definition.displayName }}</h3>
      <p class="muted">{{ data.definition.description }}</p>
      <el-tabs v-model="active">
        <el-tab-pane label="配置" name="config">
          <el-form label-position="top">
            <el-form-item label="节点名称"><el-input v-model="data.pipelineNode.name" @change="emit('changed')" /></el-form-item>
            <el-form-item v-for="(schema, name) in data.definition.parametersSchema.properties" :key="name" :label="String(name)">
              <el-select v-if="schema.enum" v-model="data.pipelineNode.parameters[name]" @change="emit('changed')"><el-option v-for="option in schema.enum" :key="option" :label="option" :value="option" /></el-select>
              <el-input-number v-else-if="schema.type === 'integer' || schema.type === 'number'" v-model="data.pipelineNode.parameters[name]" :min="schema.minimum" :max="schema.maximum" :step="schema.type === 'integer' ? 1 : 0.01" @change="emit('changed')" />
              <el-input v-else v-model="data.pipelineNode.parameters[name]" @change="emit('changed')" />
            </el-form-item>
          </el-form>
          <h4>输入端口</h4><div v-for="port in data.definition.inputPorts" :key="port.name"><code>{{ port.name }}</code> · {{ port.type }} <span v-if="port.required">必填</span></div>
          <h4>输出端口</h4><div v-for="port in data.definition.outputPorts" :key="port.name"><code>{{ port.name }}</code> · {{ port.type }}</div>
        </el-tab-pane>
        <el-tab-pane label="运行" name="runtime">
          <el-descriptions :column="1" border>
            <el-descriptions-item label="状态">{{ runtime?.status || data.status }}</el-descriptions-item>
            <el-descriptions-item label="开始">{{ runtime?.startedAt || '-' }}</el-descriptions-item>
            <el-descriptions-item label="结束">{{ runtime?.finishedAt || '-' }}</el-descriptions-item>
            <el-descriptions-item label="重试">{{ runtime?.retryCount ?? 0 }}</el-descriptions-item>
          </el-descriptions>
          <h4>日志</h4><pre class="log-view">{{ logs || '暂无日志' }}</pre>
          <h4>输出 JSON</h4><pre class="log-view">{{ JSON.stringify(output, null, 2) }}</pre>
        </el-tab-pane>
      </el-tabs>
    </template>
  </el-drawer>
</template>
