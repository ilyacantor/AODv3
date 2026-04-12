import { useEffect, useRef, useState, useCallback } from 'react'
import { Network, DataSet } from 'vis-network/standalone'
import type { Node, Edge, Options } from 'vis-network/standalone'
import { Search, ZoomIn, ZoomOut, Maximize2, Lock, Unlock, X, ChevronDown, Filter, Loader2, Info } from 'lucide-react'

/* ─── Types ─── */
interface PipelineNode extends Node {
  id: string | number
  label?: string
  level: number
  stage: string
  nodeType: string
  metadata: Record<string, string | number>
  ctxRenderer?: any
}

interface DetailsData {
  label: string
  stage: string
  nodeType: string
  metadata: Record<string, string | number>
}

interface RunData {
  aod_discovery_id: string
  tenant_id: string
  status: string
  started_at: string
  completed_at: string | null
  input_meta: {
    snapshot_id: string
    scale: string
    enterprise_profile: string
    created_at: string
    counts: Record<string, number>
    fabric_planes: { plane_type: string; vendor: string; is_healthy: boolean }[]
    sors: { domain: string; sor_name: string; sor_type: string; confidence: string }[]
  }
  counts: {
    observations_in: number
    candidates_out: number
    assets_admitted: number
    rejected: number
    ambiguous_matches: number
    findings_generated: number
    iron_dome_rejected?: number
    domain_merged?: number
    entities_normalized?: number
  }
  stage_timings?: Record<string, number>
}

/* ─── Color constants (matching AAM topology) ─── */
const C = {
  cyan:     '#22d3ee',
  cyan700:  '#0e7490',
  orange:   '#f97316',
  red:      '#ef4444',
  purple:   '#a855f7',
  green:    '#22c55e',
  amber:    '#f59e0b',
  blue:     '#3b82f6',
  violet:   '#8b5cf6',
  edge:     '#64748b',
  bgDark:   '#0f172a',
  slate800: '#1e293b',
  slate700: '#334155',
  slate600: '#475569',
  slate400: '#94a3b8',
  white:    '#ffffff',
}

/* ─── Custom database/cylinder renderer (label centered inside) ─── */
function drawDatabaseNode({ ctx, x, y, state: { selected, hover }, style, label }: any) {
  const w = style.size * 1.4
  const h = style.size * 1.6
  const ovalH = h * 0.22
  const bgColor = (style.color?.background || C.cyan) as string
  const borderColor = (style.color?.border || bgColor) as string
  const fontColor = (style.color?.fontColor || C.bgDark) as string
  const fontSize = Math.max(9, Math.min(12, style.size * 0.55))

  return {
    drawNode() {
      ctx.save()
      if (selected) {
        ctx.shadowColor = 'rgba(34, 211, 238, 0.5)'
        ctx.shadowBlur = 12
        ctx.shadowOffsetX = 0
        ctx.shadowOffsetY = 0
      }
      // Body
      ctx.beginPath()
      ctx.moveTo(x - w, y - h / 2 + ovalH)
      ctx.lineTo(x - w, y + h / 2 - ovalH)
      ctx.bezierCurveTo(x - w, y + h / 2 + ovalH * 0.6, x + w, y + h / 2 + ovalH * 0.6, x + w, y + h / 2 - ovalH)
      ctx.lineTo(x + w, y - h / 2 + ovalH)
      ctx.closePath()
      ctx.fillStyle = bgColor
      ctx.fill()
      ctx.strokeStyle = selected ? C.white : hover ? C.slate400 : borderColor
      ctx.lineWidth = selected ? 2.5 : 1.5
      ctx.stroke()
      // Top ellipse
      ctx.beginPath()
      ctx.ellipse(x, y - h / 2 + ovalH, w, ovalH, 0, 0, Math.PI * 2)
      ctx.fillStyle = bgColor
      ctx.fill()
      ctx.strokeStyle = selected ? C.white : hover ? C.slate400 : borderColor
      ctx.stroke()
      ctx.restore()
      // Label centered inside
      if (label) {
        ctx.save()
        ctx.font = `bold ${fontSize}px Quicksand, sans-serif`
        ctx.fillStyle = fontColor
        ctx.textAlign = 'center'
        ctx.textBaseline = 'middle'
        const lines = label.split('\n')
        const lineHeight = fontSize * 1.3
        const totalH = lines.length * lineHeight
        const startY = y + ovalH * 0.3 - totalH / 2 + lineHeight / 2
        for (let i = 0; i < lines.length; i++) {
          ctx.fillText(lines[i], x, startY + i * lineHeight)
        }
        ctx.restore()
      }
    },
    nodeDimensions: { width: w * 2, height: h + ovalH },
  }
}

/* ─── Custom tenant hexagon renderer (auto-sizes to fit label) ─── */
function drawTenantNode({ ctx, x, y, state: { selected, hover }, style, label }: any) {
  const fontSize = 12
  const padding = 14
  const lineHeight = fontSize * 1.35

  // Measure text and word-wrap to determine hexagon size
  ctx.save()
  ctx.font = `bold ${fontSize}px Quicksand, sans-serif`
  const words = (label || '').split(/[-\s]+/)
  const maxLineW = style.size * 1.4 // target inner width
  const lines: string[] = []
  let cur = ''
  for (const w of words) {
    const test = cur ? cur + ' ' + w : w
    if (ctx.measureText(test).width > maxLineW && cur) {
      lines.push(cur)
      cur = w
    } else {
      cur = test
    }
  }
  if (cur) lines.push(cur)

  // Compute hexagon size from text bounds
  const textW = Math.max(...lines.map((l) => ctx.measureText(l).width))
  const textH = lines.length * lineHeight
  const innerW = textW + padding * 2
  const innerH = textH + padding * 2
  // For a flat-top hexagon: width = sz * sqrt(3), height = sz * 2
  const sz = Math.max(innerW / 1.73, innerH / 2, style.size)
  ctx.restore()

  // Flat-top hexagon path
  function hexPath() {
    ctx.beginPath()
    for (let i = 0; i < 6; i++) {
      const angle = (Math.PI / 3) * i
      const px = x + sz * Math.cos(angle)
      const py = y + sz * Math.sin(angle)
      if (i === 0) ctx.moveTo(px, py)
      else ctx.lineTo(px, py)
    }
    ctx.closePath()
  }

  return {
    drawNode() {
      ctx.save()
      if (selected || hover) {
        ctx.shadowColor = 'rgba(34, 211, 238, 0.5)'
        ctx.shadowBlur = selected ? 20 : 10
        ctx.shadowOffsetX = 0
        ctx.shadowOffsetY = 0
      }
      hexPath()
      const grad = ctx.createLinearGradient(x, y - sz, x, y + sz)
      grad.addColorStop(0, '#22d3ee')
      grad.addColorStop(1, '#0891b2')
      ctx.fillStyle = grad
      ctx.fill()
      ctx.strokeStyle = selected ? C.white : '#06b6d4'
      ctx.lineWidth = selected ? 3 : 2
      ctx.stroke()
      ctx.restore()
      // Label inside (multi-line, centered)
      if (label) {
        ctx.save()
        ctx.font = `bold ${fontSize}px Quicksand, sans-serif`
        ctx.fillStyle = C.bgDark
        ctx.textAlign = 'center'
        ctx.textBaseline = 'middle'
        const startY = y - ((lines.length - 1) * lineHeight) / 2
        for (let i = 0; i < lines.length; i++) {
          ctx.fillText(lines[i], x, startY + i * lineHeight)
        }
        ctx.restore()
      }
    },
    nodeDimensions: { width: sz * 1.73, height: sz * 2 },
  }
}

