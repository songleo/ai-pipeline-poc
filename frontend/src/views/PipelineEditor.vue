<script setup lang="ts">
import { computed, markRaw, nextTick, onBeforeUnmount, onMounted, ref, shallowRef } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { type Connection, type Edge, type Node, type NodeTypesObject, useVueFlow, VueFlow } from '@vue-flow/core'
import { Background } from '@vue-flow/background'
import { Controls } from '@vue-flow/controls'
import { MiniMap } from '@vue-flow/minimap'
import { api } from '../api/client'
import NodeInspector from '../components/pipeline/NodeInspector.vue'
import NodePalette from '../components/pipeline/NodePalette.vue'
import PipelineCatalog from '../components/pipeline/PipelineCatalog.vue'
import PipelineRunList from '../components/pipeline/PipelineRunList.vue'
import PipelineNode from '../components/nodes/PipelineNode.vue'
import type { NodeTypeDefinition, Pipeline, PipelineCatalogEntry, RunDetail, UnifiedStatus, ValidationIssue, ValidationResult } from '../types/pipeline'
import { beginnerPipeline, examplePipeline } from '../utils/example'
import { clonePipeline, copyCatalogEntry, deletePipeline, loadLocalCatalog, saveToCatalog, templateEntry } from '../utils/pipelineCatalog'
import { appendFlowNode, autoLayoutFlow, clearFlow, connectFlowNodes, flowToPipeline, pipelineToFlow, removeFlowNode, terminalStatuses, validateLocally, type PipelineNodeData } from '../utils/pipeline'

type Page = 'catalog' | 'workspace' | 'history'
type WorkspaceMode = 'edit' | 'run'
type EditorSnapshot = { nodes: Node<PipelineNodeData>[]; edges: Edge[]; pipelineName: string; experimentName: string; tagsText: string; timeoutSeconds: number }

const page = ref<Page>('catalog')
const workspaceMode = ref<WorkspaceMode>('edit')
const historyFilter = ref<string>()
const registry = ref<NodeTypeDefinition[]>([])
const localEntries = ref<PipelineCatalogEntry[]>([])
const runs = ref<RunDetail[]>([])
const flowNodes = shallowRef<Node<PipelineNodeData>[]>([])
const flowEdges = shallowRef<Edge[]>([])
const pipelineName = ref('untitled-pipeline')
const experimentName = ref('新建 Pipeline')
const tagsText = ref('poc')
const timeoutSeconds = ref(300)
const currentVersion = ref<number>()
const selectedId = ref<string>()
const workflowName = ref<string>()
const runDetail = ref<RunDetail>()
const logs = ref('')
const output = ref<Record<string, unknown>>({})
const dialogOpen = ref(false)
const dialogTitle = ref('')
const dialogContent = ref('')
const controlBusy = ref(false)
const paletteCollapsed = ref(false)
const inspectorCollapsed = ref(false)
const canvasFullscreen = ref(false)
const validationOpen = ref(false)
const validationResult = ref<ValidationResult>()
const undoStack = shallowRef<EditorSnapshot[]>([])
const redoStack = shallowRef<EditorSnapshot[]>([])
const savedSignature = ref('')
let lastSnapshot: EditorSnapshot | undefined
let pollTimer: ReturnType<typeof setInterval> | undefined

