import { FormEvent, useEffect, useState } from 'react'
import { BookOpen, Search } from 'lucide-react'
import Button from '@/components/ui/Button'
import Textarea from '@/components/ui/Textarea'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/Card'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/Select'
import { ChatMessage, MessageWithError } from '@/components/retrieval/ChatMessage'
import EvidenceTrace from '@/components/retrieval/EvidenceTrace'
import { errorMessage } from '@/lib/utils'
import { getZoteroLibrary, queryScholarGraph } from '@/api/lightrag'
import type { ScholarQueryResponse, ScholarRetrievalStrategy } from '@/api/lightrag'

const descriptions: Record<ScholarRetrievalStrategy, string> = {
  VECTOR: 'Semantic chunk retrieval (LightRAG naive mode)',
  GRAPH: 'Entity and relation retrieval (LightRAG hybrid graph mode)',
  HYBRID: 'Graph and vector evidence together (LightRAG mix mode)'
}

export default function AskPapersView() {
  const [query, setQuery] = useState('')
  const [strategy, setStrategy] = useState<ScholarRetrievalStrategy>('HYBRID')
  const [collectionKey, setCollectionKey] = useState('ALL')
  const [collections, setCollections] = useState<string[]>([])
  const [result, setResult] = useState<ScholarQueryResponse | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    void getZoteroLibrary()
      .then((items) => {
        const keys = new Set(items.flatMap((item) => item.collections))
        setCollections(Array.from(keys).sort())
      })
      .catch(() => setCollections([]))
  }, [])

  const submit = async (event: FormEvent) => {
    event.preventDefault()
    if (query.trim().length < 3 || loading) return
    setLoading(true)
    setError(null)
    try {
      setResult(
        await queryScholarGraph(
          query.trim(),
          strategy,
          collectionKey === 'ALL' ? undefined : collectionKey
        )
      )
    } catch (cause) {
      setError(errorMessage(cause))
    } finally {
      setLoading(false)
    }
  }

  const answerMessage: MessageWithError | null = result
    ? {
      id: `scholar-${result.strategy}-${result.response_time}`,
      role: 'assistant',
      content: result.answer,
      displayContent: result.answer,
      responseTime: result.response_time,
      thinkingTime: null,
      mermaidRendered: true,
      latexRendered: true
    }
    : null

  return (
    <div className="size-full overflow-auto bg-muted/20 p-4">
      <div className="mx-auto flex max-w-6xl flex-col gap-4">
        <div>
          <div className="flex items-center gap-2">
            <BookOpen className="size-5 text-emerald-500" />
            <h1 className="text-xl font-semibold">Ask Papers</h1>
          </div>
          <p className="mt-1 text-sm text-muted-foreground">Compare stable retrieval strategies and inspect the evidence used for every answer.</p>
        </div>

        <Card>
          <CardContent className="pt-4">
            <form onSubmit={submit} className="space-y-3">
              <Textarea
                value={query}
                onChange={(event) => setQuery(event.target.value)}
                placeholder="Ask a scientific question across your indexed papers…"
                className="min-h-24"
              />
              <div className="flex flex-wrap items-center gap-3">
                <Select value={strategy} onValueChange={(value) => setStrategy(value as ScholarRetrievalStrategy)}>
                  <SelectTrigger className="w-44" aria-label="Retrieval strategy">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="VECTOR">Vector</SelectItem>
                    <SelectItem value="GRAPH">Graph</SelectItem>
                    <SelectItem value="HYBRID">Hybrid</SelectItem>
                  </SelectContent>
                </Select>
                <Select value={collectionKey} onValueChange={setCollectionKey}>
                  <SelectTrigger className="w-52" aria-label="Paper collection scope">
                    <SelectValue placeholder="All papers" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="ALL">All indexed papers</SelectItem>
                    {collections.map((key) => (
                      <SelectItem key={key} value={key}>
                        Collection {key}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
                <span className="grow text-xs text-muted-foreground">{descriptions[strategy]}</span>
                <Button type="submit" disabled={loading || query.trim().length < 3}>
                  <Search className="size-4" />
                  {loading ? 'Searching…' : 'Ask'}
                </Button>
              </div>
            </form>
          </CardContent>
        </Card>

        {error && <div className="rounded-lg border border-red-300 bg-red-50 p-3 text-sm text-red-700 dark:border-red-900 dark:bg-red-950 dark:text-red-300">{error}</div>}

        {result && answerMessage && (
          <div className="grid gap-4 lg:grid-cols-[minmax(0,1.2fr)_minmax(360px,0.8fr)]">
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center justify-between text-base">
                  Answer
                  <span className="rounded-full bg-emerald-500/10 px-2 py-1 text-xs font-medium text-emerald-600 dark:text-emerald-300">{result.strategy}</span>
                </CardTitle>
              </CardHeader>
              <CardContent>
                <ChatMessage message={answerMessage} />
              </CardContent>
            </Card>
            <EvidenceTrace evidence={result.evidence} />
          </div>
        )}
      </div>
    </div>
  )
}
