import { useEffect, useRef, useState, useCallback } from 'react'
import { Network, DataSet } from 'vis-network/standalone'
import type { Node, Edge, Options } from 'vis-network/standalone'
import { Search, ZoomIn, ZoomOut, Maximize2, Lock, Unlock, X, ChevronDown } from 'lucide-react'

/* ─── Types ─── */
interface PipelineNode extends Node {
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

/* ─── Custom SOR node renderer (port of AAM drawSourceNode) ─── */
function drawSourceNode({ ctx, x, y, state: { selected, hover }, style, label }: any) {
  const sz = style.size
  const r = 4
  const fontSize = 12
  const lineHeight = fontSize * 1.3
  return {
    drawNode() {
      ctx.save()
      ctx.beginPath()
      ctx.moveTo(x - sz + r, y - sz)
      ctx.lineTo(x + sz - r, y - sz)
      ctx.quadraticCurveTo(x + sz, y - sz, x + sz, y - sz + r)
      ctx.lineTo(x + sz, y + sz - r)
      ctx.quadraticCurveTo(x + sz, y + sz, x + sz - r, y + sz)
      ctx.lineTo(x - sz + r, y + sz)
      ctx.quadraticCurveTo(x - sz, y + sz, x - sz, y + sz - r)
      ctx.lineTo(x - sz, y - sz + r)
      ctx.quadraticCurveTo(x - sz, y - sz, x - sz + r, y - sz)
      ctx.closePath()
      const grad = ctx.createLinearGradient(x, y - sz, x, y + sz)
      grad.addColorStop(0, C.slate800)
      grad.addColorStop(1, C.slate700)
      ctx.fillStyle = grad
      ctx.fill()
      if (selected) {
        ctx.shadowColor = 'rgba(34, 211, 238, 0.5)'
        ctx.shadowBlur = 15
        ctx.shadowOffsetX = 0
        ctx.shadowOffsetY = 0
      }
      ctx.strokeStyle = selected ? C.cyan : hover ? C.slate400 : C.slate600
      ctx.lineWidth = selected ? 2.5 : 1.5
      ctx.stroke()
      ctx.restore()
      if (label) {
        ctx.save()
        ctx.font = `${fontSize}px Quicksand, sans-serif`
        ctx.fillStyle = C.white
        ctx.textAlign = 'center'
        ctx.textBaseline = 'middle'
        const lines = label.split('\n')
        const startY = y + sz + 10 + lineHeight / 2
        for (let i = 0; i < lines.length; i++) {
          ctx.fillText(lines[i], x, startY + i * lineHeight)
        }
        ctx.restore()
      }
    },
    nodeDimensions: { width: sz * 2, height: sz * 2 },
  }
}

/* ─── Build graph data ─── */
function buildNodes(): PipelineNode[] {
  return [
    // Level 0 — Hub
    { id: 'aod', label: 'AOD\nDiscovery', level: 0, shape: 'diamond', color: { background: C.cyan, border: C.cyan }, font: { color: C.bgDark, size: 13, face: 'Quicksand' }, size: 28, stage: 'Hub', nodeType: 'diamond', metadata: { role: 'Discovery orchestrator', module: 'AOD' } },

    // Level 1 — Observation planes
    { id: 'plane-idp',     label: 'Identity\nProvider',   level: 1, shape: 'dot', color: { background: C.cyan, border: C.cyan },   size: 14, stage: 'Observation', nodeType: 'dot', metadata: { type: 'IdP',     examples: 'Okta, Azure AD',     tier: 'Tier 2' } },
    { id: 'plane-network', label: 'Network\nTraffic',     level: 1, shape: 'dot', color: { background: C.cyan, border: C.cyan },   size: 14, stage: 'Observation', nodeType: 'dot', metadata: { type: 'Network', examples: 'DNS, proxy logs',   tier: 'Tier 2' } },
    { id: 'plane-cloud',   label: 'Cloud\nInventory',     level: 1, shape: 'dot', color: { background: C.cyan, border: C.cyan },   size: 14, stage: 'Observation', nodeType: 'dot', metadata: { type: 'Cloud',   examples: 'AWS, Azure, GCP',   tier: 'Tier 2' } },
    { id: 'plane-finance', label: 'Finance\nRecords',     level: 1, shape: 'dot', color: { background: C.orange, border: C.orange }, size: 14, stage: 'Observation', nodeType: 'dot', metadata: { type: 'Finance', examples: 'Invoices, POs',     tier: 'Tier 2' } },
    { id: 'plane-browser', label: 'Browser\nTelemetry',   level: 1, shape: 'dot', color: { background: C.cyan, border: C.cyan },   size: 14, stage: 'Observation', nodeType: 'dot', metadata: { type: 'Browser', examples: 'Extension data',    tier: 'Tier 2' } },
    { id: 'plane-cmdb',    label: 'CMDB\nRecords',        level: 1, shape: 'dot', color: { background: C.cyan, border: C.cyan },   size: 14, stage: 'Observation', nodeType: 'dot', metadata: { type: 'CMDB',    examples: 'ServiceNow, Jira',  tier: 'Tier 1' } },
    { id: 'plane-catalog', label: 'Fabric Plane\nCatalog', level: 1, shape: 'dot', color: { background: C.orange, border: C.orange }, size: 14, stage: 'Observation', nodeType: 'dot', metadata: { type: 'Catalog', examples: 'MuleSoft, Kong',    tier: 'Tier 1' } },

    // Level 2 — Ingested
    { id: 'ingested', label: 'Ingested\n448 observations', level: 2, shape: 'dot', color: { background: C.cyan, border: C.cyan }, size: 20, stage: 'Ingestion', nodeType: 'dot', metadata: { count: 448, description: 'Raw evidence collected from all observation planes' } },

    // Level 3 — Validated / Rejected
    { id: 'validated', label: 'Validated\n101', level: 3, shape: 'dot', color: { background: C.cyan, border: C.cyan }, size: 18, stage: 'Validation', nodeType: 'dot', metadata: { count: 101, description: 'Passed format checks and deduplication' } },
    { id: 'rejected',  label: 'Rejected\n3',   level: 3, shape: 'dot', color: { background: C.red, border: C.red },   size: 12, stage: 'Validation', nodeType: 'dot', metadata: { count: 3, description: 'Failed validation — format errors or duplicates' } },

    // Level 4 — Cataloged
    { id: 'cataloged', label: 'Cataloged\n98', level: 4, shape: 'dot', color: { background: C.cyan700, border: C.cyan700 }, size: 18, stage: 'Catalog', nodeType: 'dot', metadata: { count: 98, description: 'Confirmed assets admitted to catalog' } },

    // Level 5 — Classifications + Handoff hub
    { id: 'class-shadow',   label: 'Shadow\n12',          level: 5, shape: 'triangle', color: { background: C.purple, border: C.purple }, size: 16, stage: 'Classification', nodeType: 'triangle', metadata: { count: 12, description: 'In use but NOT governed — no SSO, not in CMDB' } },
    { id: 'class-zombie',   label: 'Zombie\n8',           level: 5, shape: 'triangle', color: { background: C.green, border: C.green },   size: 16, stage: 'Classification', nodeType: 'triangle', metadata: { count: 8, description: 'Governed but inactive 90+ days' } },
    { id: 'class-security', label: 'Security\nRisk 5',    level: 5, shape: 'triangle', color: { background: C.amber, border: C.amber },   size: 16, stage: 'Classification', nodeType: 'triangle', metadata: { count: 5, description: 'Identity gaps, shadow spending, data conflicts' } },
    { id: 'class-governed', label: 'Governed\n73',        level: 5, shape: 'triangle', color: { background: C.blue, border: C.blue },     size: 16, stage: 'Classification', nodeType: 'triangle', metadata: { count: 73, description: 'Fully governed, compliant assets' } },
    { id: 'handoff-aam',    label: 'Handoff\n→ AAM',      level: 5, shape: 'diamond',  color: { background: C.orange, border: C.orange },  size: 20, stage: 'Handoff', nodeType: 'diamond', metadata: { description: 'ConnectionCandidate handoff to AAM', target: 'AAM module' } },

    // Level 6 — Fabric planes
    { id: 'fabric-ipaas',   label: 'iPaaS\nWorkato',         level: 6, shape: 'diamond', color: { background: C.cyan, border: C.cyan },     size: 16, stage: 'Fabric Plane', nodeType: 'diamond', metadata: { vendor: 'Workato', type: 'iPaaS',       pipes: 14 } },
    { id: 'fabric-event',   label: 'Event Bus\nEventBridge', level: 6, shape: 'diamond', color: { background: C.violet, border: C.violet }, size: 16, stage: 'Fabric Plane', nodeType: 'diamond', metadata: { vendor: 'AWS', type: 'Event Bus',        pipes: 8 } },
    { id: 'fabric-api',     label: 'API Gateway\nKong',      level: 6, shape: 'diamond', color: { background: C.orange, border: C.orange }, size: 16, stage: 'Fabric Plane', nodeType: 'diamond', metadata: { vendor: 'Kong', type: 'API Gateway',     pipes: 22 } },
    { id: 'fabric-data',    label: 'Data Mesh\nSnowflake',   level: 6, shape: 'diamond', color: { background: C.green, border: C.green },   size: 16, stage: 'Fabric Plane', nodeType: 'diamond', metadata: { vendor: 'Snowflake', type: 'Data Mesh',  pipes: 11 } },

    // Level 7 — SOR nodes (custom renderer)
    { id: 'sor-salesforce', label: 'Salesforce',    level: 7, shape: 'custom', ctxRenderer: drawSourceNode, color: { background: C.slate800, border: C.amber }, size: 22, stage: 'System of Record', nodeType: 'sor', metadata: { vendor: 'Salesforce', category: 'CRM',      status: 'Connected' } },
    { id: 'sor-sap',        label: 'SAP',           level: 7, shape: 'custom', ctxRenderer: drawSourceNode, color: { background: C.slate800, border: C.amber }, size: 22, stage: 'System of Record', nodeType: 'sor', metadata: { vendor: 'SAP', category: 'ERP',            status: 'Connected' } },
    { id: 'sor-okta',       label: 'Okta',          level: 7, shape: 'custom', ctxRenderer: drawSourceNode, color: { background: C.slate800, border: C.amber }, size: 22, stage: 'System of Record', nodeType: 'sor', metadata: { vendor: 'Okta', category: 'Identity',       status: 'Connected' } },
    { id: 'sor-workday',    label: 'Workday',       level: 7, shape: 'custom', ctxRenderer: drawSourceNode, color: { background: C.slate800, border: C.amber }, size: 22, stage: 'System of Record', nodeType: 'sor', metadata: { vendor: 'Workday', category: 'HCM',        status: 'Connected' } },
    { id: 'sor-snowflake',  label: 'Snowflake',     level: 7, shape: 'custom', ctxRenderer: drawSourceNode, color: { background: C.slate800, border: C.amber }, size: 22, stage: 'System of Record', nodeType: 'sor', metadata: { vendor: 'Snowflake', category: 'Data',      status: 'Connected' } },
    { id: 'sor-servicenow', label: 'ServiceNow',    level: 7, shape: 'custom', ctxRenderer: drawSourceNode, color: { background: C.slate800, border: C.amber }, size: 22, stage: 'System of Record', nodeType: 'sor', metadata: { vendor: 'ServiceNow', category: 'ITSM',    status: 'Connected' } },
  ]
}

function buildEdges(): Edge[] {
  return [
    // Hub → Observation planes
    { from: 'aod', to: 'plane-idp',     width: 2 },
    { from: 'aod', to: 'plane-network', width: 2 },
    { from: 'aod', to: 'plane-cloud',   width: 2 },
    { from: 'aod', to: 'plane-finance', width: 2 },
    { from: 'aod', to: 'plane-browser', width: 2 },
    { from: 'aod', to: 'plane-cmdb',    width: 2 },
    { from: 'aod', to: 'plane-catalog', width: 2 },

    // Observation planes → Ingested
    { from: 'plane-idp',     to: 'ingested', width: 1.5 },
    { from: 'plane-network', to: 'ingested', width: 1.5 },
    { from: 'plane-cloud',   to: 'ingested', width: 1.5 },
    { from: 'plane-finance', to: 'ingested', width: 1.5 },
    { from: 'plane-browser', to: 'ingested', width: 1.5 },
    { from: 'plane-cmdb',    to: 'ingested', width: 1.5 },
    { from: 'plane-catalog', to: 'ingested', width: 1.5 },

    // Ingested → Validated / Rejected
    { from: 'ingested', to: 'validated', width: 2 },
    { from: 'ingested', to: 'rejected',  width: 1.5, color: { color: C.red, opacity: 0.8 } },

    // Validated → Cataloged
    { from: 'validated', to: 'cataloged', width: 2 },

    // Cataloged → Classifications
    { from: 'cataloged', to: 'class-shadow',   width: 1.5 },
    { from: 'cataloged', to: 'class-zombie',   width: 1.5 },
    { from: 'cataloged', to: 'class-security', width: 1.5 },
    { from: 'cataloged', to: 'class-governed', width: 1.5 },

    // Classifications → Handoff (dashed)
    { from: 'class-shadow',   to: 'handoff-aam', width: 1.5, dashes: [6, 4] },
    { from: 'class-zombie',   to: 'handoff-aam', width: 1.5, dashes: [6, 4] },
    { from: 'class-security', to: 'handoff-aam', width: 1.5, dashes: [6, 4] },
    { from: 'class-governed', to: 'handoff-aam', width: 1.5, dashes: [6, 4] },

    // Handoff → Fabric planes
    { from: 'handoff-aam', to: 'fabric-ipaas', width: 2 },
    { from: 'handoff-aam', to: 'fabric-event', width: 2 },
    { from: 'handoff-aam', to: 'fabric-api',   width: 2 },
    { from: 'handoff-aam', to: 'fabric-data',  width: 2 },

    // Fabric planes → SORs
    { from: 'fabric-ipaas', to: 'sor-salesforce', width: 1.5 },
    { from: 'fabric-ipaas', to: 'sor-workday',    width: 1.5 },
    { from: 'fabric-event', to: 'sor-sap',        width: 1.5 },
    { from: 'fabric-event', to: 'sor-snowflake',  width: 1.5 },
    { from: 'fabric-api',   to: 'sor-okta',       width: 1.5 },
    { from: 'fabric-api',   to: 'sor-servicenow', width: 1.5 },
    { from: 'fabric-data',  to: 'sor-snowflake',  width: 1.5 },
    { from: 'fabric-data',  to: 'sor-salesforce', width: 1.5 },
  ]
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
            levelSeparation: 200,
            nodeSpacing: 80,
            treeSpacing: 100,
            sortMethod: 'directed',
          },
        },
        physics: {
          enabled: true,
          hierarchicalRepulsion: {
            centralGravity: 0.0,
            springLength: 150,
            springConstant: 0.01,
            nodeDistance: 120,
          },
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
      smooth: { enabled: true, type: 'continuous', roundness: 0.2 },
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
  { shape: 'diamond', color: C.cyan,   label: 'Hub / Fabric' },
  { shape: 'circle',  color: C.cyan,   label: 'Flow stage' },
  { shape: 'triangle', color: C.purple, label: 'Classification' },
  { shape: 'rect',    color: C.amber,  label: 'System of Record' },
]

