import type { Pipeline, PipelineEdge, PipelineNode } from '../types/pipeline'

const nodes: PipelineNode[] = [
  { id: 'dataset', type: 'dataset-version', version: '1.0.0', name: '已标注电商评论集 v1', parameters: { datasetName: 'ecommerce-comment-labels', version: 'v1.0', sampleCount: 50000, missingRate: 0.006, classBalance: 0.24, durationSeconds: 1 } },
  { id: 'profile', type: 'data-profile', version: '1.0.0', name: '标签与隐私质量画像', parameters: { durationSeconds: 2 } },
  { id: 'data-gate', type: 'data-quality-gate', version: '1.0.0', name: '评论数据质量门禁', parameters: { minSamples: 20000, maxMissingRate: 0.02 } },
  { id: 'preprocess', type: 'feature-preprocess', version: '1.0.0', name: '清洗并划分三类数据集', parameters: { strategy: 'standardize', durationSeconds: 2 } },
  { id: 'train-baseline', type: 'train-model', version: '1.0.0', name: 'BERT 评论分类微调', parameters: { algorithm: 'bert-base-chinese', epochs: 3, learningRate: 0.0002, resourceProfile: 'cpu-small', durationSeconds: 8, baseAccuracy: 0.88, baseF1: 0.84, latencyMs: 38, retryLimit: 2, failMode: 'never' } },
  { id: 'train-candidate', type: 'train-model', version: '1.0.0', name: 'RoBERTa 评论分类微调', parameters: { algorithm: 'roberta-wwm-ext', epochs: 4, learningRate: 0.0001, resourceProfile: 'cpu-medium', durationSeconds: 8, baseAccuracy: 0.92, baseF1: 0.88, latencyMs: 45, retryLimit: 2, failMode: 'never' } },
  { id: 'eval-baseline', type: 'evaluate-model', version: '1.0.0', name: 'BERT 独立测试集评测', parameters: { accuracyAdjustment: 0.01, durationSeconds: 2 } },
  { id: 'eval-candidate', type: 'evaluate-model', version: '1.0.0', name: 'RoBERTa 独立测试集评测', parameters: { accuracyAdjustment: 0.005, durationSeconds: 2 } },
  { id: 'leaderboard', type: 'compare-evaluations', version: '1.0.0', name: '排行榜与候选选择', parameters: {} },
  { id: 'admission', type: 'model-admission-gate', version: '1.0.0', name: '评论分类模型准入', parameters: { minAccuracy: 0.9, minF1: 0.85, maxLatencyMs: 60 } },
  { id: 'register', type: 'register-model-version', version: '1.0.0', name: '登记评论分类模型', parameters: { versionAlias: 'comment-classifier-candidate' } },
  { id: 'inference-smoke', type: 'inference-smoke-test', version: '1.0.0', name: '投诉评论推理冒烟', parameters: { inputSample: '客服一直不处理我的退款申请', expectedOutput: '投诉', durationSeconds: 2 } },
  { id: 'deployment', type: 'deployment-handoff', version: '1.0.0', name: '交接推理部署', parameters: { environment: 'staging', resourceProfile: 'cpu-small', replicas: 1 } },
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
  ['register', 'registeredModel', 'inference-smoke', 'registeredModel'], ['register', 'registeredModel', 'deployment', 'registeredModel'],
  ['inference-smoke', 'inferenceTest', 'deployment', 'inferenceTest'],
  ['admission', 'rejectedDecision', 'rejected-report', 'decision'],
].map(([source, sourcePort, target, targetPort]) => ({ source, sourcePort, target, targetPort }))

export const examplePipeline: Pipeline = {
  apiVersion: 'demo.pipeline.io/v1alpha1', kind: 'Pipeline',
  metadata: { name: 'comment-classification-demo', experimentName: '小林的 AI 评论分类项目', scenario: 'training-evaluation-admission', tags: ['poc', 'nlp', 'comment-classification'] },
  spec: { nodes, edges, runPolicy: { timeoutSeconds: 420 } },
  uiLayout: { nodes: {
    dataset: { x: 20, y: 250 }, profile: { x: 240, y: 100 }, 'data-gate': { x: 470, y: 250 }, preprocess: { x: 700, y: 250 },
    'train-baseline': { x: 930, y: 90 }, 'train-candidate': { x: 930, y: 410 }, 'eval-baseline': { x: 1170, y: 90 },
    'eval-candidate': { x: 1170, y: 410 }, leaderboard: { x: 1410, y: 250 }, admission: { x: 1650, y: 250 },
    register: { x: 1890, y: 90 }, 'inference-smoke': { x: 2120, y: 90 }, deployment: { x: 2350, y: 90 }, 'approved-report': { x: 1890, y: 280 }, 'rejected-report': { x: 1890, y: 470 },
  } },
}
