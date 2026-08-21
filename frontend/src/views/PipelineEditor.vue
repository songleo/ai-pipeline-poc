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
import type { NodeTypeDefinition, Pipeline, PipelineCatalogEntry, RunDetail, UnifiedStatus } from '../types/pipeline'
import { examplePipeline } from '../utils/example'
import { copyCatalogEntry, loadLocalCatalog, saveToCatalog, templateEntry } from '../utils/pipelineCatalog'
import { appendFlowNode, connectFlowNodes, flowToPipeline, pipelineToFlow, terminalStatuses, validateLocally, type PipelineNodeData } from '../utils/pipeline'

type Page = 'catalog' | 'workspace' | 'history'
type WorkspaceMode = 'edit' | 'run'

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
const selectedId = ref<string>()
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
const catalogEntries = computed(() => [templateEntry(examplePipeline), ...localEntries.value])
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

function currentPipeline() { return flowToPipeline(pipelineName.value, experimentName.value, tagsText.value.split(',').map(item => item.trim()).filter(Boolean), flowNodes.value, flowEdges.value, timeoutSeconds.value) }
async function loadPipeline(pipeline: Pipeline, mode: WorkspaceMode = 'edit') {
  stopPolling()
  const converted = pipelineToFlow(structuredClone(pipeline), registry.value)
  flowNodes.value = converted.nodes; flowEdges.value = converted.edges
  pipelineName.value = pipeline.metadata.name; experimentName.value = pipeline.metadata.experimentName
  tagsText.value = pipeline.metadata.tags.join(','); timeoutSeconds.value = pipeline.spec.runPolicy.timeoutSeconds
  selectedId.value = undefined; workflowName.value = undefined; runDetail.value = undefined; workspaceMode.value = mode; page.value = 'workspace'
  await nextTick(); fitView({ padding: 0.12 })
}
async function openEntry(entry: PipelineCatalogEntry) { await loadPipeline(entry.pipeline) }
async function copyEntry(entry: PipelineCatalogEntry) { await loadPipeline(copyCatalogEntry(entry)); ElMessage.success('已创建可编辑副本') }
async function newPipeline() {
  const pipeline = structuredClone(examplePipeline)
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
  const entry = catalogEntries.value.find(item => item.pipeline.metadata.name === runItem.pipelineName)
  if (!entry) { ElMessage.warning('该历史运行没有保留对应的浏览器 Pipeline 定义，无法可靠还原 DAG。'); return }
  await loadPipeline(entry.pipeline, 'run')
  workflowName.value = runItem.workflowName; await poll(); if (!terminalStatuses.has(currentStatus.value as UnifiedStatus)) startPolling()
}
function saveLocal() {
  const pipeline = currentPipeline()
  localEntries.value = saveToCatalog(localStorage, localEntries.value, pipeline)
  localStorage.setItem('pipeline-demo.pipeline', JSON.stringify(pipeline))
  ElMessage.success(`已保存为浏览器原型版本 v${localEntries.value.find(item => item.pipeline.metadata.name === pipeline.metadata.name)?.version}`)
}
function onDragOver(event: DragEvent) { if (workspaceMode.value === 'edit') { event.preventDefault(); if (event.dataTransfer) event.dataTransfer.dropEffect = 'move' } }
function onDrop(event: DragEvent) {
  if (workspaceMode.value !== 'edit') return
  event.preventDefault(); const type = event.dataTransfer?.getData('application/vueflow'); const definition = registry.value.find(item => item.type === type)
  if (!definition) return
  const position = screenToFlowCoordinate({ x: event.clientX, y: event.clientY }); const id = `${type}-${Math.random().toString(36).slice(2, 7)}`
  flowNodes.value = appendFlowNode(flowNodes.value, definition, position, id)
}
function onConnect(connection: Connection) {
  if (workspaceMode.value !== 'edit') return
  const result = connectFlowNodes(flowNodes.value, flowEdges.value, connection)
  if (result.error) { ElMessage.error(result.error); return }
  flowEdges.value = result.edges
}
function refreshSelectedNode() { flowNodes.value = [...flowNodes.value] }
async function selectNode(event: { node: Node<PipelineNodeData> }) {
  selectedId.value = event.node.id; logs.value = ''; output.value = {}
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
  try { const result = await api.run(currentPipeline()); workflowName.value = result.workflowName; workspaceMode.value = 'run'; ElMessage.success(`已提交 ${result.workflowName}`); await poll(); if (!terminalStatuses.has(currentStatus.value as UnifiedStatus)) startPolling(); await refreshRuns() } catch (error) { ElMessage.error(String(error)) }
}
async function poll() {
  if (!workflowName.value) return
  try {
    runDetail.value = await api.runDetail(workflowName.value)
    const statuses = new Map(runDetail.value.nodes.map(item => [item.nodeId, item.status]))
    flowNodes.value = flowNodes.value.map(node => node.data ? { ...node, data: { ...node.data, status: statuses.get(node.id) ?? 'PENDING' } } : node)
    flowEdges.value = flowEdges.value.map(edge => ({ ...edge, animated: statuses.get(edge.source) === 'RUNNING' }))
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
  <div class="app-shell">
    <header class="global-header">
      <button class="brand" @click="page = 'catalog'"><span class="brand-mark">P</span><span><strong>Pipeline Studio</strong><small>AI workflow PoC</small></span></button>
      <nav><button :class="{ active: page === 'catalog' }" @click="page = 'catalog'">Pipeline</button><button :class="{ active: page === 'history' }" @click="showHistory()">运行记录</button><button disabled>平台能力 <span>未来接入</span></button></nav>
      <div class="header-boundary"><span class="status-dot"></span>Kind 直连原型<el-tag size="small" type="warning">未接入 ai-platform</el-tag></div>
    </header>

    <PipelineCatalog v-if="page === 'catalog'" :entries="catalogEntries" :runs="runs" @create="newPipeline" @open="openEntry" @copy="copyEntry" @history="showHistory" />
    <PipelineRunList v-else-if="page === 'history'" :runs="runs" :filter="historyFilter" @open="openRun" @back="page = 'catalog'" />

    <template v-else>
      <div class="workspace-header">
        <div class="workspace-title"><el-button link @click="page = 'catalog'">← Pipeline</el-button><div><strong>{{ experimentName }}</strong><span>{{ pipelineName }}</span></div><el-tag :type="workspaceMode === 'run' ? 'success' : 'info'">{{ workspaceMode === 'run' ? '运行视图' : '编辑视图' }}</el-tag></div>
        <div class="workspace-actions"><el-button size="small" @click="showPipelineJson">DSL</el-button><el-button size="small" @click="showWorkflowYaml">Workflow</el-button><el-button v-if="workspaceMode === 'edit'" size="small" @click="saveLocal">保存版本</el-button><el-button v-if="workspaceMode === 'edit'" size="small" type="warning" @click="validatePipeline">校验</el-button><el-button v-if="workspaceMode === 'edit'" size="small" type="primary" @click="run">运行</el-button><el-button v-else size="small" @click="workspaceMode = 'edit'">返回编辑</el-button><el-button v-if="workspaceMode === 'run'" size="small" type="danger" :disabled="!canStop" @click="stopRun">停止运行</el-button></div>
      </div>
      <div v-if="workspaceMode === 'edit'" class="pipeline-meta-bar"><el-input v-model="pipelineName" size="small" aria-label="Pipeline name"><template #prepend>标识</template></el-input><el-input v-model="experimentName" size="small" aria-label="Experiment name"><template #prepend>名称</template></el-input><el-input v-model="tagsText" size="small" aria-label="Run tags"><template #prepend>标签</template></el-input><el-input-number v-model="timeoutSeconds" size="small" :min="1" :max="3600" /><span>秒超时</span></div>
      <div v-else class="run-status-bar"><div><span class="status-dot" :class="`status-${currentStatus.toLowerCase()}`"></span><strong>{{ currentStatus }}</strong><span>{{ workflowName }}</span></div><div>{{ completedCount }}/{{ runDetail?.nodes.length ?? flowNodes.length }} 节点完成</div></div>

      <main class="workspace">
        <NodePalette v-if="workspaceMode === 'edit'" :node-types="registry" />
        <div class="flow-wrap" @dragover="onDragOver" @drop="onDrop">
          <VueFlow v-model:nodes="flowNodes" v-model:edges="flowEdges" :node-types="nodeTypes" fit-view-on-init :delete-key-code="workspaceMode === 'edit' ? 'Delete' : null" :nodes-draggable="workspaceMode === 'edit'" :nodes-connectable="workspaceMode === 'edit'" :elements-selectable="true" @connect="onConnect" @node-click="selectNode" @pane-click="selectedId = undefined">
            <Background pattern-color="#cbd5e1" :gap="20" /><MiniMap :node-color="minimapColor" pannable zoomable /><Controls />
          </VueFlow>
        </div>
        <NodeInspector v-if="selectedNode" :data="selectedNode.data" :runtime="selectedRuntime" :logs="logs" :output="output" :control-busy="controlBusy" :readonly="workspaceMode === 'run'" @changed="refreshSelectedNode" @stop-node="stopSelectedNode" @rerun-node="rerunSelectedNode" />
        <aside v-else class="inspector pipeline-inspector">
          <span class="eyebrow">{{ workspaceMode === 'run' ? 'RUN OVERVIEW' : 'PIPELINE' }}</span><h3>{{ workspaceMode === 'run' ? '运行概览' : '编排说明' }}</h3>
          <template v-if="workspaceMode === 'edit'"><p>从左侧拖入节点，通过类型化端口连线。点击节点后可配置属性并查看输入输出契约。</p><div class="boundary-card"><strong>可复用边界</strong><span>DSL · Registry · Validator · Adapter Contract</span><small>Kubernetes 只是当前 PoC 执行器</small></div></template>
          <template v-else>
            <el-descriptions :column="1" border size="small"><el-descriptions-item label="实验">{{ runDetail?.experimentName }}</el-descriptions-item><el-descriptions-item label="状态">{{ currentStatus }}</el-descriptions-item><el-descriptions-item label="开始">{{ runDetail?.startedAt || '-' }}</el-descriptions-item><el-descriptions-item label="结束">{{ runDetail?.finishedAt || '-' }}</el-descriptions-item></el-descriptions>
            <h4>业务门禁</h4><div v-for="item in decisions" :key="item.id" class="decision-card"><el-tag :type="item.value.outcome === 'APPROVED' ? 'success' : 'danger'">{{ item.value.outcome }}</el-tag><span>{{ item.value.gate }}</span></div>
            <h4>模型排行榜</h4><el-table v-if="leaderboard" :data="leaderboard" size="small"><el-table-column prop="rank" label="#" width="36" /><el-table-column prop="algorithm" label="模型" /><el-table-column prop="accuracy" label="Acc" width="58" /></el-table><el-empty v-else description="尚未生成" :image-size="48" />
            <div v-if="deploymentRequest" class="deployment-card"><el-tag type="success">READY</el-tag><strong>推理部署交接已就绪</strong><span>{{ deploymentRequest.id }}</span><small>{{ deploymentRequest.adapterContract }} · {{ deploymentRequest.executionMode }}</small></div>
            <h4>Artifact Lineage</h4><div v-for="item in artifacts" :key="`${item.nodeId}-${item.port}`" class="artifact-card"><span class="artifact-kind">{{ item.kind }}</span><strong>{{ item.id }}</strong><small>{{ item.nodeId }} · {{ item.port }}</small></div>
          </template>
        </aside>
      </main>
    </template>
    <el-dialog v-model="dialogOpen" :title="dialogTitle" width="72%"><pre class="json-dialog">{{ dialogContent }}</pre></el-dialog>
  </div>
</template>
