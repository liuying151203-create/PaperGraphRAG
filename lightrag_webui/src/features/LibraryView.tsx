import { useCallback, useEffect, useState } from 'react'
import type { ReactNode } from 'react'
import { BookMarked, RefreshCw, RotateCcw, Trash2, Unplug, Wifi } from 'lucide-react'
import Button from '@/components/ui/Button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/Card'
import { errorMessage } from '@/lib/utils'
import {
  deleteZoteroAttachmentIndex,
  getZoteroLibrary,
  getZoteroStatus,
  reindexZoteroAttachment,
  syncZoteroLibrary
} from '@/api/lightrag'
import type { ZoteroLibraryItem, ZoteroStatusResponse } from '@/api/lightrag'

export default function LibraryView() {
  const [status, setStatus] = useState<ZoteroStatusResponse | null>(null)
  const [items, setItems] = useState<ZoteroLibraryItem[]>([])
  const [loading, setLoading] = useState(true)
  const [actionKey, setActionKey] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  const refresh = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const [nextStatus, nextItems] = await Promise.all([getZoteroStatus(), getZoteroLibrary()])
      setStatus(nextStatus)
      setItems(nextItems)
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

  const run = async (key: string, operation: () => Promise<unknown>) => {
    setActionKey(key)
    setError(null)
    try {
      await operation()
      await refresh()
    } catch (cause) {
      setError(errorMessage(cause))
    } finally {
      setActionKey(null)
    }
  }

  const counts = {
    indexed: status?.status_counts.indexed || 0,
    processing: status?.status_counts.processing || 0,
    failed: status?.status_counts.failed || 0
  }

  return (
    <div className="size-full overflow-auto bg-muted/20 p-4">
      <div className="mx-auto flex max-w-7xl flex-col gap-4">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <div className="flex items-center gap-2">
              <BookMarked className="size-5 text-emerald-500" />
              <h1 className="text-xl font-semibold">Library</h1>
            </div>
            <p className="mt-1 text-sm text-muted-foreground">Zotero is the source of truth; LightRAG stores only a derived search index.</p>
          </div>
          <div className="flex gap-2">
            <Button variant="outline" onClick={() => void refresh()} disabled={loading}>
              <RefreshCw className={`size-4 ${loading ? 'animate-spin' : ''}`} /> Refresh
            </Button>
            <Button onClick={() => void run('sync', syncZoteroLibrary)} disabled={!status?.connected || actionKey !== null}>
              <RotateCcw className={`size-4 ${actionKey === 'sync' ? 'animate-spin' : ''}`} /> Sync Now
            </Button>
          </div>
        </div>

        {error && <div className="rounded-lg border border-red-300 bg-red-50 p-3 text-sm text-red-700 dark:border-red-900 dark:bg-red-950 dark:text-red-300">{error}</div>}

        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
          <StatusCard label="Zotero" value={status?.connected ? 'Connected' : 'Disconnected'} icon={status?.connected ? <Wifi className="size-4 text-emerald-500" /> : <Unplug className="size-4 text-amber-500" />} />
          <StatusCard label="Papers" value={status?.papers ?? 0} />
          <StatusCard label="Indexed" value={counts.indexed} />
          <StatusCard label="Processing" value={counts.processing} />
          <StatusCard label="Failed" value={counts.failed} />
        </div>

        {!status?.connected && status?.error && (
          <p className="rounded-lg border border-amber-300 bg-amber-50 p-3 text-sm text-amber-800 dark:border-amber-900 dark:bg-amber-950 dark:text-amber-200">
            Start Zotero and enable “Allow other applications on this computer to communicate with Zotero”. Existing derived mappings remain visible below.
          </p>
        )}

        <Card>
          <CardHeader><CardTitle className="text-base">Synced PDF attachments</CardTitle></CardHeader>
          <CardContent className="overflow-x-auto">
            <table className="w-full min-w-[900px] text-left text-sm">
              <thead className="border-b text-xs uppercase text-muted-foreground">
                <tr>
                  <th className="px-2 py-2">Paper</th><th className="px-2 py-2">Authors</th><th className="px-2 py-2">Year</th><th className="px-2 py-2">Collections</th><th className="px-2 py-2">Status</th><th className="px-2 py-2">Actions</th>
                </tr>
              </thead>
              <tbody>
                {items.map((item) => (
                  <tr key={item.attachment_key} className="border-b align-top last:border-0">
                    <td className="px-2 py-3"><p className="font-medium">{item.title || item.item_key}</p><p className="text-xs text-muted-foreground">{item.attachment_key}{item.doi ? ` · ${item.doi}` : ''}</p></td>
                    <td className="px-2 py-3 text-xs">{item.authors.join(', ') || '—'}</td>
                    <td className="px-2 py-3">{item.year || '—'}</td>
                    <td className="px-2 py-3 text-xs">{item.collections.join(', ') || '—'}</td>
                    <td className="px-2 py-3"><span className="rounded-full border px-2 py-1 text-xs capitalize">{item.index_status}</span>{item.error && <p className="mt-1 max-w-52 text-xs text-red-500">{item.error}</p>}</td>
                    <td className="px-2 py-3"><div className="flex gap-1"><Button size="sm" variant="outline" disabled={actionKey !== null || !status?.connected} onClick={() => void run(`reindex-${item.attachment_key}`, () => reindexZoteroAttachment(item.attachment_key))}><RotateCcw className="size-3" /> Reindex</Button><Button size="sm" variant="ghost" disabled={actionKey !== null || item.index_status === 'excluded'} onClick={() => { if (window.confirm('Delete only this derived LightRAG index? The Zotero item and PDF will not be changed.')) void run(`delete-${item.attachment_key}`, () => deleteZoteroAttachmentIndex(item.attachment_key)) }}><Trash2 className="size-3" /> Delete Index</Button></div></td>
                  </tr>
                ))}
                {!loading && items.length === 0 && <tr><td colSpan={6} className="py-10 text-center text-muted-foreground">No Zotero PDF mappings yet. Connect Zotero and choose Sync Now.</td></tr>}
              </tbody>
            </table>
          </CardContent>
        </Card>
      </div>
    </div>
  )
}

function StatusCard({ label, value, icon }: { label: string; value: string | number; icon?: ReactNode }) {
  return <Card><CardContent className="flex items-center justify-between p-4"><div><p className="text-xs text-muted-foreground">{label}</p><p className="mt-1 text-lg font-semibold">{value}</p></div>{icon}</CardContent></Card>
}