const observationColors = [C.cyan, C.violet, C.orange, C.green, C.blue, C.amber, C.red]

/* ─── Build graph data from live run ─── */
function buildNodes(run: RunData): PipelineNode[] {
  const mc = run.input_meta.counts
  const rc = run.counts

  // Observation plane counts (aggregate sub-keys into 7 planes)
  const planes: { id: string; label: string; count: number; tier: string; examples: string }[] = [
    { id: 'plane-discovery', label: 'Discovery',  count: mc.discovery_observations || 0, tier: 'Tier 2', examples: 'Web apps, SaaS' },
    { id: 'plane-idp',      label: 'Identity\nProvider', count: mc.idp_objects || 0,    tier: 'Tier 2', examples: 'Okta, Azure AD' },
    { id: 'plane-cmdb',     label: 'CMDB',        count: mc.cmdb_cis || 0,              tier: 'Tier 1', examples: 'ServiceNow, Jira' },
    { id: 'plane-cloud',    label: 'Cloud\nInventory', count: mc.cloud_resources || 0,   tier: 'Tier 2', examples: 'AWS, Azure, GCP' },
    { id: 'plane-network',  label: 'Network',     count: (mc.network_dns || 0) + (mc.network_proxy || 0) + (mc.network_certs || 0), tier: 'Tier 2', examples: 'DNS, proxy, certs' },
    { id: 'plane-finance',  label: 'Finance',     count: (mc.finance_vendors || 0) + (mc.finance_contracts || 0) + (mc.finance_transactions || 0), tier: 'Tier 2', examples: 'Vendors, contracts' },
    { id: 'plane-endpoint', label: 'Endpoint',    count: (mc.endpoint_devices || 0) + (mc.endpoint_installed_apps || 0), tier: 'Tier 2', examples: 'Devices, installed apps' },
  ]

  const totalAssets = rc.assets_admitted

  const nodes: PipelineNode[] = [
    // Level 0 — Hub: tenant name rendered inside a custom hexagon
    { id: 'aod', label: run.tenant_id, level: 0, shape: 'custom', ctxRenderer: drawTenantNode, color: { background: C.cyan, border: C.cyan }, size: 42, stage: 'Discovery', nodeType: 'hexagon', metadata: { tenant: run.tenant_id, aod_discovery_id: run.aod_discovery_id, snapshot_id: run.input_meta.snapshot_id, status: run.status, scale: run.input_meta.scale, profile: run.input_meta.enterprise_profile, started_at: run.started_at, description: 'Central discovery hub — orchestrates evidence collection across all observation planes for this tenant' } },

    // Level 2 — Ingested
    { id: 'ingested', label: `Ingested\n${rc.observations_in}`, level: 2, shape: 'custom', ctxRenderer: drawDatabaseNode, color: { background: C.cyan, border: C.cyan } as any, size: 22, stage: 'Discovery', nodeType: 'database', metadata: { tenant: run.tenant_id, aod_discovery_id: run.aod_discovery_id, count: rc.observations_in, description: 'Raw evidence collected from all observation planes' } },

    // Level 3 — Normalization funnel: rejected + duplicates + unique entities
    { id: 'rejected', label: `Rejected\n${(rc.iron_dome_rejected || 0) + rc.rejected}`, level: 3, shape: 'custom', ctxRenderer: drawDatabaseNode, color: { background: C.red, border: C.red, fontColor: C.white } as any, size: 18, stage: 'Discovery', nodeType: 'database', metadata: { tenant: run.tenant_id, aod_discovery_id: run.aod_discovery_id, count: (rc.iron_dome_rejected || 0) + rc.rejected, iron_dome: rc.iron_dome_rejected || 0, admission_failed: rc.rejected, description: `Observations that could not be admitted to the catalog. Iron Dome (${rc.iron_dome_rejected || 0}): blocked at normalization — internal hostnames, invalid TLDs, malformed domains, or empty identifiers. Admission failed (${rc.rejected}): passed normalization but lacked sufficient governance evidence — no IdP, CMDB, cloud, finance, or discovery signals met the admission threshold.` } },
    ...(rc.domain_merged ? [{ id: 'domain-merged', label: `Duplicates\n${rc.domain_merged}`, level: 3, shape: 'custom', ctxRenderer: drawDatabaseNode, color: { background: C.amber, border: C.amber, fontColor: C.white } as any, size: 18, stage: 'Discovery', nodeType: 'database', metadata: { tenant: run.tenant_id, aod_discovery_id: run.aod_discovery_id, count: rc.domain_merged, description: 'Observations merged — multiple signals from different planes resolved to the same entity' } }] : []) as PipelineNode[],

    // Level 3 — Cataloged (same level, main flow)
    { id: 'cataloged', label: `Cataloged\n${totalAssets}`, level: 3, shape: 'custom', ctxRenderer: drawDatabaseNode, color: { background: C.cyan700, border: C.cyan700, fontColor: C.white } as any, size: 20, stage: 'Classification', nodeType: 'database', metadata: { tenant: run.tenant_id, aod_discovery_id: run.aod_discovery_id, count: totalAssets, description: 'Confirmed assets admitted to catalog' } },

    // Level 4 — Handoff hub
    { id: 'handoff-aam',    label: 'Handoff\n→ AAM',           level: 4, shape: 'diamond',  color: { background: C.orange, border: C.orange },  size: 20, stage: 'Classification', nodeType: 'diamond', metadata: { tenant: run.tenant_id, aod_discovery_id: run.aod_discovery_id, description: 'ConnectionCandidate handoff to AAM', target: 'AAM module' } },
  ]

  // Level 1 — Observation plane nodes (multicolored triangleDown with 3D shading)
  planes.forEach((p, i) => {
    const col = observationColors[i % observationColors.length]
    nodes.push({
      id: p.id, label: `*${p.label}*\n_${p.count.toLocaleString()}_`, level: 1,
      shape: 'triangleDown', size: 18,
      font: {
        multi: 'markdown',
        color: C.white, size: 13, face: 'Quicksand, sans-serif',
        bold: { color: col, size: 14, face: 'Quicksand, sans-serif', vadjust: -2 },
        ital: { color: C.white, size: 12, face: 'Quicksand, sans-serif' },
      } as any,
      color: { background: col, border: col, highlight: { background: col, border: C.white } },
      shadow: { enabled: true, color: col + '40', size: 8, x: 2, y: 3 },
      borderWidth: 2,
      stage: 'Discovery', nodeType: 'triangleDown',
      metadata: { tenant: run.tenant_id, aod_discovery_id: run.aod_discovery_id, type: p.label.replace('\n', ' '), examples: p.examples, tier: p.tier, signals: p.count, description: `Collects ${p.label.replace('\n', ' ').toLowerCase()} evidence from ${p.examples} and similar systems` },
    })
  })

  return nodes
}

