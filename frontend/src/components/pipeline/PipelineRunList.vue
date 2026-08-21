<script setup lang="ts">
import { computed, ref } from 'vue'
import type { RunDetail, UnifiedStatus } from '../../types/pipeline'
import { filterAndSortRuns, statusLabel, type RunScope } from '../../utils/runs'

const props = defineProps<{ runs: RunDetail[]; filter?: string }>()
const emit = defineEmits<{ open: [run: RunDetail]; back: [] }>()
const query = ref('')
const status = ref<UnifiedStatus | ''>('')
const scope = ref<RunScope>('business')
const visibleRuns = computed(() => filterAndSortRuns(props.runs, { pipeline: props.filter, query: query.value, status: status.value, scope: scope.value }))
function duration(run: RunDetail) {
  if (!run.startedAt || !run.finishedAt) return '-'
  return `${Math.max(0, Math.round((Date.parse(run.finishedAt) - Date.parse(run.startedAt)) / 1000))} 秒`
}
function displayTime(value?: string) { return value ? new Date(value).toLocaleString('zh-CN', { hour12: false }) : '-' }
function tagType(value: UnifiedStatus) { return value === 'SUCCEEDED' ? 'success' : value === 'RUNNING' ? 'primary' : ['FAILED', 'ERROR'].includes(value) ? 'danger' : value === 'CANCELLED' ? 'info' : 'warning' }
</script>

<template>
  <section class="catalog-page">
    <div class="page-title-row"><div><el-button link @click="emit('back')">← 返回 Pipeline</el-button><h1>运行记录</h1><p>{{ filter ? `Pipeline：${filter}` : '当前 Kind 环境中的受控 Pipeline 运行' }}</p></div></div>
    <div class="run-filters">
      <el-input v-model="query" clearable placeholder="搜索 Run ID、Pipeline 或实验" />
      <el-select v-model="status" placeholder="全部状态" clearable><el-option v-for="item in ['RUNNING','SUCCEEDED','FAILED','ERROR','CANCELLED']" :key="item" :label="statusLabel(item as UnifiedStatus)" :value="item" /></el-select>
      <el-segmented v-model="scope" :options="[{ label: '业务运行', value: 'business' }, { label: '系统验证', value: 'system' }, { label: '全部', value: 'all' }]" />
      <span class="run-count">{{ visibleRuns.length }} 条，按最新时间排序</span>
    </div>
    <el-table :data="visibleRuns" class="pipeline-table" empty-text="当前筛选条件下暂无运行记录">
      <el-table-column prop="workflowName" label="Run ID" min-width="250" />
      <el-table-column label="实验 / Pipeline" min-width="230"><template #default="scope"><strong>{{ scope.row.experimentName || scope.row.pipelineName }}</strong><div class="table-subtitle">{{ scope.row.pipelineName }}</div></template></el-table-column>
      <el-table-column label="状态" width="120"><template #default="scope"><el-tag :type="tagType(scope.row.status)">{{ statusLabel(scope.row.status) }}</el-tag></template></el-table-column>
      <el-table-column label="开始时间" width="190"><template #default="scope">{{ displayTime(scope.row.startedAt) }}</template></el-table-column>
      <el-table-column label="运行时长" width="100"><template #default="scope">{{ duration(scope.row) }}</template></el-table-column>
      <el-table-column label="定义快照" width="120"><template #default="scope"><code>{{ scope.row.definitionDigest || '历史记录' }}</code></template></el-table-column>
      <el-table-column label="操作" width="100"><template #default="scope"><el-button link type="primary" @click="emit('open', scope.row)">查看详情</el-button></template></el-table-column>
    </el-table>
  </section>
</template>
