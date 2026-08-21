<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import type { RunNode } from '../../types/pipeline'
import type { PipelineNodeData } from '../../utils/pipeline'

const props = defineProps<{ data?: PipelineNodeData; runtime?: RunNode; logs: string; output: Record<string, unknown>; controlBusy: boolean; readonly: boolean }>()
const emit = defineEmits<{ changed: []; stopNode: []; rerunNode: [] }>()
const active = ref('properties')
watch(() => props.data?.pipelineNode.id, () => { active.value = 'properties' })
const title = computed(() => props.data?.pipelineNode.name || props.data?.definition.displayName || 'Pipeline')
</script>

<template>
  <aside class="inspector">
    <template v-if="data">
      <div class="inspector-heading"><span class="eyebrow">{{ data.definition.category }}</span><h3>{{ title }}</h3><p>{{ data.definition.description }}</p></div>
      <el-tabs v-model="active" stretch>
        <el-tab-pane label="属性" name="properties">
          <el-form label-position="top" size="small">
            <el-form-item label="节点名称"><el-input v-model="data.pipelineNode.name" :disabled="readonly" @change="emit('changed')" /></el-form-item>
            <el-form-item v-for="(schema, name) in data.definition.parametersSchema.properties" :key="name" :label="String(name)">
              <el-select v-if="schema.enum" v-model="data.pipelineNode.parameters[name]" :disabled="readonly" @change="emit('changed')"><el-option v-for="option in schema.enum" :key="option" :label="option" :value="option" /></el-select>
              <el-input-number v-else-if="schema.type === 'integer' || schema.type === 'number'" v-model="data.pipelineNode.parameters[name]" :disabled="readonly" :min="schema.minimum" :max="schema.maximum" :step="schema.type === 'integer' ? 1 : 0.01" @change="emit('changed')" />
              <el-input v-else v-model="data.pipelineNode.parameters[name]" :disabled="readonly" @change="emit('changed')" />
            </el-form-item>
          </el-form>
        </el-tab-pane>
        <el-tab-pane label="输入" name="inputs"><div v-for="port in data.definition.inputPorts" :key="port.name" class="port-row"><code>{{ port.name }}</code><span>{{ port.type }}</span><el-tag v-if="port.required" size="small">必填</el-tag></div><el-empty v-if="!data.definition.inputPorts.length" description="无输入端口" :image-size="54" /></el-tab-pane>
        <el-tab-pane label="输出" name="outputs"><div v-for="port in data.definition.outputPorts" :key="port.name" class="port-row"><code>{{ port.name }}</code><span>{{ port.type }}</span></div></el-tab-pane>
        <el-tab-pane label="运行" name="runtime">
          <el-descriptions :column="1" border size="small"><el-descriptions-item label="状态">{{ runtime?.status || data.status }}</el-descriptions-item><el-descriptions-item label="开始">{{ runtime?.startedAt || '-' }}</el-descriptions-item><el-descriptions-item label="结束">{{ runtime?.finishedAt || '-' }}</el-descriptions-item><el-descriptions-item label="重试">{{ runtime?.retryCount ?? 0 }}</el-descriptions-item></el-descriptions>
          <div class="node-actions"><el-button type="danger" size="small" :loading="controlBusy" :disabled="!runtime?.canStop || controlBusy" @click="emit('stopNode')">停止节点</el-button><el-button type="primary" size="small" :loading="controlBusy" :disabled="!runtime?.canRerun || controlBusy" @click="emit('rerunNode')">从此重跑</el-button></div>
          <h4>日志</h4><pre class="log-view">{{ logs || '暂无日志' }}</pre><h4>输出</h4><pre class="log-view">{{ JSON.stringify(output, null, 2) }}</pre>
        </el-tab-pane>
      </el-tabs>
    </template>
    <template v-else><div class="inspector-heading"><span class="eyebrow">PIPELINE</span><h3>选择节点查看详情</h3><p>节点配置、类型化输入输出、运行日志和单节点控制都在这里完成。</p></div><el-empty description="尚未选择节点" :image-size="72" /></template>
  </aside>
</template>