function buildEdges(run: RunData): Edge[] {
  const raw: Omit<Edge, 'id'>[] = []
  const rc = run.counts
  const planeIds = ['plane-discovery', 'plane-idp', 'plane-cmdb', 'plane-cloud', 'plane-network', 'plane-finance', 'plane-endpoint']

  // Hub → Observation planes
  planeIds.forEach((p) => raw.push({ from: 'aod', to: p, width: 2 }))

  // Observation planes → Ingested
  planeIds.forEach((p) => raw.push({ from: p, to: 'ingested', width: 1.5 }))

  // Ingested → Rejected / Duplicates / Cataloged
  raw.push({ from: 'ingested', to: 'rejected', width: 1.5, color: { color: C.red, opacity: 0.8 } })
  if (rc.domain_merged) raw.push({ from: 'ingested', to: 'domain-merged', width: 1.5, color: { color: C.amber, opacity: 0.8 } })
  raw.push({ from: 'ingested', to: 'cataloged', width: 2 })

  // Cataloged → Handoff
  raw.push({ from: 'cataloged', to: 'handoff-aam', width: 2 })

  const withIds = raw.map((e, i) => ({ ...e, id: `e${i}` }))
  return assignEdgeCurves(withIds)
}

/* ─── Distribute curve roundness so overlapping edges fan out visually ─── */
function assignEdgeCurves(edges: Edge[]): Edge[] {
  // Group edges by shared endpoint (fan-out by `from`, fan-in by `to`)
  const fanOut = new Map<string, number[]>()
  const fanIn  = new Map<string, number[]>()
  edges.forEach((e, i) => {
    const f = e.from as string
    const t = e.to as string
    if (!fanOut.has(f)) fanOut.set(f, [])
    fanOut.get(f)!.push(i)
    if (!fanIn.has(t)) fanIn.set(t, [])
    fanIn.get(t)!.push(i)
  })

  // Collect all fan groups, largest first so each edge gets roundness from its most crowded fan
  const groups: number[][] = []
  for (const indices of fanOut.values()) if (indices.length > 1) groups.push(indices)
  for (const indices of fanIn.values())  if (indices.length > 1) groups.push(indices)
  groups.sort((a, b) => b.length - a.length)

  const assigned = new Set<number>()
  for (const group of groups) {
    const unassigned = group.filter((i) => !assigned.has(i))
    if (unassigned.length < 2) continue
    const n = unassigned.length
    const step = Math.min(0.25, 0.8 / (n - 1))
    unassigned.forEach((idx, j) => {
      const roundness = -((n - 1) * step) / 2 + j * step
      edges[idx] = {
        ...edges[idx],
        smooth: { enabled: true, type: 'curvedCW' as any, roundness },
      }
      assigned.add(idx)
    })
  }

  return edges
}

/* ─── Layout presets ─── */
type LayoutKey = 'hierarchical' | 'force' | 'circular'

function getLayoutOptions(layout: LayoutKey): Partial<Options> {
  switch (layout) {
    case 'hierarchical':
      return {
        layout: {
          hierarchical: {
            enabled: true,
            direction: 'LR',
            levelSeparation: 120,
            nodeSpacing: 65,
            treeSpacing: 75,
            sortMethod: 'directed',
          },
        },
        physics: {
          enabled: true,
          hierarchicalRepulsion: {
            centralGravity: 0.0,
            springLength: 100,
            springConstant: 0.01,
            nodeDistance: 70,
          },
          stabilization: { iterations: 100 },
        },
      }
    case 'force':
      return {
        layout: { hierarchical: { enabled: false } },
        physics: {
          enabled: true,
          forceAtlas2Based: {
            gravitationalConstant: -60,
            centralGravity: 0.01,
            springLength: 120,
            springConstant: 0.08,
          },
          maxVelocity: 50,
          solver: 'forceAtlas2Based',
          stabilization: { iterations: 200 },
        },
      }
    case 'circular':
      return {
        layout: { hierarchical: { enabled: false } },
        physics: {
          enabled: true,
          repulsion: {
            centralGravity: 0.2,
            springLength: 200,
            springConstant: 0.05,
            nodeDistance: 150,
          },
          solver: 'repulsion',
          stabilization: { iterations: 200 },
        },
      }
  }
}

