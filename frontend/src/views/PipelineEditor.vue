<script setup lang="ts">
import { computed, markRaw, nextTick, onBeforeUnmount, onMounted, ref, shallowRef } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { type Connection, type Edge, type Node, type NodeTypesObject, useVueFlow, VueFlow } from '@vue-flow/core'
import { Background } from '@vue-flow/background'
import { Controls } from '@vue-flow/controls'
import { MiniMap } from '@vue-flow/minimap'
import { api } from '../api/client'
import NodeConfigDrawer from '../components/pipeline/NodeConfigDrawer.vue'
import NodePalette from '../components/pipeline/NodePalette.vue'
import PipelineNode from '../components/nodes/PipelineNode.vue'
import type { NodeTypeDefinition, RunDetail, UnifiedStatus } from '../types/pipeline'
import { examplePipeline } from '../utils/example'
import { appendFlowNode, connectFlowNodes, flowToPipeline, pipelineToFlow, terminalStatuses, validateLocally, type PipelineNodeData } from '../utils/pipeline'

const registry = ref<NodeTypeDefinition[]>([])
const flowNodes = shallowRef<Node<PipelineNodeData>[]>([])
const flowEdges = shallowRef<Edge[]>([])
const pipelineName = ref('untitled-pipeline')
const timeoutSeconds = ref(300)
const selectedId = ref<string>()
const drawerOpen = ref(false)
const workflowName = ref<string>()
const runDetail = ref<RunDetail>()
const logs = ref('')
const output = ref<Record<string, unknown>>({})
const dialogOpen = ref(false)
const dialogTitle = ref('')
const dialogContent = ref('')
const controlBusy = ref(false)
let pollTimer: ReturnType<typeof setInterval> | undefined

const nodeTypes = { pipeline: markRaw(PipelineNode) } as unknown as NodeTypesObject
const { fitView, screenToFlowCoordinate } = useVueFlow()
const selectedNode = computed(() => flowNodes.value.find(item => item.id === selectedId.value))
const selectedRuntime = computed(() => runDetail.value?.nodes.find(item => item.nodeId === selectedId.value))
const currentStatus = computed(() => runDetail.value?.status ?? 'IDLE')
const canStop = computed(() => !!workflowName.value && !terminalStatuses.has(currentStatus.value as UnifiedStatus))

function currentPipeline() { return flowToPipeline(pipelineName.value, flowNodes.value, flowEdges.value, timeoutSeconds.value) }
function newPipeline() {
  stopPolling(); flowNodes.value = []; flowEdges.value = []; pipelineName.value = 'untitled-pipeline'; workflowName.value = undefined; runDetail.value = undefined
}
async function loadExample() {
  const converted = pipelineToFlow(structuredClone(examplePipeline), registry.value)
  flowNodes.value = converted.nodes; flowEdges.value = converted.edges; pipelineName.value = examplePipeline.metadata.name; timeoutSeconds.value = examplePipeline.spec.runPolicy.timeoutSeconds
  workflowName.value = undefined; runDetail.value = undefined; await nextTick(); fitView({ padding: 0.15 })
}
function saveLocal() { localStorage.setItem('pipeline-demo.pipeline', JSON.stringify(currentPipeline())); ElMessage.success('已保存到浏览器') }
function onDragOver(event: DragEvent) { event.preventDefault(); if (event.dataTransfer) event.dataTransfer.dropEffect = 'move' }
function onDrop(event: DragEvent) {
  event.preventDefault(); const type = event.dataTransfer?.getData('application/vueflow'); const definition = registry.value.find(item => item.type === type)
  if (!definition) return
  const position = screenToFlowCoordinate({ x: event.clientX, y: event.clientY }); const suffix = Math.random().toString(36).slice(2, 7); const id = `${type}-${suffix}`
  flowNodes.value = appendFlowNode(flowNodes.value, definition, position, id)
}
function onConnect(connection: Connection) {
  const result = connectFlowNodes(flowNodes.value, flowEdges.value, connection)
  if (result.error) { ElMessage.error(result.error); return }
  flowEdges.value = result.edges
}
function refreshSelectedNode() { flowNodes.value = [...flowNodes.value] }
async function selectNode(event: { node: Node<PipelineNodeData> }) {
  selectedId.value = event.node.id; drawerOpen.value = true; logs.value = ''; output.value = {}
  if (!workflowName.value) return
  const [logResult, outputResult] = await Promise.allSettled([api.logs(workflowName.value, event.node.id), api.output(workflowName.value, event.node.id)])
  logs.value = logResult.status === 'fulfilled' ? logResult.value.logs : String(logResult.reason)
  output.value = outputResult.status === 'fulfilled' ? outputResult.value.outputs : {}
}
async function validatePipeline() {
  const pipeline = currentPipeline(); const local = validateLocally(pipeline, registry.value)
  if (!local.valid) { await showIssues('前端校验失败', local.errors.map(item => item.message)); return false }
  try {
    const result = await api.validate(pipeline)
    if (!result.valid) { await showIssues('后端校验失败', result.errors.map(item => `${item.nodeId ?? 'pipeline'}: ${item.message}`)); return false }
    ElMessage.success(result.warnings.length ? `校验通过，${result.warnings.length} 个警告` : '校验通过'); return true
  } catch (error) { ElMessage.error(String(error)); return false }
}
async function showIssues(title: string, issues: string[]) { await ElMessageBox.alert(issues.join('\n'), title, { type: 'error' }).catch(() => undefined) }
async function run() {
  if (!await validatePipeline()) return
  try { const result = await api.run(currentPipeline()); workflowName.value = result.workflowName; ElMessage.success(`已提交 ${result.workflowName}`); await poll(); startPolling() } catch (error) { ElMessage.error(String(error)) }
}
async function poll() {
  if (!workflowName.value) return
  try {
    runDetail.value = await api.runDetail(workflowName.value)
    const statuses = new Map(runDetail.value.nodes.map(item => [item.nodeId, item.status]))
    flowNodes.value = flowNodes.value.map(node => node.data ? { ...node, data: { ...node.data, status: statuses.get(node.id) ?? 'PENDING' } } : node)
    flowEdges.value = flowEdges.value.map(edge => ({ ...edge, animated: statuses.get(edge.source) === 'RUNNING' }))
    if (terminalStatuses.has(runDetail.value.status)) stopPolling()
  } catch (error) { stopPolling(); ElMessage.error(String(error)) }
}
function startPolling() { stopPolling(); pollTimer = setInterval(poll, 2000) }
function stopPolling() { if (pollTimer) clearInterval(pollTimer); pollTimer = undefined }
async function stopRun() { if (!workflowName.value) return; try { await api.stop(workflowName.value); await poll(); ElMessage.success('已请求立即停止') } catch (error) { ElMessage.error(String(error)) } }
async function stopSelectedNode() {
  if (!workflowName.value || !selectedId.value) return
  controlBusy.value = true
  try {
    await api.stopNode(workflowName.value, selectedId.value)
    await poll(); startPolling(); ElMessage.success('已请求停止此节点，并行分支不会受影响')
  } catch (error) { ElMessage.error(String(error)) } finally { controlBusy.value = false }
}
async function rerunSelectedNode() {
  if (!workflowName.value || !selectedId.value) return
  const confirmed = await ElMessageBox.confirm('将重新运行此节点及其所有下游节点；其他已成功的并行分支保持不变。', '确认重新运行', { type: 'warning' }).catch(() => false)
  if (!confirmed) return
  controlBusy.value = true
  try {
    await api.rerunNode(workflowName.value, selectedId.value)
    await poll(); startPolling(); ElMessage.success('已从此节点开始重新运行')
  } catch (error) { ElMessage.error(String(error)) } finally { controlBusy.value = false }
}
function showPipelineJson() { dialogTitle.value = 'Pipeline JSON'; dialogContent.value = JSON.stringify(currentPipeline(), null, 2); dialogOpen.value = true }
async function showWorkflowYaml() { try { const result = await api.compile(currentPipeline()); dialogTitle.value = 'Argo Workflow YAML'; dialogContent.value = result.yaml; dialogOpen.value = true } catch (error) { ElMessage.error(String(error)) } }
function minimapColor(node: Node<PipelineNodeData>) { return ({ RUNNING: '#409eff', SUCCEEDED: '#67c23a', FAILED: '#f56c6c', ERROR: '#f56c6c', CANCELLED: '#606266', PENDING: '#e6a23c' } as Record<string, string>)[node.data?.status ?? 'IDLE'] ?? '#909399' }

