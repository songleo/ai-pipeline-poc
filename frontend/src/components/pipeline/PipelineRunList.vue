<script setup lang="ts">
import type { RunDetail } from '../../types/pipeline'

defineProps<{ runs: RunDetail[]; filter?: string }>()
const emit = defineEmits<{ open: [run: RunDetail]; back: [] }>()
function duration(run: RunDetail) {
  if (!run.startedAt || !run.finishedAt) return '-'
  return `${Math.max(0, Math.round((Date.parse(run.finishedAt) - Date.parse(run.startedAt)) / 1000))} 秒`
}
</script>

<template>
  <section class="catalog-page">
    <div class="page-title-row"><div><el-button link @click="emit('back')">← 返回 Pipeline</el-button><h1>运行记录</h1><p>{{ filter ? `Pipeline：${filter}` : '当前 Kind 环境中的受控 Pipeline 运行' }}</p></div></div>
    <el-table :data="runs.filter(item => !filter || item.pipelineName === filter)" class="pipeline-table" empty-text="暂无运行记录">
      <el-table-column prop="workflowName" label="Run ID" min-width="250" />
      <el-table-column prop="pipelineName" label="Pipeline" min-width="190" />
      <el-table-column label="状态" width="120"><template #default="scope"><el-tag>{{ scope.row.status }}</el-tag></template></el-table-column>
      <el-table-column prop="startedAt" label="开始时间" width="210" />
      <el-table-column label="运行时长" width="110"><template #default="scope">{{ duration(scope.row) }}</template></el-table-column>
      <el-table-column label="操作" width="120"><template #default="scope"><el-button link type="primary" @click="emit('open', scope.row)">查看详情</el-button></template></el-table-column>
    </el-table>
  </section>
</template>