function getBaseOptions(): Options {
  return {
    nodes: {
      font: { color: C.white, size: 12, face: 'Quicksand, sans-serif' },
      borderWidth: 2,
      shadow: false,
    },
    edges: {
      color: { color: C.edge, opacity: 0.8 },
      arrows: { to: { enabled: true, scaleFactor: 0.5 } },
      smooth: { enabled: true, type: 'continuous', roundness: 0.5 },
      width: 2,
    },
    interaction: {
      hover: true,
      tooltipDelay: 200,
      zoomView: true,
      dragView: true,
      dragNodes: true,
      navigationButtons: false,
    },
  }
}

/* ─── Legend entries ─── */
const legendItems = [
  { shape: 'hexagon',      color: C.cyan,    label: 'Tenant' },
  { shape: 'triangleDown', color: C.violet,  label: 'Observation plane' },
  { shape: 'database',     color: C.cyan,    label: 'Lifecycle stage' },
  { shape: 'line',         color: C.red,     label: 'Rejected' },
  { shape: 'line',         color: C.amber,   label: 'Duplicates' },
  { shape: 'diamond',      color: C.orange,  label: 'Handoff' },
]

/* ─── Stage filter config ─── */
const ALL_STAGES = ['Discovery', 'Classification'] as const
type Stage = typeof ALL_STAGES[number]

const stageColors: Record<Stage, string> = {
  'Discovery':      C.cyan,
  'Classification': C.purple,
}

