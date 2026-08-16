import { describe, expect, test } from 'bun:test'
import { getRerankRuntimeLabel, getRerankRuntimeState } from './rerankStatus'

describe('rerank runtime status', () => {
  test('reports unknown before authenticated health configuration is available', () => {
    expect(getRerankRuntimeState(null)).toBe('unknown')
    expect(getRerankRuntimeState({})).toBe('unknown')
  })

  test('reports unavailable for the default null binding', () => {
    expect(
      getRerankRuntimeState({
        configuration: { enable_rerank: false, rerank_binding: 'null' }
      })
    ).toBe('unavailable')
  })

  test('reports the configured model when reranking is available', () => {
    const status = {
      configuration: {
        enable_rerank: true,
        rerank_binding: 'cohere',
        rerank_model: 'BAAI/bge-reranker-v2-m3'
      },
      rerank_queue_status: { available: true }
    }

    expect(getRerankRuntimeState(status)).toBe('available')
    expect(getRerankRuntimeLabel(status)).toBe('BAAI/bge-reranker-v2-m3')
  })
})