/* ─── Component ─── */
export default function PipelineTopology() {
  const containerRef = useRef<HTMLDivElement>(null)
  const networkRef = useRef<Network | null>(null)
  const nodesRef = useRef<DataSet<PipelineNode> | null>(null)
  const [selectedNode, setSelectedNode] = useState<DetailsData | null>(null)
  const [searchTerm, setSearchTerm] = useState('')
  const [layout, setLayout] = useState<LayoutKey>('hierarchical')
  const [physicsEnabled, setPhysicsEnabled] = useState(true)
  const [layoutOpen, setLayoutOpen] = useState(false)

  // Initialize network
  useEffect(() => {
    if (!containerRef.current) return

    const nodes = new DataSet<PipelineNode>(buildNodes())
    const edges = new DataSet<Edge>(buildEdges())
    nodesRef.current = nodes

    const options: Options = {
      ...getBaseOptions(),
      ...getLayoutOptions('hierarchical'),
    }

    const network = new Network(containerRef.current, { nodes, edges }, options)
    networkRef.current = network

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

    // Stabilize then disable physics for hierarchical
    network.once('stabilizationIterationsDone', () => {
      if (layout === 'hierarchical') {
        network.setOptions({ physics: { enabled: false } })
        setPhysicsEnabled(false)
      }
    })

    return () => {
      network.destroy()
      networkRef.current = null
      nodesRef.current = null
    }
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  // Layout changes
  useEffect(() => {
    const net = networkRef.current
    if (!net) return
    const opts = getLayoutOptions(layout)
    net.setOptions(opts as any)

    if (layout === 'hierarchical') {
      net.once('stabilizationIterationsDone', () => {
        net.setOptions({ physics: { enabled: false } })
        setPhysicsEnabled(false)
      })
    } else {
      setPhysicsEnabled(true)
    }
  }, [layout])

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
            onClick={() => setLayoutOpen(!layoutOpen)}
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
          {legendItems.map((item) => (
            <div key={item.label} className="flex items-center gap-2 text-xs text-white font-[Quicksand]">
              <LegendShape shape={item.shape} color={item.color} />
              <span>{item.label}</span>
            </div>
          ))}
        </div>
      </div>

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
      `}</style>
    </div>
  )
}

/* ─── Legend shape helper ─── */
function LegendShape({ shape, color }: { shape: string; color: string }) {
  const size = 12
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