const nodeTypes = { pipeline: markRaw(PipelineNode) } as unknown as NodeTypesObject
const { fitView, screenToFlowCoordinate } = useVueFlow()
const catalogEntries = computed(() => [
  templateEntry(beginnerPipeline, {
    id: 'template-beginner-training', name: '新手入门：基础模型训练 Pipeline', recommended: true,
    description: '用 4 个基础组件完成拖拽、连线、运行和结果查看。',
    flowSummary: '选择数据集 → 数据预处理 → 模型训练 → 模型评测',
  }),
  templateEntry(examplePipeline, {
    id: 'template-training-qualification', name: '专业示例：训练—评测—准入闭环',
    description: '包含质量门禁、双路训练、模型准入与部署交接的进阶参考。',
    flowSummary: '数据质量 → 双路训练 → 排行榜 → 准入 → 交接',
  }),
  ...localEntries.value,
])
const selectedNode = computed(() => flowNodes.value.find(item => item.id === selectedId.value))
const selectedRuntime = computed(() => runDetail.value?.nodes.find(item => item.nodeId === selectedId.value))
const currentStatus = computed(() => runDetail.value?.status ?? 'IDLE')
const canStop = computed(() => !!workflowName.value && !terminalStatuses.has(currentStatus.value as UnifiedStatus))
const completedCount = computed(() => runDetail.value?.nodes.filter(node => ['SUCCEEDED', 'SKIPPED'].includes(node.status)).length ?? 0)
const artifacts = computed(() => (runDetail.value?.nodes ?? []).flatMap(node => Object.entries(node.outputs).flatMap(([port, value]) => {
  if (!value || typeof value !== 'object' || !('kind' in value)) return []
  const artifact = value as Record<string, unknown>
  const decision = (node.outputs.approvedDecision ?? node.outputs.rejectedDecision) as Record<string, unknown> | undefined
  if (decision?.outcome === 'APPROVED' && port.startsWith('rejected')) return []
  if (decision?.outcome === 'REJECTED' && port.startsWith('approved')) return []
  return [{ nodeId: node.nodeId, port, kind: String(artifact.kind), id: String(artifact.id ?? '-'), value: artifact }]
})))
const leaderboard = computed(() => artifacts.value.find(item => item.kind === 'LeaderboardRef')?.value.entries as Array<Record<string, unknown>> | undefined)
const decisions = computed(() => artifacts.value.filter(item => item.kind === 'GateDecisionRef').filter((item, index, values) => values.findIndex(other => other.id === item.id) === index))
const deploymentRequest = computed(() => artifacts.value.find(item => item.kind === 'DeploymentRequestRef')?.value)
const evaluationResult = computed(() => artifacts.value.find(item => item.kind === 'EvaluationRef')?.value)
const evaluationMetrics = computed(() => evaluationResult.value?.metrics as Record<string, number> | undefined)
const evaluationModel = computed(() => evaluationResult.value?.model as Record<string, unknown> | undefined)
const advancedArtifactKinds = new Set(['DataProfileRef', 'GateDecisionRef', 'CandidateModelRef', 'LeaderboardRef', 'RegisteredModelRef', 'InferenceTestRef', 'DeploymentRequestRef', 'ReportRef'])
const hasAdvancedResults = computed(() => artifacts.value.some(item => advancedArtifactKinds.has(item.kind)))
const admissionDecision = computed(() => decisions.value.find(item => item.value.gate === 'model-admission')?.value)
const admissionChecks = computed(() => Object.entries((admissionDecision.value?.checks as Record<string, boolean> | undefined) ?? {}))
const metricDelta = computed(() => {
  if (!leaderboard.value || leaderboard.value.length < 2) return undefined
  return {
    accuracy: Number(leaderboard.value[0].accuracy) - Number(leaderboard.value[1].accuracy),
    f1: Number(leaderboard.value[0].f1) - Number(leaderboard.value[1].f1),
  }
})
const failedNode = computed(() => runDetail.value?.nodes.find(node => ['FAILED', 'ERROR', 'CANCELLED'].includes(node.status)))
const isDirty = computed(() => page.value === 'workspace' && workspaceMode.value === 'edit' && JSON.stringify(currentPipeline()) !== savedSignature.value)

