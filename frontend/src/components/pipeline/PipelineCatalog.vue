<script setup lang="ts">
import { computed, ref } from 'vue'
import type { PipelineCatalogEntry, RunDetail } from '../../types/pipeline'
import { latestCatalogEntries, versionsForPipeline } from '../../utils/pipelineCatalog'

const props = defineProps<{ entries: PipelineCatalogEntry[]; runs: RunDetail[] }>()
const emit = defineEmits<{ create: []; open: [entry: PipelineCatalogEntry]; copy: [entry: PipelineCatalogEntry]; history: [pipelineName?: string]; delete: [entry: PipelineCatalogEntry] }>()
const query = ref('')
const versionDialog = ref(false)
const versionPipeline = ref<string>()
const templates = computed(() => props.entries.filter(item => item.source === 'template'))
const locals = computed(() => latestCatalogEntries(props.entries).filter(item => `${item.name} ${item.pipeline.metadata.name}`.toLowerCase().includes(query.value.toLowerCase())))
const versionEntries = computed(() => versionsForPipeline(props.entries, versionPipeline.value ?? ''))
function latestRun(name: string) { return props.runs.find(item => item.pipelineName === name) }
function displayTime(value: string) { return value === '内置模板' ? value : new Date(value).toLocaleString('zh-CN', { hour12: false }) }
function showVersions(entry: PipelineCatalogEntry) { versionPipeline.value = entry.pipeline.metadata.name; versionDialog.value = true }
</script>

<template>
  <section class="catalog-page">
    <div class="catalog-hero">
      <div><span class="eyebrow">AI PIPELINE POC</span><h1>把 AI 业务能力编排成可运行的流水线</h1><p>使用受控组件完成定义、校验、运行与结果追踪。</p></div>
      <el-button type="primary" size="large" @click="emit('create')">新建 Pipeline</el-button>
    </div>
    <div class="section-heading"><div><h2>业务模板</h2><p>从受控场景开始，避免用户提交任意镜像或脚本。</p></div></div>
    <div class="template-grid">
      <article v-for="entry in templates" :key="entry.id" class="template-card">
        <div class="template-icon">ML</div><div class="template-body"><el-tag size="small" :type="entry.recommended ? 'success' : 'info'">{{ entry.recommended ? '新手推荐' : '专业示例' }}</el-tag><h3>{{ entry.name }}</h3><p>{{ entry.description }}</p>
        <div class="template-flow">{{ entry.flowSummary }}</div>
        <el-button type="primary" plain @click="emit('open', entry)">查看模板</el-button><el-button @click="emit('copy', entry)">创建演示副本</el-button></div>
      </article>
    </div>
    <div class="section-heading list-heading"><div><h2>我的 Pipeline</h2><p>每次保存都会生成不可变版本；运行与具体版本绑定。</p></div>
      <div class="catalog-tools"><el-input v-model="query" clearable placeholder="搜索名称" style="width:220px" /><el-button @click="emit('history')">全部运行记录</el-button></div>
    </div>
    <el-table :data="locals" class="pipeline-table" empty-text="尚未保存 Pipeline，可从上方模板开始">
      <el-table-column label="Pipeline">
        <template #default="scope"><strong>{{ scope.row.name }}</strong><div class="table-subtitle">{{ scope.row.pipeline.metadata.name }}</div></template>
      </el-table-column>
      <el-table-column label="版本" width="90"><template #default="scope">v{{ scope.row.version }}</template></el-table-column>
      <el-table-column label="节点" width="80"><template #default="scope">{{ scope.row.pipeline.spec.nodes.length }}</template></el-table-column>
      <el-table-column label="最近状态" width="130"><template #default="scope"><el-tag v-if="latestRun(scope.row.pipeline.metadata.name)" size="small">{{ latestRun(scope.row.pipeline.metadata.name)?.status }}</el-tag><span v-else>-</span></template></el-table-column>
      <el-table-column label="更新时间" width="190"><template #default="scope">{{ displayTime(scope.row.updatedAt) }}</template></el-table-column>
      <el-table-column label="操作" width="360"><template #default="scope"><el-button link type="primary" @click="emit('open', scope.row)">编辑</el-button><el-button link @click="showVersions(scope.row)">版本历史</el-button><el-button link @click="emit('copy', scope.row)">复制</el-button><el-button link @click="emit('history', scope.row.pipeline.metadata.name)">运行记录</el-button><el-button link type="danger" @click="emit('delete', scope.row)">删除</el-button></template></el-table-column>
    </el-table>
    <el-dialog v-model="versionDialog" title="版本历史" width="680px">
      <el-table :data="versionEntries" empty-text="暂无版本">
        <el-table-column label="版本" width="90"><template #default="scope"><strong>v{{ scope.row.version }}</strong></template></el-table-column>
        <el-table-column label="节点" width="80"><template #default="scope">{{ scope.row.pipeline.spec.nodes.length }}</template></el-table-column>
        <el-table-column label="保存时间" min-width="190"><template #default="scope">{{ displayTime(scope.row.updatedAt) }}</template></el-table-column>
        <el-table-column label="定义摘要" min-width="170"><template #default="scope">{{ scope.row.description }}</template></el-table-column>
        <el-table-column label="操作" width="100"><template #default="scope"><el-button link type="primary" @click="versionDialog = false; emit('open', scope.row)">打开</el-button></template></el-table-column>
      </el-table>
    </el-dialog>
  </section>
</template>