onMounted(async () => {
  try {
    registry.value = await api.nodeTypes()
    const saved = localStorage.getItem('pipeline-demo.pipeline')
    if (saved) { const pipeline = JSON.parse(saved); const converted = pipelineToFlow(pipeline, registry.value); flowNodes.value = converted.nodes; flowEdges.value = converted.edges; pipelineName.value = pipeline.metadata.name }
    else await loadExample()
  } catch (error) { ElMessage.error(`Node Registry 加载失败：${String(error)}`) }
})
onBeforeUnmount(stopPolling)
</script>

<template>
  <div class="app-shell">
    <header class="toolbar">
      <strong>pipeline-demo</strong><el-input v-model="pipelineName" size="small" style="width:210px" aria-label="Pipeline name" />
      <el-button size="small" @click="newPipeline">新建</el-button><el-button size="small" @click="loadExample">加载示例</el-button><el-button size="small" @click="saveLocal">保存本地</el-button>
      <el-button size="small" type="warning" @click="validatePipeline">校验</el-button><el-button size="small" type="primary" @click="run">运行</el-button><el-button size="small" type="danger" :disabled="!canStop" @click="stopRun">停止</el-button>
      <el-button size="small" @click="showPipelineJson">Pipeline JSON</el-button><el-button size="small" @click="showWorkflowYaml">Workflow YAML</el-button>
      <el-tag>{{ currentStatus }}</el-tag><span v-if="workflowName" class="workflow-name">{{ workflowName }}</span>
    </header>
    <main class="workspace">
      <NodePalette :node-types="registry" />
      <div class="flow-wrap" @dragover="onDragOver" @drop="onDrop">
        <VueFlow v-model:nodes="flowNodes" v-model:edges="flowEdges" :node-types="nodeTypes" fit-view-on-init delete-key-code="Delete" @connect="onConnect" @node-click="selectNode">
          <Background pattern-color="#d7dce5" :gap="18" /><MiniMap :node-color="minimapColor" pannable zoomable /><Controls />
        </VueFlow>
      </div>
    </main>
    <NodeConfigDrawer v-model="drawerOpen" :data="selectedNode?.data" :runtime="selectedRuntime" :logs="logs" :output="output" :control-busy="controlBusy" @changed="refreshSelectedNode" @stop-node="stopSelectedNode" @rerun-node="rerunSelectedNode" />
    <el-dialog v-model="dialogOpen" :title="dialogTitle" width="72%"><pre class="json-dialog">{{ dialogContent }}</pre></el-dialog>
  </div>
</template>