function currentPipeline() { return flowToPipeline(pipelineName.value, experimentName.value, tagsText.value.split(',').map(item => item.trim()).filter(Boolean), flowNodes.value, flowEdges.value, timeoutSeconds.value, currentVersion.value) }
function cloneSnapshot(value: EditorSnapshot): EditorSnapshot { return JSON.parse(JSON.stringify(value)) as EditorSnapshot }
function editorSnapshot(): EditorSnapshot {
  return cloneSnapshot({ nodes: flowNodes.value, edges: flowEdges.value, pipelineName: pipelineName.value, experimentName: experimentName.value, tagsText: tagsText.value, timeoutSeconds: timeoutSeconds.value })
}
function snapshotSignature(value: EditorSnapshot) { return JSON.stringify(value) }
function resetHistory(markSaved = true) {
  lastSnapshot = editorSnapshot(); undoStack.value = []; redoStack.value = []
  if (markSaved) savedSignature.value = JSON.stringify(currentPipeline())
}
function clearValidationMarks() {
  validationResult.value = undefined
  flowNodes.value = flowNodes.value.map(node => node.data ? { ...node, data: { ...node.data, validationError: false } } : node)
}
function recordHistory() {
  clearValidationMarks()
  const current = editorSnapshot()
  if (lastSnapshot && snapshotSignature(lastSnapshot) !== snapshotSignature(current)) undoStack.value = [...undoStack.value, cloneSnapshot(lastSnapshot)]
  lastSnapshot = current; redoStack.value = []
}
function applySnapshot(snapshot: EditorSnapshot) {
  const value = cloneSnapshot(snapshot)
  flowNodes.value = value.nodes; flowEdges.value = value.edges; pipelineName.value = value.pipelineName
  experimentName.value = value.experimentName; tagsText.value = value.tagsText; timeoutSeconds.value = value.timeoutSeconds
  selectedId.value = undefined; clearValidationMarks(); lastSnapshot = editorSnapshot(); void nextTick(() => fitView({ padding: 0.14, duration: 300 }))
}
function undo() {
  const target = undoStack.value.at(-1); if (!target) return
  undoStack.value = undoStack.value.slice(0, -1); redoStack.value = [...redoStack.value, editorSnapshot()]; applySnapshot(target)
}
function redo() {
  const target = redoStack.value.at(-1); if (!target) return
  redoStack.value = redoStack.value.slice(0, -1); undoStack.value = [...undoStack.value, editorSnapshot()]; applySnapshot(target)
}
async function loadPipeline(pipeline: Pipeline, mode: WorkspaceMode = 'edit') {
  stopPolling()
  const converted = pipelineToFlow(clonePipeline(pipeline), registry.value)
  flowNodes.value = converted.nodes; flowEdges.value = converted.edges
  pipelineName.value = pipeline.metadata.name; experimentName.value = pipeline.metadata.experimentName
  tagsText.value = pipeline.metadata.tags.join(','); timeoutSeconds.value = pipeline.spec.runPolicy.timeoutSeconds
  currentVersion.value = pipeline.metadata.version
  selectedId.value = undefined; workflowName.value = undefined; runDetail.value = undefined; workspaceMode.value = mode; page.value = 'workspace'
  await nextTick(); fitView({ padding: 0.12 }); resetHistory()
}
async function openEntry(entry: PipelineCatalogEntry) { await loadPipeline(entry.pipeline) }
async function copyEntry(entry: PipelineCatalogEntry) { await loadPipeline(copyCatalogEntry(entry)); ElMessage.success('已创建可编辑副本') }
async function newPipeline() {
  const pipeline = clonePipeline(beginnerPipeline)
  pipeline.metadata.name = `pipeline-${Date.now().toString().slice(-5)}`
  pipeline.metadata.experimentName = '新建 Pipeline'
  pipeline.metadata.scenario = 'custom-workflow'
  pipeline.metadata.tags = ['poc']
  pipeline.spec.runPolicy.timeoutSeconds = 300
  pipeline.spec.nodes = []; pipeline.spec.edges = []; pipeline.uiLayout.nodes = {}
  await loadPipeline(pipeline)
}
function showHistory(filter?: string) { historyFilter.value = filter; page.value = 'history'; void refreshRuns() }
async function refreshRuns() { try { runs.value = await api.runs() } catch (error) { ElMessage.warning(`运行记录暂不可用：${String(error)}`) } }
async function openRun(runItem: RunDetail) {
  const entry = catalogEntries.value.find(item => item.pipeline.metadata.name === runItem.pipelineName && (!runItem.definitionVersion || item.version === runItem.definitionVersion))
  const definition = runItem.pipelineDefinition ?? entry?.pipeline
  if (!definition) { ElMessage.warning('这是一条旧运行记录，尚未保存可恢复的定义快照。'); return }
  await loadPipeline(definition, 'run')
  workflowName.value = runItem.workflowName; await poll(); if (!terminalStatuses.has(currentStatus.value as UnifiedStatus)) startPolling()
}
function saveLocal(): Pipeline {
  const pipeline = currentPipeline()
  const result = saveToCatalog(localStorage, localEntries.value, pipeline)
  localEntries.value = result.entries; currentVersion.value = result.entry.version
  localStorage.setItem('pipeline-demo.pipeline', JSON.stringify(result.entry.pipeline))
  savedSignature.value = JSON.stringify(currentPipeline())
  ElMessage.success(`已保存不可变版本 v${result.entry.version}`)
  return result.entry.pipeline
}
async function deleteCatalogPipeline(entry: PipelineCatalogEntry) {
  const count = localEntries.value.filter(item => item.pipeline.metadata.name === entry.pipeline.metadata.name).length
  const confirmed = await ElMessageBox.confirm(`将删除“${entry.name}”的全部 ${count} 个本地版本。运行记录及其定义快照不受影响。`, '删除 Pipeline', { type: 'warning', confirmButtonText: '确认删除' }).catch(() => false)
  if (!confirmed) return
  localEntries.value = deletePipeline(localStorage, localEntries.value, entry.pipeline.metadata.name)
  ElMessage.success('Pipeline 及其本地版本已删除')
}
function onDragOver(event: DragEvent) { if (workspaceMode.value === 'edit') { event.preventDefault(); if (event.dataTransfer) event.dataTransfer.dropEffect = 'move' } }
function onDrop(event: DragEvent) {
  if (workspaceMode.value !== 'edit') return
  event.preventDefault(); const type = event.dataTransfer?.getData('application/vueflow'); const definition = registry.value.find(item => item.type === type)
  if (!definition) return
  const position = screenToFlowCoordinate({ x: event.clientX, y: event.clientY }); const id = `${type}-${Math.random().toString(36).slice(2, 7)}`
  flowNodes.value = appendFlowNode(flowNodes.value, definition, position, id)
  recordHistory()
}
function onConnect(connection: Connection) {
  if (workspaceMode.value !== 'edit') return
  const result = connectFlowNodes(flowNodes.value, flowEdges.value, connection)
  if (result.error) { ElMessage.error(result.error); return }
  flowEdges.value = result.edges
  recordHistory()
}
function refreshSelectedNode() { flowNodes.value = [...flowNodes.value]; recordHistory() }
function onNodeDragStop() { recordHistory() }
function arrangeCanvas() { flowNodes.value = autoLayoutFlow(flowNodes.value, flowEdges.value); recordHistory(); void nextTick(() => fitView({ padding: 0.12, duration: 350 })) }
async function deleteSelectedNode() {
  if (!selectedId.value || workspaceMode.value !== 'edit') return
  const node = selectedNode.value
  const connected = flowEdges.value.filter(edge => edge.source === selectedId.value || edge.target === selectedId.value).length
  const confirmed = await ElMessageBox.confirm(`将删除“${node?.data?.pipelineNode.name ?? selectedId.value}”及 ${connected} 条关联连线。`, '删除节点', { type: 'warning', confirmButtonText: '确认删除' }).catch(() => false)
  if (!confirmed) return
  const result = removeFlowNode(flowNodes.value, flowEdges.value, selectedId.value)
  flowNodes.value = result.nodes; flowEdges.value = result.edges; selectedId.value = undefined; recordHistory(); ElMessage.success('节点及关联连线已删除')
}
async function clearCanvas() {
  if (!flowNodes.value.length || workspaceMode.value !== 'edit') return
  const confirmed = await ElMessageBox.confirm(`将清空 ${flowNodes.value.length} 个节点和 ${flowEdges.value.length} 条连线，此操作可通过“撤销”恢复。`, '清空画布', { type: 'warning', confirmButtonText: '确认清空' }).catch(() => false)
  if (!confirmed) return
  const result = clearFlow(); flowNodes.value = result.nodes; flowEdges.value = result.edges; selectedId.value = undefined; recordHistory(); ElMessage.success('画布已清空，可使用撤销恢复')
}
async function selectNode(event: { node: Node<PipelineNodeData> }) {
  selectedId.value = event.node.id; logs.value = ''; output.value = {}
  if (!workflowName.value) return
  const [logResult, outputResult] = await Promise.allSettled([api.logs(workflowName.value, event.node.id), api.output(workflowName.value, event.node.id)])
  logs.value = logResult.status === 'fulfilled' ? logResult.value.logs : String(logResult.reason)
  output.value = outputResult.status === 'fulfilled' ? outputResult.value.outputs : {}
}
async function validatePipeline() {
  const pipeline = currentPipeline(); const local = validateLocally(pipeline, registry.value)
  if (!local.valid) { applyValidation(local); validationOpen.value = true; ElMessage.error(`发现 ${local.errors.length} 个编排问题`); return false }
  try {
    const result = await api.validate(pipeline)
    applyValidation(result)
    if (!result.valid) { validationOpen.value = true; ElMessage.error(`发现 ${result.errors.length} 个运行前问题`); return false }
    ElMessage.success(result.warnings.length ? `校验通过，${result.warnings.length} 个警告` : '校验通过'); return true
  } catch (error) { ElMessage.error(String(error)); return false }
}
function applyValidation(result: ValidationResult) {
  validationResult.value = result
  const invalid = new Set([...result.errors, ...result.warnings].flatMap(issue => issue.nodeId ? [issue.nodeId] : []))
  flowNodes.value = flowNodes.value.map(node => node.data ? { ...node, data: { ...node.data, validationError: invalid.has(node.id) } } : node)
}
async function focusIssue(issue: ValidationIssue) {
  if (!issue.nodeId) return
  selectedId.value = issue.nodeId; inspectorCollapsed.value = false; validationOpen.value = false
  await nextTick(); fitView({ nodes: [issue.nodeId], padding: 0.7, duration: 350 })
}
async function run() {
  if (!await validatePipeline()) return
  const definition = isDirty.value || !currentVersion.value ? saveLocal() : currentPipeline()
  try { const result = await api.run(definition); workflowName.value = result.workflowName; workspaceMode.value = 'run'; ElMessage.success(`已提交 v${definition.metadata.version}：${result.workflowName}`); await poll(); if (!terminalStatuses.has(currentStatus.value as UnifiedStatus)) startPolling(); await refreshRuns() } catch (error) { ElMessage.error(String(error)) }
}
async function poll() {
  if (!workflowName.value) return
  try {
    runDetail.value = await api.runDetail(workflowName.value)
    const statuses = new Map(runDetail.value.nodes.map(item => [item.nodeId, item.status]))
    flowNodes.value = flowNodes.value.map(node => node.data ? { ...node, data: { ...node.data, status: statuses.get(node.id) ?? 'PENDING' } } : node)
    flowEdges.value = flowEdges.value.map(edge => ({ ...edge, animated: statuses.get(edge.source) === 'RUNNING' }))
    if (failedNode.value && !selectedId.value && ['FAILED', 'ERROR'].includes(runDetail.value.status)) selectedId.value = failedNode.value.nodeId
    if (terminalStatuses.has(runDetail.value.status)) { stopPolling(); void refreshRuns() }
  } catch (error) { stopPolling(); ElMessage.error(String(error)) }
}
function startPolling() { stopPolling(); pollTimer = setInterval(poll, 2000) }
function stopPolling() { if (pollTimer) clearInterval(pollTimer); pollTimer = undefined }
async function stopRun() { if (!workflowName.value) return; try { await api.stop(workflowName.value); await poll(); ElMessage.success('已请求立即停止') } catch (error) { ElMessage.error(String(error)) } }
async function stopSelectedNode() {
  if (!workflowName.value || !selectedId.value) return
  controlBusy.value = true
  try { await api.stopNode(workflowName.value, selectedId.value); await poll(); if (!terminalStatuses.has(currentStatus.value as UnifiedStatus)) startPolling(); ElMessage.success('已请求停止此节点，并行分支不受影响') } catch (error) { ElMessage.error(String(error)) } finally { controlBusy.value = false }
}
async function rerunSelectedNode() {
  if (!workflowName.value || !selectedId.value) return
  if (!await ElMessageBox.confirm('重新运行此节点及其下游；其他已成功并行分支保持不变。', '确认重新运行', { type: 'warning' }).catch(() => false)) return
  controlBusy.value = true
  try { await api.rerunNode(workflowName.value, selectedId.value); await poll(); if (!terminalStatuses.has(currentStatus.value as UnifiedStatus)) startPolling(); ElMessage.success('已从此节点开始重新运行') } catch (error) { ElMessage.error(String(error)) } finally { controlBusy.value = false }
}
function showPipelineJson() { dialogTitle.value = 'Pipeline JSON'; dialogContent.value = JSON.stringify(currentPipeline(), null, 2); dialogOpen.value = true }
async function showWorkflowYaml() { try { const result = await api.compile(currentPipeline()); dialogTitle.value = 'Argo Workflow YAML'; dialogContent.value = result.yaml; dialogOpen.value = true } catch (error) { ElMessage.error(String(error)) } }
function minimapColor(node: Node<PipelineNodeData>) { return ({ RUNNING: '#2563eb', SUCCEEDED: '#16a34a', FAILED: '#dc2626', ERROR: '#dc2626', CANCELLED: '#64748b', PENDING: '#d97706' } as Record<string, string>)[node.data?.status ?? 'IDLE'] ?? '#94a3b8' }