/* ─── Component ─── */
export default function Discovery() {
  const containerRef = useRef<HTMLDivElement>(null)
  const networkRef = useRef<Network | null>(null)
  const nodesRef = useRef<DataSet<PipelineNode> | null>(null)
  const edgesRef = useRef<DataSet<Edge> | null>(null)
  const allNodesRef = useRef<PipelineNode[]>([])
  const allEdgesRef = useRef<Edge[]>([])
  const [selectedNode, setSelectedNode] = useState<DetailsData | null>(null)
  const [searchTerm, setSearchTerm] = useState('')
  // Defaults: hierarchical LR with physics on — physics auto-disables after stabilization
  const [layout, setLayout] = useState<LayoutKey>('hierarchical')
  const [refreshKey, setRefreshKey] = useState(0)
  const [physicsEnabled, setPhysicsEnabled] = useState(true)
  const [layoutOpen, setLayoutOpen] = useState(false)
  const [hiddenStages, setHiddenStages] = useState<Set<Stage>>(new Set())
  const [filterOpen, setFilterOpen] = useState(false)

  // Close dropdowns on click outside
  useEffect(() => {
    const close = () => { setLayoutOpen(false); setFilterOpen(false) }
    document.addEventListener('click', close)
    return () => document.removeEventListener('click', close)
  }, [])

  const [loading, setLoading] = useState(true)
  const [loadingMessage, setLoadingMessage] = useState<string | null>('Loading pipeline data...')
  const [error, setError] = useState<string | null>(null)
  const [calloutModal, setCalloutModal] = useState<string | null>(null)
  const [planeCalloutPos, setPlaneCalloutPos] = useState<{ x: number; y: number } | null>(null)
  const planeCanvasCenterRef = useRef<{ x: number; y: number } | null>(null)

  // Fetch latest run data, then initialize network
  useEffect(() => {
    if (!containerRef.current) return
    let destroyed = false
    let rafId: number | null = null

    async function init() {
      try {
        // The iframe receives canonical tenant_id + snapshot_id from app.js.
        // Flow: (1) try /api/runs for a completed discovery run;
        //       (2) if none and snapshot_id was provided, render a preview
        //           from /api/farm/snapshot (Farm-first, cache fallback);
        //       (3) otherwise show an explicit empty state.
        const url = new URLSearchParams(window.location.search)
        const tenantParam = url.get('tenant_id')
        const snapshotIdParam = url.get('snapshot_id')

        const runsUrl = tenantParam ? `/api/runs?tenant_id=${encodeURIComponent(tenantParam)}` : '/api/runs'
        const runsRes = await fetch(runsUrl)
        if (!runsRes.ok) throw new Error(`Failed to fetch runs: ${runsRes.status}`)
        const runs: RunData[] = await runsRes.json()
        if (destroyed) return
        let run: RunData | null = runs.length > 0
          ? (runs.find(r => r.status.startsWith('completed')) || runs[0])
          : null

        if (!run && tenantParam && snapshotIdParam) {
          const snapRes = await fetch(
            `/api/farm/snapshot?tenant_id=${encodeURIComponent(tenantParam)}&snapshot_id=${encodeURIComponent(snapshotIdParam)}`
          )
          if (!snapRes.ok) {
            const body = await snapRes.text().catch(() => '')
            throw new Error(`Snapshot fetch failed: HTTP ${snapRes.status} ${body.slice(0, 200)}`)
          }
          const snap = await snapRes.json()
          const meta = snap.meta || {}
          run = {
            aod_discovery_id: 'snapshot-preview',
            tenant_id: meta.tenant_id || tenantParam,
            status: 'snapshot_loaded',
            started_at: meta.created_at || new Date().toISOString(),
            completed_at: null,
            input_meta: {
              snapshot_id: snapshotIdParam,
              scale: meta.scale || '',
              enterprise_profile: meta.enterprise_profile || '',
              created_at: meta.created_at || '',
              counts: meta.counts || {},
              fabric_planes: meta.fabric_planes || [],
              sors: meta.sors || [],
            },
            counts: {
              observations_in: 0, candidates_out: 0, assets_admitted: 0,
              rejected: 0, ambiguous_matches: 0, findings_generated: 0,
            },
          }
        }

        if (!run) {
          setLoadingMessage(null)
          setLoading(false)
          setError(tenantParam
            ? 'No discovery run or snapshot loaded for this tenant'
            : 'No tenant selected')
          return
        }

        if (destroyed) return

        setLoadingMessage('Stabilizing graph layout...')
        const allNodes = buildNodes(run)
        const allEdges = buildEdges(run)
        allNodesRef.current = allNodes
        allEdgesRef.current = allEdges
        const nodes = new DataSet<PipelineNode>(allNodes)
        const edges = new DataSet<Edge>(allEdges)
        nodesRef.current = nodes
        edgesRef.current = edges

        const options: Options = {
          ...getBaseOptions(),
          ...getLayoutOptions('hierarchical'),
        }

        const network = new Network(containerRef.current!, { nodes, edges }, options)
        networkRef.current = network

        // After stabilization: disable physics, then fit on the NEXT draw frame
        // so the canvas has final node positions before we calculate the viewport.
        let settled = false
        const settle = () => {
          if (settled || destroyed) return
          settled = true
          const positions = network.getPositions()
          network.setOptions({ physics: { enabled: false } })
          setPhysicsEnabled(false)
          // Compute callout position under observation plane nodes
          const planeNodeIds = ['plane-discovery', 'plane-idp', 'plane-cmdb', 'plane-cloud', 'plane-network', 'plane-finance', 'plane-endpoint']
          const planePositions = planeNodeIds.map(id => positions[id]).filter(Boolean)
          planeCanvasCenterRef.current = planePositions.length > 0 ? {
            x: planePositions.reduce((s, p) => s + p.x, 0) / planePositions.length,
            y: Math.max(...planePositions.map(p => p.y)) + 80,
          } : null
          // Wait for one canvas redraw with final positions, then fit
          network.once('afterDrawing', () => {
            network.fit({ animation: false })
            if (planeCanvasCenterRef.current) {
              const dom = network.canvasToDOM(planeCanvasCenterRef.current)
              setPlaneCalloutPos({ x: dom.x, y: dom.y })
            }
            setLoadingMessage(null)
            setLoading(false)
          })
          // Trigger a redraw so afterDrawing fires
          network.redraw()
        }

        network.once('stabilizationIterationsDone', settle)
        // Safety: if stabilization completed before listener was attached
        setTimeout(settle, 800)

        // Click → details panel
        network.on('click', (params) => {
          if (params.nodes.length > 0) {
            const nodeId = params.nodes[0]
            const node = nodes.get(nodeId) as unknown as PipelineNode | null
            if (node) {
              setSelectedNode({
                label: (node.label || '').replace('\n', ' '),
                stage: node.stage,
                nodeType: node.nodeType,
                metadata: node.metadata,
              })
            }
          } else {
            setSelectedNode(null)
          }
        })

        // Release node on mouseup so it doesn't stay draggable after click
        network.on('dragEnd', (params) => {
          if (params.nodes.length > 0) {
            network.unselectAll()
            // Re-select for the details panel without triggering drag
            const nodeId = params.nodes[0]
            const node = nodes.get(nodeId) as unknown as PipelineNode | null
            if (node) {
              setSelectedNode({
                label: (node.label || '').replace('\n', ' '),
                stage: node.stage,
                nodeType: node.nodeType,
                metadata: node.metadata,
              })
            }
          }
        })

        // Selection glow
        network.on('selectNode', (params) => {
          params.nodes.forEach((id: string) => {
            nodes.update({ id, shadow: { enabled: true, color: 'rgba(34,211,238,0.5)', size: 15, x: 0, y: 0 } } as any)
          })
        })
        network.on('deselectNode', (params) => {
          params.previousSelection.nodes.forEach((id: string) => {
            nodes.update({ id, shadow: false } as any)
          })
        })

        // Update callout positions on zoom/pan/drag (RAF-throttled to avoid flash)
        const updateCalloutPos = () => {
          if (rafId !== null) return
          rafId = requestAnimationFrame(() => {
            rafId = null
            if (planeCanvasCenterRef.current) {
              const dom = network.canvasToDOM(planeCanvasCenterRef.current)
              setPlaneCalloutPos({ x: dom.x, y: dom.y })
            }
          })
        }
        network.on('zoom', updateCalloutPos)
        network.on('dragEnd', updateCalloutPos)
        network.on('dragging', updateCalloutPos)
      } catch (err: any) {
        if (!destroyed) {
          setError(err.message || 'Failed to load pipeline data')
          setLoading(false)
        }
      }
    }

    init()

    return () => {
      destroyed = true
      if (rafId !== null) cancelAnimationFrame(rafId)
      networkRef.current?.destroy()
      networkRef.current = null
      nodesRef.current = null
      edgesRef.current = null
    }
  }, [refreshKey]) // eslint-disable-line react-hooks/exhaustive-deps

  // Layout changes
  useEffect(() => {
    const net = networkRef.current
    if (!net) return

    // 1. Stop physics before swapping solver to prevent mid-frame crash
    net.stopSimulation()

    // 2. Remove any leftover stabilization listener from previous layout
    net.off('stabilizationIterationsDone')

    // 3. Apply new layout options
    const opts = getLayoutOptions(layout)
    net.setOptions(opts as any)

    net.once('stabilizationIterationsDone', () => {
      if (layout === 'hierarchical') {
        net.setOptions({ physics: { enabled: false } })
        setPhysicsEnabled(false)
      }
      net.once('afterDrawing', () => {
        net.fit({ animation: { duration: 300, easingFunction: 'easeInOutQuad' } })
      })
      net.redraw()
    })
    if (layout !== 'hierarchical') {
      setPhysicsEnabled(true)
    }

    // 4. Restart stabilization cleanly
    net.stabilize()
  }, [layout])

  // Listen for parent postMessage to trigger data refresh via useEffect re-run
  useEffect(() => {
    const handler = (event: MessageEvent) => {
      if (event.data?.action === 'refreshData') setRefreshKey(k => k + 1)
    }
    window.addEventListener('message', handler)
    return () => window.removeEventListener('message', handler)
  }, [])

  // Search — dim non-matching nodes
  useEffect(() => {
    const nodes = nodesRef.current
    if (!nodes) return
    const term = searchTerm.toLowerCase().trim()
    const allNodes = nodes.get()

    if (!term) {
      allNodes.forEach((n) => {
        nodes.update({ id: n.id, opacity: 1.0 } as any)
      })
      return
    }

    allNodes.forEach((n) => {
      const label = (n.label || '').toLowerCase()
      const stage = (n.stage || '').toLowerCase()
      const matches = label.includes(term) || stage.includes(term) ||
        Object.values(n.metadata || {}).some((v) => String(v).toLowerCase().includes(term))
      nodes.update({ id: n.id, opacity: matches ? 1.0 : 0.15 } as any)
    })
  }, [searchTerm])

  // Stage filter — hide/show nodes + connected edges
  useEffect(() => {
    const nodes = nodesRef.current
    const edges = edgesRef.current
    if (!nodes || !edges) return

    const allNodes = allNodesRef.current
    const allEdges = allEdgesRef.current

    // Determine visible node IDs
    const visibleIds = new Set<string>()
    allNodes.forEach((n) => {
      if (!hiddenStages.has(n.stage as Stage)) {
        visibleIds.add(n.id as string)
      }
    })

    // Update nodes: hidden if stage is filtered out
    allNodes.forEach((n) => {
      const hidden = !visibleIds.has(n.id as string)
      nodes.update({ id: n.id, hidden } as any)
    })

    // Update edges: hidden if either endpoint is hidden
    allEdges.forEach((e) => {
      const hidden = !visibleIds.has(e.from as string) || !visibleIds.has(e.to as string)
      edges.update({ id: e.id, hidden } as any)
    })
  }, [hiddenStages])

  const toggleStage = useCallback((stage: Stage) => {
    setHiddenStages((prev) => {
      const next = new Set(prev)
      if (next.has(stage)) {
        next.delete(stage)
      } else {
        // Prevent hiding all stages
        if (next.size >= ALL_STAGES.length - 1) return prev
        next.add(stage)
      }
      return next
    })
  }, [])

  // Physics toggle
  const togglePhysics = useCallback(() => {
    const net = networkRef.current
    if (!net) return
    const next = !physicsEnabled
    net.setOptions({ physics: { enabled: next } })
    setPhysicsEnabled(next)
  }, [physicsEnabled])

  // Zoom controls
  const zoomIn = useCallback(() => {
    const net = networkRef.current
    if (!net) return
    const scale = net.getScale()
    net.moveTo({ scale: scale * 1.3, animation: { duration: 300, easingFunction: 'easeInOutQuad' } })
  }, [])

  const zoomOut = useCallback(() => {
    const net = networkRef.current
    if (!net) return
    const scale = net.getScale()
    net.moveTo({ scale: scale / 1.3, animation: { duration: 300, easingFunction: 'easeInOutQuad' } })
  }, [])

  const fitAll = useCallback(() => {
    networkRef.current?.fit({ animation: { duration: 500, easingFunction: 'easeInOutQuad' } })
  }, [])

  return (
    <div id="topology-root" className="relative w-screen h-screen bg-slate-950" style={{
      backgroundImage: 'radial-gradient(circle, rgba(148,163,184,0.08) 1px, transparent 1px)',
      backgroundSize: '20px 20px',
    }}>
      {/* Graph container */}
      <div ref={containerRef} className="w-full h-full" />

      {/* Loading overlay */}
      {loading && (
        <div className="absolute inset-0 flex items-center justify-center z-30">
          <div className="flex items-center gap-3 bg-slate-800/90 backdrop-blur border border-slate-700 rounded-lg px-5 py-3">
            <Loader2 size={18} className="text-cyan-400 animate-spin" />
            <span className="text-sm text-white font-[Quicksand]">{loadingMessage || 'Loading pipeline data...'}</span>
          </div>
        </div>
      )}

      {/* Error overlay */}
      {error && (
        <div className="absolute inset-0 flex items-center justify-center z-30">
          <div className="bg-slate-800/90 backdrop-blur border border-red-500/50 rounded-lg px-5 py-3 max-w-md">
            <span className="text-sm text-red-400 font-[Quicksand]">{error}</span>
          </div>
        </div>
      )}

      {/* Top toolbar */}
      <div className="absolute top-4 left-4 right-4 flex items-center gap-3 pointer-events-none z-10">
        {/* Search */}
        <div className="pointer-events-auto flex items-center gap-2 bg-slate-800/90 backdrop-blur border border-slate-700 rounded-lg px-3 py-2 w-72">
          <Search size={16} className="text-slate-400 shrink-0" />
          <input
            type="text"
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            placeholder="Search nodes..."
            className="bg-transparent text-sm text-white placeholder-slate-500 outline-none w-full font-[Quicksand]"
          />
        </div>

        {/* Layout selector */}
        <div className="pointer-events-auto relative">
          <button
            onClick={(e) => { e.stopPropagation(); setLayoutOpen(!layoutOpen); setFilterOpen(false) }}
            className="flex items-center gap-2 bg-slate-800/90 backdrop-blur border border-slate-700 rounded-lg px-3 py-2 text-sm text-white font-[Quicksand] hover:border-cyan-500/50 transition-colors"
          >
            {layout === 'hierarchical' ? 'Hierarchical LR' : layout === 'force' ? 'Force-directed' : 'Circular'}
            <ChevronDown size={14} className="text-slate-400" />
          </button>
          {layoutOpen && (
            <div className="absolute top-full mt-1 left-0 bg-slate-800/95 backdrop-blur border border-slate-700 rounded-lg overflow-hidden shadow-xl min-w-[160px]">
              {(['hierarchical', 'force', 'circular'] as LayoutKey[]).map((l) => (
                <button
                  key={l}
                  onClick={() => { setLayout(l); setLayoutOpen(false) }}
                  className={`block w-full text-left px-3 py-2 text-sm font-[Quicksand] hover:bg-slate-700/50 transition-colors ${l === layout ? 'text-cyan-400' : 'text-white'}`}
                >
                  {l === 'hierarchical' ? 'Hierarchical LR' : l === 'force' ? 'Force-directed' : 'Circular'}
                </button>
              ))}
            </div>
          )}
        </div>

        {/* Physics toggle */}
        <button
          onClick={togglePhysics}
          className="pointer-events-auto flex items-center gap-1.5 bg-slate-800/90 backdrop-blur border border-slate-700 rounded-lg px-3 py-2 text-sm text-white font-[Quicksand] hover:border-cyan-500/50 transition-colors"
          title={physicsEnabled ? 'Lock positions' : 'Unlock positions'}
        >
          {physicsEnabled ? <Unlock size={14} /> : <Lock size={14} />}
          <span>{physicsEnabled ? 'Physics On' : 'Physics Off'}</span>
        </button>

        {/* Stage filter */}
        <div className="pointer-events-auto relative">
          <button
            onClick={(e) => { e.stopPropagation(); setFilterOpen(!filterOpen); setLayoutOpen(false) }}
            className={`flex items-center gap-1.5 bg-slate-800/90 backdrop-blur border rounded-lg px-3 py-2 text-sm font-[Quicksand] hover:border-cyan-500/50 transition-colors ${hiddenStages.size > 0 ? 'border-cyan-500/60 text-cyan-400' : 'border-slate-700 text-white'}`}
          >
            <Filter size={14} />
            <span>Stages{hiddenStages.size > 0 ? ` (${ALL_STAGES.length - hiddenStages.size}/${ALL_STAGES.length})` : ''}</span>
            <ChevronDown size={14} className="text-slate-400" />
          </button>
          {filterOpen && (
            <div className="absolute top-full mt-1 left-0 bg-slate-800/95 backdrop-blur border border-slate-700 rounded-lg overflow-hidden shadow-xl min-w-[200px] py-1">
              {ALL_STAGES.map((stage) => {
                const active = !hiddenStages.has(stage)
                return (
                  <button
                    key={stage}
                    onClick={() => toggleStage(stage)}
                    className="flex items-center gap-2.5 w-full text-left px-3 py-1.5 text-sm font-[Quicksand] hover:bg-slate-700/50 transition-colors"
                  >
                    <span
                      className="w-3 h-3 rounded-sm border flex-shrink-0 flex items-center justify-center"
                      style={{
                        borderColor: stageColors[stage],
                        backgroundColor: active ? stageColors[stage] : 'transparent',
                      }}
                    >
                      {active && <span className="text-[9px] text-slate-950 font-bold leading-none">{'\u2713'}</span>}
                    </span>
                    <span className={active ? 'text-white' : 'text-slate-500'}>{stage}</span>
                  </button>
                )
              })}
              {hiddenStages.size > 0 && (
                <>
                  <div className="border-t border-slate-700 my-1" />
                  <button
                    onClick={() => setHiddenStages(new Set())}
                    className="w-full text-left px-3 py-1.5 text-xs font-[Quicksand] text-cyan-400 hover:bg-slate-700/50 transition-colors"
                  >
                    Show all stages
                  </button>
                </>
              )}
            </div>
          )}
        </div>
      </div>

      {/* Zoom controls (bottom-right) */}
      <div className="absolute bottom-4 right-4 flex flex-col gap-1.5 z-10">
        <button onClick={zoomIn} className="bg-slate-800/90 backdrop-blur border border-slate-700 rounded-lg w-9 h-9 flex items-center justify-center text-white hover:border-cyan-500/50 transition-colors">
          <ZoomIn size={16} />
        </button>
        <button onClick={zoomOut} className="bg-slate-800/90 backdrop-blur border border-slate-700 rounded-lg w-9 h-9 flex items-center justify-center text-white hover:border-cyan-500/50 transition-colors">
          <ZoomOut size={16} />
        </button>
        <button onClick={fitAll} className="bg-slate-800/90 backdrop-blur border border-slate-700 rounded-lg w-9 h-9 flex items-center justify-center text-white hover:border-cyan-500/50 transition-colors" title="Fit to screen">
          <Maximize2 size={16} />
        </button>
      </div>

      {/* Legend (bottom-left) */}
      <div className="absolute bottom-4 left-4 bg-slate-800/90 backdrop-blur border border-slate-700 rounded-lg px-4 py-3 z-10">
        <div className="text-xs text-slate-400 font-[Quicksand] font-semibold uppercase tracking-wider mb-2">Legend</div>
        <div className="flex flex-col gap-1.5">
          {legendItems.map((item, i) => (
            <div key={`${item.shape}-${item.label}-${i}`} className="flex items-center gap-2 text-xs text-white font-[Quicksand]">
              <LegendShape shape={item.shape} color={item.color} />
              <span>{item.label}</span>
            </div>
          ))}
        </div>
      </div>

      {/* Callout: Observation Planes — anchored under the triangle column */}
      {!loading && planeCalloutPos && (
        <button
          onClick={() => setCalloutModal('observation-planes')}
          className="absolute z-10 group flex items-center gap-2 bg-slate-800/90 backdrop-blur border border-violet-500/40 rounded-full pl-2.5 pr-3.5 py-1.5 hover:border-violet-400 hover:bg-slate-700/90 transition-all duration-200"
          style={{ left: planeCalloutPos.x, top: planeCalloutPos.y, transform: 'translateX(-50%)' }}
        >
          <Info size={14} className="text-violet-400 group-hover:text-violet-300 transition-colors" />
          <span className="text-xs text-violet-300 group-hover:text-violet-200 font-[Quicksand] font-medium transition-colors whitespace-nowrap">Why 7 observation planes?</span>
        </button>
      )}

      {/* Callout Modal */}
      {calloutModal === 'observation-planes' && (
        <div className="absolute inset-0 z-40 flex items-center justify-center" onClick={() => setCalloutModal(null)}>
          <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" />
          <div
            className="relative bg-slate-800 border border-slate-600 rounded-2xl shadow-2xl max-w-lg w-full mx-4 animate-modal-in"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="px-6 pt-5 pb-4 border-b border-slate-700/50">
              <div className="flex items-start justify-between">
                <div>
                  <h3 className="text-lg font-semibold text-white font-[Quicksand]">The 7 Observation Planes</h3>
                  <p className="text-xs text-slate-400 font-[Quicksand] mt-0.5">Why AOD collects evidence from exactly these sources</p>
                </div>
                <button onClick={() => setCalloutModal(null)} className="text-slate-400 hover:text-white transition-colors p-1 -mr-1 -mt-1">
                  <X size={18} />
                </button>
              </div>
            </div>
            <div className="px-6 py-5 space-y-4 max-h-[60vh] overflow-y-auto">
              <p className="text-sm text-slate-300 font-[Quicksand] leading-relaxed">
                No single enterprise system has a complete picture of what software an organization actually uses. AOD solves this by collecting evidence from seven independent observation planes — each providing a different lens on the IT landscape.
              </p>
              <div className="space-y-3">
                {[
                  { name: 'Discovery', color: C.cyan, desc: 'Web traffic, SaaS login pages, and browser-observed applications. Catches shadow IT that no official system tracks.' },
                  { name: 'Identity Provider', color: C.violet, desc: 'SSO configurations, SCIM provisioning, and service principals from Okta, Azure AD, etc. The strongest governance signal — if it\'s in IdP, someone sanctioned it.' },
                  { name: 'CMDB', color: C.orange, desc: 'Configuration items from ServiceNow, Jira Assets, and similar. The official IT inventory — but often incomplete or stale.' },
                  { name: 'Cloud Inventory', color: C.green, desc: 'Resource inventories from AWS, Azure, and GCP. Reveals infrastructure-level dependencies invisible to other planes.' },
                  { name: 'Network', color: C.blue, desc: 'DNS records, proxy logs, and TLS certificates. Provides independent verification of what systems are actually communicating.' },
                  { name: 'Finance', color: C.amber, desc: 'Vendor contracts, purchase orders, and transaction records. If the company is paying for it, it exists — even if IT doesn\'t know about it.' },
                  { name: 'Endpoint', color: C.red, desc: 'Device management and installed application inventories. Reveals locally installed software that never touches the network.' },
                ].map((plane) => (
                  <div key={plane.name} className="flex gap-3">
                    <div className="mt-1.5 w-2.5 h-2.5 rounded-full flex-shrink-0" style={{ backgroundColor: plane.color }} />
                    <div>
                      <span className="text-sm font-semibold font-[Quicksand]" style={{ color: plane.color }}>{plane.name}</span>
                      <p className="text-xs text-slate-400 font-[Quicksand] leading-relaxed mt-0.5">{plane.desc}</p>
                    </div>
                  </div>
                ))}
              </div>
              <div className="border-t border-slate-700/50 pt-4">
                <p className="text-xs text-slate-400 font-[Quicksand] leading-relaxed italic">
                  The power is in the intersection. An application seen only in Discovery is shadow IT. One seen in IdP + CMDB + Finance is fully governed. AOD triangulates across all seven planes to classify every asset on the Governed / Shadow / Zombie spectrum.
                </p>
              </div>
            </div>
          </div>
        </div>
      )}


      {/* Details panel (right sidebar) */}
      {selectedNode && (
        <div className="absolute top-0 right-0 h-full w-80 bg-slate-800/95 backdrop-blur border-l border-slate-700 z-20 overflow-y-auto animate-slide-in">
          <div className="p-5">
            <div className="flex items-start justify-between mb-4">
              <div>
                <h2 className="text-lg font-semibold text-white font-[Quicksand]">{selectedNode.label}</h2>
                <span className="text-xs text-cyan-400 font-[Quicksand]">{selectedNode.stage}</span>
              </div>
              <button
                onClick={() => setSelectedNode(null)}
                className="text-slate-400 hover:text-white transition-colors p-1"
              >
                <X size={18} />
              </button>
            </div>

            <div className="mb-4">
              <span className="inline-block px-2 py-0.5 rounded text-xs font-[Quicksand] bg-slate-700 text-slate-300">
                {selectedNode.nodeType}
              </span>
            </div>

            <div className="space-y-2">
              <div className="text-xs text-slate-400 font-[Quicksand] font-semibold uppercase tracking-wider">Metadata</div>
              {Object.entries(selectedNode.metadata).map(([key, value]) => (
                <div key={key} className="flex justify-between items-baseline py-1.5 border-b border-slate-700/50">
                  <span className="text-xs text-slate-400 font-[Quicksand] capitalize">{key}</span>
                  <span className="text-sm text-white font-[Quicksand] text-right max-w-[60%]">{String(value)}</span>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* Slide-in animation */}
      <style>{`
        @keyframes slideIn {
          from { transform: translateX(100%); opacity: 0; }
          to   { transform: translateX(0);    opacity: 1; }
        }
        .animate-slide-in {
          animation: slideIn 0.2s ease-out;
        }
        @keyframes modalIn {
          from { transform: scale(0.95) translateY(8px); opacity: 0; }
          to   { transform: scale(1) translateY(0);      opacity: 1; }
        }
        .animate-modal-in {
          animation: modalIn 0.2s ease-out;
        }
      `}</style>
    </div>
  )
}

/* ─── Legend shape helper ─── */
function LegendShape({ shape, color }: { shape: string; color: string }) {
  const size = 12
  if (shape === 'line') {
    return (
      <svg width={size} height={4} viewBox="0 0 12 4">
        <line x1="0" y1="2" x2="12" y2="2" stroke={color} strokeWidth="2.5" />
        <polygon points="9,0 12,2 9,4" fill={color} />
      </svg>
    )
  }
  if (shape === 'hexagon') {
    return (
      <svg width={size} height={size} viewBox="0 0 12 12">
        <polygon points="3,0 9,0 12,6 9,12 3,12 0,6" fill={color} />
      </svg>
    )
  }
  if (shape === 'database') {
    return (
      <svg width={size} height={size} viewBox="0 0 12 14">
        <ellipse cx="6" cy="3" rx="5" ry="2.5" fill={color} />
        <rect x="1" y="3" width="10" height="8" fill={color} />
        <ellipse cx="6" cy="11" rx="5" ry="2.5" fill={color} opacity="0.7" />
      </svg>
    )
  }
  if (shape === 'diamond') {
    return (
      <svg width={size} height={size} viewBox="0 0 12 12">
        <polygon points="6,0 12,6 6,12 0,6" fill={color} />
      </svg>
    )
  }
  if (shape === 'triangle') {
    return (
      <svg width={size} height={size} viewBox="0 0 12 12">
        <polygon points="6,0 12,12 0,12" fill={color} />
      </svg>
    )
  }
  if (shape === 'triangleDown') {
    return (
      <svg width={size} height={size} viewBox="0 0 12 12">
        <polygon points="0,0 12,0 6,12" fill={color} />
      </svg>
    )
  }
  if (shape === 'rect') {
    return (
      <svg width={size} height={size} viewBox="0 0 12 12">
        <rect x="1" y="1" width="10" height="10" rx="2" fill="none" stroke={color} strokeWidth="2" />
        <rect x="3" y="3" width="6" height="6" rx="1" fill={color} opacity="0.3" />
      </svg>
    )
  }
  // circle
  return (
    <svg width={size} height={size} viewBox="0 0 12 12">
      <circle cx="6" cy="6" r="5" fill={color} />
    </svg>
  )
}
