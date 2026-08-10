import { ChevronRight, FileText, Network, Quote } from 'lucide-react'
import type { ScholarQueryResponse } from '@/api/lightrag'

const emptyLabel = <p className="text-xs text-muted-foreground">No evidence returned for this strategy.</p>

export default function EvidenceTrace({ evidence }: { evidence: ScholarQueryResponse['evidence'] }) {
  return (
    <section className="space-y-3" aria-label="Evidence trace">
      <div className="flex items-center justify-between">
        <h2 className="text-sm font-semibold">Evidence Trace</h2>
        <span className="text-xs text-muted-foreground">
          {evidence.sources.length} sources · {evidence.vector.length} chunks · {evidence.relations.length} relations
        </span>
      </div>

      <details open className="rounded-lg border bg-card p-3">
        <summary className="flex cursor-pointer list-none items-center gap-2 text-sm font-medium">
          <Quote className="size-4 text-emerald-500" />
          Vector Evidence
        </summary>
        <div className="mt-3 space-y-2">
          {evidence.vector.length === 0
            ? emptyLabel
            : evidence.vector.map((chunk) => (
              <article key={chunk.chunk_id} className="rounded-md bg-muted/60 p-3 text-xs">
                <div className="mb-2 flex flex-wrap items-center gap-2 text-muted-foreground">
                  <span className="font-medium text-foreground">{chunk.paper?.title || chunk.file_path}</span>
                  {chunk.paper?.year && <span>{chunk.paper.year}</span>}
                  {chunk.section && <span>§ {chunk.section}</span>}
                  {chunk.page !== null && chunk.page !== undefined && <span>p. {chunk.page}</span>}
                  {chunk.score !== null && chunk.score !== undefined && <span>score {chunk.score.toFixed(3)}</span>}
                  <span>chunk {chunk.chunk_id}</span>
                </div>
                <p className="whitespace-pre-wrap leading-relaxed">{chunk.content}</p>
              </article>
            ))}
        </div>
      </details>

      <details open className="rounded-lg border bg-card p-3">
        <summary className="flex cursor-pointer list-none items-center gap-2 text-sm font-medium">
          <Network className="size-4 text-violet-500" />
          Graph Evidence
        </summary>
        <div className="mt-3 space-y-2">
          {evidence.relations.length === 0
            ? emptyLabel
            : evidence.relations.map((relation, index) => (
              <article key={`${relation.source}-${relation.relation}-${relation.target}-${index}`} className="rounded-md bg-muted/60 p-3 text-xs">
                <div className="flex flex-wrap items-center gap-2 font-medium">
                  <span>{relation.source}</span>
                  <ChevronRight className="size-3 text-violet-500" />
                  <span className="rounded bg-violet-500/10 px-2 py-0.5 text-violet-600 dark:text-violet-300">{relation.relation || 'RELATED_TO'}</span>
                  <ChevronRight className="size-3 text-violet-500" />
                  <span>{relation.target}</span>
                </div>
                {relation.description && <p className="mt-2 text-muted-foreground">{relation.description}</p>}
              </article>
            ))}
          {evidence.entities.length > 0 && (
            <div className="flex flex-wrap gap-1 pt-1">
              {evidence.entities.map((entity) => (
                <span key={`${entity.entity_name}-${entity.entity_type}`} className="rounded-full border px-2 py-1 text-[11px]">
                  {entity.entity_name} · {entity.entity_type}
                </span>
              ))}
            </div>
          )}
        </div>
      </details>

      <details className="rounded-lg border bg-card p-3">
        <summary className="flex cursor-pointer list-none items-center gap-2 text-sm font-medium">
          <FileText className="size-4 text-sky-500" />
          Sources
        </summary>
        <ol className="mt-3 space-y-2 text-xs">
          {evidence.sources.map((source) => (
            <li key={`${source.reference_id}-${source.file_path}`} className="rounded-md bg-muted/60 p-2">
              <span className="mr-2 font-semibold">[{source.reference_id}]</span>
              <span>{source.title || source.file_path}</span>
              {source.authors.length > 0 && <span className="text-muted-foreground"> · {source.authors.join(', ')}</span>}
              {source.doi && <span className="block text-muted-foreground">DOI: {source.doi}</span>}
            </li>
          ))}
        </ol>
      </details>
    </section>
  )
}
