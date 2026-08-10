import { useEffect, useState } from 'react'
import { FilterIcon } from 'lucide-react'
import { useSigma } from '@react-sigma/core'

import Button from '@/components/ui/Button'
import Checkbox from '@/components/ui/Checkbox'
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/Popover'
import { useGraphStore } from '@/stores/graph'

const ACADEMIC_ENTITY_TYPES = [
  'Paper',
  'Method',
  'Task',
  'Dataset',
  'Metric',
  'Model',
  'Concept',
  'Attack',
  'Defense'
] as const

const AcademicEntityFilter = () => {
  const sigma = useSigma()
  const rawGraph = useGraphStore.use.rawGraph()
  const graphNodeCount = useGraphStore.use.graphNodeCount()
  const graphEdgeCount = useGraphStore.use.graphEdgeCount()
  const [selectedTypes, setSelectedTypes] = useState<Set<string>>(new Set())

  const availableTypes = (() => {
    if (graphNodeCount === 0) return []
    const present = new Set(
      (rawGraph?.nodes ?? [])
        .map((node) => String(node.properties?.entity_type ?? '').trim().toLowerCase())
        .filter(Boolean)
    )
    return ACADEMIC_ENTITY_TYPES.filter((entityType) => present.has(entityType.toLowerCase()))
  })()

  useEffect(() => {
    const graph = sigma.getGraph()
    const selected = new Set(Array.from(selectedTypes, (value) => value.toLowerCase()))

    graph.forEachNode((node) => {
      const rawNode = rawGraph?.getNode(node)
      const entityType = String(rawNode?.properties?.entity_type ?? '').trim().toLowerCase()
      graph.setNodeAttribute(node, 'hidden', selected.size > 0 && !selected.has(entityType))
    })
    graph.forEachEdge((edge, _attributes, source, target) => {
      const hidden =
        Boolean(graph.getNodeAttribute(source, 'hidden')) ||
        Boolean(graph.getNodeAttribute(target, 'hidden'))
      graph.setEdgeAttribute(edge, 'hidden', hidden)
    })
    sigma.refresh()
  }, [sigma, rawGraph, graphNodeCount, graphEdgeCount, selectedTypes])

  const toggleType = (entityType: string) => {
    setSelectedTypes((current) => {
      const next = new Set(current)
      if (next.has(entityType)) next.delete(entityType)
      else next.add(entityType)
      return next
    })
  }

  const activeLabel = selectedTypes.size === 0 ? 'All types' : `${selectedTypes.size} selected`

  return (
    <Popover>
      <PopoverTrigger asChild>
        <Button
          variant="outline"
          size="sm"
          className="bg-background/80 h-9 shadow-sm backdrop-blur-lg"
          aria-label="Filter graph by academic entity type"
        >
          <FilterIcon className="size-4" />
          {activeLabel}
        </Button>
      </PopoverTrigger>
      <PopoverContent align="start" className="w-56 p-3">
        <div className="mb-2 flex items-center justify-between">
          <p className="text-sm font-semibold">Academic entity types</p>
          {selectedTypes.size > 0 && (
            <button
              type="button"
              className="text-primary text-xs hover:underline"
              onClick={() => setSelectedTypes(new Set())}
            >
              Show all
            </button>
          )}
        </div>
        <div className="space-y-2">
          {ACADEMIC_ENTITY_TYPES.map((entityType) => {
            const available = availableTypes.includes(entityType)
            return (
              <label
                key={entityType}
                className="flex cursor-pointer items-center gap-2 text-sm has-[:disabled]:cursor-not-allowed has-[:disabled]:opacity-45"
              >
                <Checkbox
                  checked={selectedTypes.has(entityType)}
                  disabled={!available}
                  onCheckedChange={() => toggleType(entityType)}
                  aria-label={`Show ${entityType} entities`}
                />
                <span>{entityType}</span>
              </label>
            )
          })}
        </div>
        <p className="text-muted-foreground mt-3 text-[11px]">
          Empty types are disabled. Selecting multiple types keeps their union visible.
        </p>
      </PopoverContent>
    </Popover>
  )
}

export default AcademicEntityFilter
