import { useCallback, useEffect, useState } from 'react'
import { BarChart3, Play, RefreshCw } from 'lucide-react'

import Button from '@/components/ui/Button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/Card'
import {
  getEvaluationDatasets,
  getEvaluationRuns,
  startEvaluationRun
} from '@/api/lightrag'
import type {
  EvaluationDatasetSummary,
  EvaluationRunSummary
} from '@/api/lightrag'
import { errorMessage } from '@/lib/utils'

export default function EvaluationView() {
  const [dataset, setDataset] = useState<EvaluationDatasetSummary | null>(null)
  const [runs, setRuns] = useState<EvaluationRunSummary[]>([])
  const [loading, setLoading] = useState(true)
  const [running, setRunning] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const refresh = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const [datasets, nextRuns] = await Promise.all([
        getEvaluationDatasets(),
        getEvaluationRuns()
      ])
      setDataset(datasets[0] ?? null)
      setRuns(nextRuns)
    } catch (cause) {
      setError(errorMessage(cause))
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    const timer = window.setTimeout(() => void refresh(), 0)
    return () => window.clearTimeout(timer)
  }, [refresh])

  const runAblation = async () => {
    if (!dataset || running) return
    const cells = dataset.question_count * 3
    if (
      !window.confirm(
        `Run ${cells} generated-answer evaluations (${dataset.question_count} questions × 3 strategies)? This uses the configured LLM.`
      )
    ) {
      return
    }
    setRunning(true)
    setError(null)
    try {
      const summary = await startEvaluationRun({ enable_rerank: false })
      setRuns((current) => [summary, ...current])
    } catch (cause) {
      setError(errorMessage(cause))
    } finally {
      setRunning(false)
    }
  }

  const latest = runs[0] ?? null

  return (
    <div className="size-full overflow-auto bg-muted/20 p-4">
      <div className="mx-auto flex max-w-6xl flex-col gap-4">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <div className="flex items-center gap-2">
              <BarChart3 className="size-5 text-emerald-500" />
              <h1 className="text-xl font-semibold">Evaluation</h1>
            </div>
            <p className="mt-1 text-sm text-muted-foreground">
              Controlled Vector, Graph, and Hybrid ablation on the same questions and budgets.
            </p>
          </div>
          <div className="flex gap-2">
            <Button variant="outline" onClick={() => void refresh()} disabled={loading || running}>
              <RefreshCw className={`size-4 ${loading ? 'animate-spin' : ''}`} /> Refresh
            </Button>
            <Button onClick={() => void runAblation()} disabled={!dataset || running}>
              <Play className={`size-4 ${running ? 'animate-pulse' : ''}`} />
              {running ? 'Running ablation…' : 'Run 3-mode ablation'}
            </Button>
          </div>
        </div>

        {error && (
          <div className="rounded-lg border border-red-300 bg-red-50 p-3 text-sm text-red-700 dark:border-red-900 dark:bg-red-950 dark:text-red-300">
            {error}
          </div>
        )}

        {dataset && (
          <Card>
            <CardContent className="grid gap-3 p-4 sm:grid-cols-3">
              <Metric label="Dataset" value={`${dataset.dataset_id} v${dataset.version}`} />
              <Metric label="Public papers" value={dataset.paper_count} />
              <Metric label="Questions" value={dataset.question_count} />
              <div className="sm:col-span-3">
                <p className="text-xs text-muted-foreground">Coverage</p>
                <div className="mt-1 flex flex-wrap gap-1">
                  {dataset.categories.map((category) => (
                    <span key={category} className="rounded-full border px-2 py-1 text-xs">
                      {category.replace('_', ' ')}
                    </span>
                  ))}
                </div>
              </div>
            </CardContent>
          </Card>
        )}

        <Card>
          <CardHeader>
            <CardTitle className="flex items-center justify-between text-base">
              Latest controlled run
              {latest && <span className="font-mono text-xs font-normal text-muted-foreground">{latest.run_id}</span>}
            </CardTitle>
          </CardHeader>
          <CardContent className="overflow-x-auto">
            {latest ? (
              <table className="w-full min-w-[760px] text-left text-sm">
                <thead className="border-b text-xs uppercase text-muted-foreground">
                  <tr>
                    <th className="px-2 py-2">Mode</th>
                    <th className="px-2 py-2">Answer correctness</th>
                    <th className="px-2 py-2">Evidence recall</th>
                    <th className="px-2 py-2">Faithfulness</th>
                    <th className="px-2 py-2">Citation validity</th>
                    <th className="px-2 py-2">Latency</th>
                    <th className="px-2 py-2">Failed</th>
                  </tr>
                </thead>
                <tbody>
                  {latest.modes.map((mode) => (
                    <tr key={mode.retrieval_mode} className="border-b last:border-0">
                      <td className="px-2 py-3 font-semibold">{mode.retrieval_mode}</td>
                      <td className="px-2 py-3">{formatScore(mode.answer_correctness)}</td>
                      <td className="px-2 py-3">{formatScore(mode.evidence_recall)}</td>
                      <td className="px-2 py-3">{formatScore(mode.faithfulness)}</td>
                      <td className="px-2 py-3">{formatScore(mode.citation_validity)}</td>
                      <td className="px-2 py-3">{mode.latency == null ? 'N/A' : `${mode.latency.toFixed(3)} s`}</td>
                      <td className="px-2 py-3">{mode.failed}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            ) : (
              <p className="py-8 text-center text-sm text-muted-foreground">
                No evaluation result has been generated. The repository contains questions and expected evidence, not fabricated scores.
              </p>
            )}
          </CardContent>
        </Card>

        <p className="text-xs text-muted-foreground">
          Correctness and evidence recall are transparent expected-term coverage. Faithfulness remains N/A unless a judge is configured. Every per-query answer, evidence payload, latency, available token usage, metric, and failure is stored as JSONL.
        </p>
      </div>
    </div>
  )
}

function Metric({ label, value }: { label: string; value: string | number }) {
  return (
    <div>
      <p className="text-xs text-muted-foreground">{label}</p>
      <p className="mt-1 font-semibold">{value}</p>
    </div>
  )
}

function formatScore(value?: number | null): string {
  return value == null ? 'N/A' : `${(value * 100).toFixed(1)}%`
}