onMounted(async () => {
  try { registry.value = await api.nodeTypes(); localEntries.value = loadLocalCatalog(localStorage); await refreshRuns() }
  catch (error) { ElMessage.error(`初始化失败：${String(error)}`) }
})
onBeforeUnmount(stopPolling)
</script>

<template>
  <div class="app-shell" :class="{ 'canvas-fullscreen': canvasFullscreen }">
    <header v-if="!canvasFullscreen" class="global-header">
      <button class="brand" @click="page = 'catalog'"><span class="brand-mark">P</span><span><strong>Pipeline Studio</strong><small>AI workflow PoC</small></span></button>
      <nav><button :class="{ active: page === 'catalog' }" @click="page = 'catalog'">Pipeline</button><button :class="{ active: page === 'history' }" @click="showHistory()">运行记录</button></nav>
      <div class="header-boundary"><span class="status-dot"></span>可演示原型</div>
    </header>

    <PipelineCatalog v-if="page === 'catalog'" :entries="catalogEntries" :runs="runs" @create="newPipeline" @open="openEntry" @copy="copyEntry" @history="showHistory" @delete="deleteCatalogPipeline" />
    <PipelineRunList v-else-if="page === 'history'" :runs="runs" :filter="historyFilter" @open="openRun" @back="page = 'catalog'" />

    <template v-else>
      <div v-if="!canvasFullscreen" class="workspace-header">
        <div class="workspace-title"><el-button link @click="page = 'catalog'">← Pipeline</el-button><div><strong>{{ experimentName }}</strong><span>{{ pipelineName }}</span></div><el-tag :type="workspaceMode === 'run' ? 'success' : 'info'">{{ workspaceMode === 'run' ? '运行视图' : '编辑视图' }}</el-tag><el-tag v-if="currentVersion" effect="plain">v{{ currentVersion }}</el-tag><el-tag v-if="isDirty" type="warning" effect="plain">未保存</el-tag></div>
        <div class="workspace-actions"><el-button size="small" @click="showPipelineJson">DSL</el-button><el-button size="small" @click="showWorkflowYaml">Workflow</el-button><el-button v-if="workspaceMode === 'edit'" size="small" @click="saveLocal">保存版本</el-button><el-button v-if="workspaceMode === 'edit'" size="small" type="warning" @click="validatePipeline">校验</el-button><el-button v-if="workspaceMode === 'edit'" size="small" type="primary" @click="run">运行</el-button><el-button v-else size="small" @click="workspaceMode = 'edit'">返回编辑</el-button><el-button v-if="workspaceMode === 'run'" size="small" type="danger" :disabled="!canStop" @click="stopRun">停止运行</el-button></div>
      </div>
      <div v-if="workspaceMode === 'edit' && !canvasFullscreen" class="pipeline-meta-bar"><el-input v-model="pipelineName" size="small" aria-label="Pipeline name" @change="recordHistory"><template #prepend>标识</template></el-input><el-input v-model="experimentName" size="small" aria-label="Experiment name" @change="recordHistory"><template #prepend>名称</template></el-input><el-input v-model="tagsText" size="small" aria-label="Run tags" @change="recordHistory"><template #prepend>标签</template></el-input><el-input-number v-model="timeoutSeconds" size="small" :min="1" :max="3600" @change="recordHistory" /><span>秒超时</span></div>
      <div v-else-if="workspaceMode === 'run' && !canvasFullscreen" class="run-status-bar"><div><span class="status-dot" :class="`status-${currentStatus.toLowerCase()}`"></span><strong>{{ currentStatus }}</strong><span>{{ workflowName }}</span><code v-if="runDetail?.definitionDigest">定义 {{ runDetail.definitionDigest }}</code></div><div>{{ completedCount }}/{{ runDetail?.nodes.length ?? flowNodes.length }} 节点完成</div></div>

      <div class="canvas-toolbar">
        <el-button v-if="workspaceMode === 'edit'" size="small" @click="paletteCollapsed = !paletteCollapsed">{{ paletteCollapsed ? '展开组件库' : '收起组件库' }}</el-button>
        <template v-if="workspaceMode === 'edit'"><el-button size="small" :disabled="!undoStack.length" @click="undo">撤销</el-button><el-button size="small" :disabled="!redoStack.length" @click="redo">重做</el-button><el-button size="small" :disabled="!flowNodes.length" @click="arrangeCanvas">自动布局</el-button><el-button size="small" :disabled="!selectedId" @click="deleteSelectedNode">删除节点</el-button><el-button size="small" type="danger" plain :disabled="!flowNodes.length" @click="clearCanvas">清空画布</el-button></template>
        <el-button size="small" :disabled="!flowNodes.length" @click="fitView({ padding: 0.12, duration: 300 })">适应画布</el-button>
        <el-button size="small" @click="inspectorCollapsed = !inspectorCollapsed">{{ inspectorCollapsed ? '展开详情' : '收起详情' }}</el-button>
        <el-button size="small" @click="canvasFullscreen = !canvasFullscreen">{{ canvasFullscreen ? '退出全屏' : '全屏画布' }}</el-button>
        <span v-if="isDirty" class="dirty-hint">● 有未保存修改</span>
      </div>

      <main class="workspace">
        <NodePalette v-if="workspaceMode === 'edit' && !paletteCollapsed" :node-types="registry" />
        <div class="flow-wrap" @dragover="onDragOver" @drop="onDrop">
          <VueFlow v-model:nodes="flowNodes" v-model:edges="flowEdges" :node-types="nodeTypes" fit-view-on-init :delete-key-code="null" :nodes-draggable="workspaceMode === 'edit'" :nodes-connectable="workspaceMode === 'edit'" :elements-selectable="true" @connect="onConnect" @node-click="selectNode" @node-drag-stop="onNodeDragStop" @pane-click="selectedId = undefined">
            <Background pattern-color="#cbd5e1" :gap="20" /><MiniMap :node-color="minimapColor" pannable zoomable /><Controls />
          </VueFlow>
        </div>
        <NodeInspector v-if="selectedNode && !inspectorCollapsed" :data="selectedNode.data" :runtime="selectedRuntime" :logs="logs" :output="output" :control-busy="controlBusy" :readonly="workspaceMode === 'run'" @changed="refreshSelectedNode" @delete-node="deleteSelectedNode" @stop-node="stopSelectedNode" @rerun-node="rerunSelectedNode" />
        <aside v-else-if="!inspectorCollapsed" class="inspector pipeline-inspector">
          <span class="eyebrow">{{ workspaceMode === 'run' ? 'RUN OVERVIEW' : 'PIPELINE' }}</span><h3>{{ workspaceMode === 'run' ? '运行概览' : '编排说明' }}</h3>
          <template v-if="workspaceMode === 'edit'"><p>从左侧拖入节点，通过类型化端口连线。连线标签展示 Artifact 类型或条件分支语义。</p><div class="boundary-card"><strong>可复用边界</strong><span>DSL · Registry · Validator · Adapter Contract</span><small>执行器与产品交互保持解耦</small></div></template>
          <template v-else>
            <el-alert v-if="failedNode" type="error" :closable="false" show-icon><template #title>失败节点：{{ failedNode.nodeId }}</template><div>{{ failedNode.message || '请点击节点查看日志，并可从该节点重跑。' }}</div></el-alert>
            <el-descriptions :column="1" border size="small"><el-descriptions-item label="实验">{{ runDetail?.experimentName }}</el-descriptions-item><el-descriptions-item label="定义版本">{{ runDetail?.definitionVersion ? `v${runDetail.definitionVersion}` : '历史版本' }}</el-descriptions-item><el-descriptions-item label="定义摘要"><code>{{ runDetail?.definitionDigest || '历史运行未记录' }}</code></el-descriptions-item><el-descriptions-item label="状态">{{ currentStatus }}</el-descriptions-item><el-descriptions-item label="开始">{{ runDetail?.startedAt || '-' }}</el-descriptions-item><el-descriptions-item label="结束">{{ runDetail?.finishedAt || '-' }}</el-descriptions-item></el-descriptions>
            <template v-if="evaluationMetrics">
              <h4>模型评测结果</h4>
              <div class="metric-grid"><div><span>Accuracy</span><strong>{{ evaluationMetrics.accuracy }}</strong></div><div><span>F1</span><strong>{{ evaluationMetrics.f1 }}</strong></div><div><span>延迟</span><strong>{{ evaluationMetrics.latencyMs }} ms</strong></div></div>
              <div v-if="evaluationModel" class="model-result"><span>模型输出</span><strong>{{ evaluationModel.algorithm }}</strong><code>{{ evaluationModel.id }}</code></div>
            </template>
            <template v-if="hasAdvancedResults">
              <template v-if="decisions.length"><h4>业务门禁</h4><div v-for="item in decisions" :key="item.id" class="decision-card"><el-tag :type="item.value.outcome === 'APPROVED' ? 'success' : 'danger'">{{ item.value.outcome }}</el-tag><span>{{ item.value.gate }}</span></div></template>
              <div v-if="admissionDecision" class="admission-reason"><strong>模型准入依据</strong><div v-for="([metric, passed]) in admissionChecks" :key="metric"><span>{{ metric }}</span><el-tag size="small" :type="passed ? 'success' : 'danger'">{{ passed ? '通过' : '未通过' }}</el-tag></div></div>
              <template v-if="leaderboard"><h4>模型排行榜</h4><el-table :data="leaderboard" size="small"><el-table-column prop="rank" label="#" width="34" /><el-table-column prop="algorithm" label="模型" min-width="118" /><el-table-column prop="accuracy" label="Acc" width="55" /><el-table-column prop="f1" label="F1" width="55" /><el-table-column prop="latencyMs" label="ms" width="52" /></el-table><div v-if="metricDelta" class="metric-delta">候选相对基线：Accuracy {{ metricDelta.accuracy >= 0 ? '+' : '' }}{{ metricDelta.accuracy.toFixed(4) }}，F1 {{ metricDelta.f1 >= 0 ? '+' : '' }}{{ metricDelta.f1.toFixed(4) }}</div></template>
              <div v-if="deploymentRequest" class="deployment-card"><el-tag type="success">READY</el-tag><strong>推理部署交接已就绪</strong><span>{{ deploymentRequest.id }}</span><small>{{ deploymentRequest.adapterContract }} · {{ deploymentRequest.executionMode }}</small></div>
              <h4>Artifact Lineage</h4><div v-for="item in artifacts" :key="`${item.nodeId}-${item.port}`" class="artifact-card"><span class="artifact-kind">{{ item.kind }}</span><strong>{{ item.id }}</strong><small>{{ item.nodeId }} · {{ item.port }}</small></div>
            </template>
          </template>
        </aside>
      </main>
    </template>
    <el-dialog v-model="dialogOpen" :title="dialogTitle" width="72%"><pre class="json-dialog">{{ dialogContent }}</pre></el-dialog>
    <el-drawer v-model="validationOpen" title="Pipeline 校验结果" size="420px">
      <el-alert v-if="validationResult?.valid" title="校验通过" type="success" :closable="false" show-icon />
      <div v-for="issue in validationResult?.errors" :key="`${issue.code}-${issue.nodeId}-${issue.field}`" class="validation-issue error" @click="focusIssue(issue)"><strong>{{ issue.code }}</strong><span>{{ issue.message }}</span><small>{{ issue.nodeId || 'Pipeline 全局问题' }}<template v-if="issue.nodeId"> · 点击定位</template></small></div>
      <div v-for="issue in validationResult?.warnings" :key="`${issue.code}-${issue.nodeId}-${issue.field}`" class="validation-issue warning" @click="focusIssue(issue)"><strong>{{ issue.code }}</strong><span>{{ issue.message }}</span><small>{{ issue.nodeId || 'Pipeline 全局提示' }}</small></div>
      <el-empty v-if="validationResult && !validationResult.errors.length && !validationResult.warnings.length" description="没有发现问题" />
    </el-drawer>
  </div>
</template>
