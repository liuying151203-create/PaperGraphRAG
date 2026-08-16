export type RerankRuntimeState = 'available' | 'unavailable' | 'unknown'

type RerankStatusSource = {
  configuration?: {
    enable_rerank?: boolean
    rerank_binding?: string | null
    rerank_model?: string | null
  }
  rerank_queue_status?: {
    available?: boolean
  }
} | null

export const getRerankRuntimeState = (status: RerankStatusSource): RerankRuntimeState => {
  if (!status?.configuration) return 'unknown'

  if (
    status.configuration.enable_rerank === true ||
    status.rerank_queue_status?.available === true
  ) {
    return 'available'
  }

  if (
    status.configuration.enable_rerank === false ||
    status.configuration.rerank_binding === 'null'
  ) {
    return 'unavailable'
  }

  return 'unknown'
}

export const getRerankRuntimeLabel = (status: RerankStatusSource): string | null => {
  if (getRerankRuntimeState(status) !== 'available') return null
  return status?.configuration?.rerank_model || status?.configuration?.rerank_binding || null
}
