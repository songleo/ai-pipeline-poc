import type { Pipeline, PipelineEdge, PipelineNode } from '../types/pipeline'

const nodes: PipelineNode[] = [
  { id: 'dataset', type: 'dataset-version', version: '1.0.0', name: '客户流失数据 v2026.08', parameters: { datasetName: 'customer-churn', version: 'v2026.08', sampleCount: 12000, missingRate: 0.018, classBalance: 0.42, durationSeconds: 1 } },
  { id: 'profile', type: 'data-profile', version: '1.0.0', name: '数据画像', parameters: { durationSeconds: 2 } },
  { id: 'data-gate', type: 'data-quality-gate', version: '1.0.0', name: '数据质量门禁', parameters: { minSamples: 5000, maxMissingRate: 0.05 } },
  { id: 'preprocess', type: 'feature-preprocess', version: '1.0.0', name: '特征标准化', parameters: { strategy: 'standardize', durationSeconds: 2 } },
  { id: 'train-baseline', type: 'train-model', version: '1.0.0', name: '基线模型训练', parameters: { algorithm: 'lightgbm', epochs: 30, learningRate: 0.08, resourceProfile: 'cpu-small', durationSeconds: 8, baseAccuracy: 0.87, baseF1: 0.82, latencyMs: 28, retryLimit: 2, failMode: 'never' } },
  { id: 'train-candidate', type: 'train-model', version: '1.0.0', name: '候选模型训练', parameters: { algorithm: 'xgboost', epochs: 60, learningRate: 0.04, resourceProfile: 'cpu-medium', durationSeconds: 8, baseAccuracy: 0.91, baseF1: 0.86, latencyMs: 42, retryLimit: 2, failMode: 'never' } },
  { id: 'eval-baseline', type: 'evaluate-model', version: '1.0.0', name: '基线模型评测', parameters: { accuracyAdjustment: 0.01, durationSeconds: 2 } },
  { id: 'eval-candidate', type: 'evaluate-model', version: '1.0.0', name: '候选模型评测', parameters: { accuracyAdjustment: 0.005, durationSeconds: 2 } },
  { id: 'leaderboard', type: 'compare-evaluations', version: '1.0.0', name: '排行榜与候选选择', parameters: {} },
  { id: 'admission', type: 'model-admission-gate', version: '1.0.0', name: '模型准入门禁', parameters: { minAccuracy: 0.9, minF1: 0.84, maxLatencyMs: 50 } },
  { id: 'register', type: 'register-model-version', version: '1.0.0', name: '登记候选模型', parameters: { versionAlias: 'candidate' } },
  { id: 'approved-report', type: 'qualification-report', version: '1.0.0', name: '生成通过报告', parameters: {} },
  { id: 'rejected-report', type: 'qualification-report', version: '1.0.0', name: '生成拒绝报告', parameters: {} },
]

const edges: PipelineEdge[] = [
  ['dataset', 'dataset', 'profile', 'dataset'], ['dataset', 'dataset', 'data-gate', 'dataset'], ['profile', 'profile', 'data-gate', 'profile'],
  ['data-gate', 'approvedDataset', 'preprocess', 'dataset'], ['preprocess', 'processedDataset', 'train-baseline', 'dataset'],
  ['preprocess', 'processedDataset', 'train-candidate', 'dataset'], ['train-baseline', 'model', 'eval-baseline', 'model'],
  ['preprocess', 'processedDataset', 'eval-baseline', 'dataset'], ['train-candidate', 'model', 'eval-candidate', 'model'],
  ['preprocess', 'processedDataset', 'eval-candidate', 'dataset'], ['eval-baseline', 'evaluation', 'leaderboard', 'evaluationA'],
  ['eval-candidate', 'evaluation', 'leaderboard', 'evaluationB'], ['leaderboard', 'candidate', 'admission', 'candidate'],
  ['admission', 'approvedCandidate', 'register', 'candidate'], ['admission', 'approvedDecision', 'approved-report', 'decision'],
  ['admission', 'rejectedDecision', 'rejected-report', 'decision'],
].map(([source, sourcePort, target, targetPort]) => ({ source, sourcePort, target, targetPort }))

export const examplePipeline: Pipeline = {
  apiVersion: 'demo.pipeline.io/v1alpha1', kind: 'Pipeline',
  metadata: { name: 'training-qualification-demo', experimentName: '客户流失模型资格评审', scenario: 'training-evaluation-admission', tags: ['p0', 'classification', 'qualification'] },
  spec: { nodes, edges, runPolicy: { timeoutSeconds: 420 } },
  uiLayout: { nodes: {
    dataset: { x: 20, y: 250 }, profile: { x: 240, y: 100 }, 'data-gate': { x: 470, y: 250 }, preprocess: { x: 700, y: 250 },
    'train-baseline': { x: 930, y: 90 }, 'train-candidate': { x: 930, y: 410 }, 'eval-baseline': { x: 1170, y: 90 },
    'eval-candidate': { x: 1170, y: 410 }, leaderboard: { x: 1410, y: 250 }, admission: { x: 1650, y: 250 },
    register: { x: 1890, y: 90 }, 'approved-report': { x: 1890, y: 280 }, 'rejected-report': { x: 1890, y: 470 },
  } },
}
