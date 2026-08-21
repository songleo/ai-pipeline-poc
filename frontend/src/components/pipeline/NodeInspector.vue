<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import type { ParameterProperty, ParameterUi, RunNode } from '../../types/pipeline'
import type { PipelineNodeData } from '../../utils/pipeline'

const props = defineProps<{ data?: PipelineNodeData; runtime?: RunNode; logs: string; output: Record<string, unknown>; controlBusy: boolean; readonly: boolean }>()
const emit = defineEmits<{ changed: []; stopNode: []; rerunNode: []; deleteNode: [] }>()
const active = ref('properties')
watch(() => props.data?.pipelineNode.id, () => { active.value = 'properties' })
const title = computed(() => props.data?.pipelineNode.name || props.data?.definition.displayName || 'Pipeline')
const groups = computed(() => {
  if (!props.data) return []
  const definition = props.data.definition
  const order = definition.uiSchema.order ?? Object.keys(definition.parametersSchema.properties)
  const result: Array<{ name: string; simulation: boolean; fields: Array<{ name: string; schema: ParameterProperty; ui: ParameterUi }> }> = []
  for (const name of order) {
    const schema = definition.parametersSchema.properties[name]
    if (!schema) continue
    const ui = definition.uiSchema.fields?.[name] ?? { label: name, group: '其他' }
    let group = result.find(item => item.name === ui.group)
    if (!group) { group = { name: ui.group, simulation: !!ui.simulation, fields: [] }; result.push(group) }
    group.simulation ||= !!ui.simulation
    group.fields.push({ name, schema, ui })
  }
  return result
})
</script>

<template>
  <aside class="inspector">
    <template v-if="data">
      <div class="inspector-heading"><span class="eyebrow">{{ data.definition.category }}</span><h3>{{ title }}</h3><p>{{ data.definition.description }}</p></div>
      <el-tabs v-model="active" stretch>
        <el-tab-pane label="属性" name="properties">
          <el-form label-position="top" size="small">
            <el-form-item label="节点名称"><el-input v-model="data.pipelineNode.name" :disabled="readonly" @change="emit('changed')" /></el-form-item>
            <section v-for="group in groups" :key="group.name" class="parameter-group" :class="{ 'simulation-group': group.simulation }">
              <div class="parameter-group-title"><strong>{{ group.name }}</strong><el-tag v-if="group.simulation" size="small" type="warning">仅 PoC 模拟</el-tag></div>
              <p v-if="group.simulation" class="parameter-group-help">这些值用于生成可演示结果；正式接入后由真实任务输出，不能人工指定。</p>
              <el-form-item v-for="field in group.fields" :key="field.name" :required="data.definition.parametersSchema.required?.includes(field.name)">
                <template #label><span>{{ field.ui.label }}<small v-if="field.ui.unit">（{{ field.ui.unit }}）</small></span></template>
                <el-select v-if="field.schema.enum" v-model="data.pipelineNode.parameters[field.name]" :disabled="readonly" @change="emit('changed')"><el-option v-for="option in field.schema.enum" :key="option" :label="option" :value="option" /></el-select>
                <el-input-number v-else-if="field.schema.type === 'integer' || field.schema.type === 'number'" v-model="data.pipelineNode.parameters[field.name]" :disabled="readonly" :min="field.schema.minimum" :max="field.schema.maximum" :step="field.schema.type === 'integer' ? 1 : 0.01" @change="emit('changed')" />
                <el-input v-else v-model="data.pipelineNode.parameters[field.name]" :disabled="readonly" @change="emit('changed')" />
                <div v-if="field.ui.help" class="field-help">{{ field.ui.help }}</div>
              </el-form-item>
            </section>
          </el-form>
          <el-button v-if="!readonly" class="delete-node-button" type="danger" plain @click="emit('deleteNode')">删除此节点</el-button>
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
