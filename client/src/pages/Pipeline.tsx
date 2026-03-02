import { useEffect, useRef, useCallback } from "react";
import gsap from "gsap";
import { MotionPathPlugin } from "gsap/MotionPathPlugin";

gsap.registerPlugin(MotionPathPlugin);

/* ─── hardcoded data ─── */

const PLANES = [
  { name: "Discovery",  count: 448,  color: "text-cyan-400",   accent: "#22d3ee" },
  { name: "IDP",        count: 84,   color: "text-cyan-400",   accent: "#22d3ee" },
  { name: "CMDB",       count: 78,   color: "text-cyan-400",   accent: "#22d3ee" },
  { name: "Cloud",      count: 395,  color: "text-cyan-400",   accent: "#22d3ee" },
  { name: "Endpoint",   count: 395,  color: "text-orange-400", accent: "#fb923c" },
  { name: "Network",    count: 3590, color: "text-orange-400", accent: "#fb923c" },
  { name: "Finance",    count: 247,  color: "text-orange-400", accent: "#fb923c" },
];

const TOTAL_OBS = 5237;

const FUNNEL = [
  { label: "Ingested",  value: 448, width: "100%",  color: "bg-cyan-500" },
  { label: "Validated", value: 101, width: "55%",   color: "bg-cyan-600" },
  { label: "Rejected",  value: 3,   width: "12%",   color: "bg-red-500" },
  { label: "Cataloged", value: 98,  width: "50%",   color: "bg-cyan-700" },
];

const CLASSIFICATIONS = [
  { name: "Shadow",          total: 29,  candidates: 29, color: "text-purple-400", border: "border-purple-500/40", bg: "bg-purple-500/10" },
  { name: "Zombie",          total: 11,  candidates: 11, color: "text-green-400",  border: "border-green-500/40",  bg: "bg-green-500/10" },
  { name: "Security Risks",  total: 97,  candidates: 40, color: "text-amber-400",  border: "border-amber-500/40",  bg: "bg-amber-500/10" },
  { name: "Governance",      total: 154, candidates: 84, color: "text-blue-400",   border: "border-blue-500/40",   bg: "bg-blue-500/10" },
];

const FABRIC_PLANES = [
  { name: "Workato",      status: "HEALTHY" },
  { name: "Apigee",       status: "HEALTHY" },
  { name: "EventBridge",  status: "HEALTHY" },
  { name: "Snowflake",    status: "HEALTHY" },
];

const SORS = [
  { name: "Dynamics",    confidence: "MED"  },
  { name: "NetSuite",    confidence: "HIGH" },
  { name: "BambooHR",    confidence: "HIGH" },
  { name: "QuickBooks",  confidence: "HIGH" },
  { name: "Okta",        confidence: "MED"  },
  { name: "Freshservice", confidence: "HIGH" },
];

const CANDIDATES = [
  { name: "Shadow",     count: 29, of: null, color: "text-purple-400" },
  { name: "Zombie",     count: 11, of: null, color: "text-green-400" },
  { name: "Security",   count: 40, of: 97,   color: "text-amber-400" },
  { name: "Governance", count: 84, of: 154,  color: "text-blue-400" },
];

/* ─── component ─── */

export default function Pipeline() {
  const rootRef = useRef<HTMLDivElement>(null);
  const svgRef = useRef<SVGSVGElement>(null);
  const tlRef = useRef<gsap.core.Timeline | null>(null);

  /* refs for countup targets */
  const totalRef = useRef<HTMLSpanElement>(null);
  const planeCountRefs = useRef<(HTMLSpanElement | null)[]>([]);
  const funnelCountRefs = useRef<(HTMLSpanElement | null)[]>([]);
  const classCountRefs = useRef<(HTMLSpanElement | null)[]>([]);

  /* refs for connection path endpoints */
  const stage1Ref = useRef<HTMLDivElement>(null);
  const stage2Ref = useRef<HTMLDivElement>(null);
  const stage3Ref = useRef<HTMLDivElement>(null);

  const setPlaneRef = useCallback((i: number) => (el: HTMLSpanElement | null) => {
    planeCountRefs.current[i] = el;
  }, []);
  const setFunnelRef = useCallback((i: number) => (el: HTMLSpanElement | null) => {
    funnelCountRefs.current[i] = el;
  }, []);
  const setClassRef = useCallback((i: number) => (el: HTMLSpanElement | null) => {
    classCountRefs.current[i] = el;
  }, []);

  useEffect(() => {
    if (!rootRef.current || !svgRef.current) return;

    const root = rootRef.current;
    const svg = svgRef.current;

    /* size SVG to match container */
    const rect = root.getBoundingClientRect();
    svg.setAttribute("viewBox", `0 0 ${rect.width} ${rect.height}`);

    /* compute connection paths between stages */
    const s1 = stage1Ref.current;
    const s2 = stage2Ref.current;
    const s3 = stage3Ref.current;
    if (!s1 || !s2 || !s3) return;

    const rootRect = root.getBoundingClientRect();
    const s1r = s1.getBoundingClientRect();
    const s2r = s2.getBoundingClientRect();
    const s3r = s3.getBoundingClientRect();

    const x = (r: DOMRect) => r.left - rootRect.left;
    const y = (r: DOMRect) => r.top - rootRect.top;
    const cy = (r: DOMRect) => y(r) + r.height / 2;

    /* path 1→2 */
    const p1x1 = x(s1r) + s1r.width;
    const p1y1 = cy(s1r);
    const p1x2 = x(s2r);
    const p1y2 = cy(s2r);
    const cp1 = (p1x2 - p1x1) * 0.4;
    const path1d = `M${p1x1},${p1y1} C${p1x1 + cp1},${p1y1} ${p1x2 - cp1},${p1y2} ${p1x2},${p1y2}`;

    /* path 2→3 */
    const p2x1 = x(s2r) + s2r.width;
    const p2y1 = cy(s2r);
    const p2x2 = x(s3r);
    const p2y2 = cy(s3r);
    const cp2 = (p2x2 - p2x1) * 0.4;
    const path2d = `M${p2x1},${p2y1} C${p2x1 + cp2},${p2y1} ${p2x2 - cp2},${p2y2} ${p2x2},${p2y2}`;

    /* set path d attributes */
    const pathEl1 = svg.querySelector("#conn-path-1") as SVGPathElement;
    const pathEl2 = svg.querySelector("#conn-path-2") as SVGPathElement;
    if (pathEl1) pathEl1.setAttribute("d", path1d);
    if (pathEl2) pathEl2.setAttribute("d", path2d);

    /* measure path lengths for dash animation */
    const len1 = pathEl1?.getTotalLength() ?? 400;
    const len2 = pathEl2?.getTotalLength() ?? 400;

    gsap.set(pathEl1, { strokeDasharray: len1, strokeDashoffset: len1 });
    gsap.set(pathEl2, { strokeDasharray: len2, strokeDashoffset: len2 });

    /* build timeline */
    const tl = gsap.timeline({ defaults: { ease: "power2.out" } });
    tlRef.current = tl;

    /* 0–0.8s: Stage 1 plane nodes stagger in */
    tl.fromTo(
      root.querySelectorAll(".plane-node"),
      { opacity: 0, x: -30 },
      { opacity: 1, x: 0, duration: 0.5, stagger: 0.1 },
      0
    );

    /* plane count-ups */
    planeCountRefs.current.forEach((el, i) => {
      if (!el) return;
      el.textContent = "0";
      tl.to(el, {
        textContent: PLANES[i].count,
        snap: { textContent: 1 },
        duration: 1.2,
      }, 0.1 + i * 0.1);
    });

    /* total count-up */
    if (totalRef.current) {
      totalRef.current.textContent = "0";
      tl.to(totalRef.current, {
        textContent: TOTAL_OBS,
        snap: { textContent: 1 },
        duration: 1.5,
      }, 0.2);
    }

    /* 0.8–1.5s: SVG paths draw in */
    tl.to(pathEl1, { strokeDashoffset: 0, duration: 0.7, ease: "power1.inOut" }, 0.8);

    /* particles along path 1 */
    const particles1 = svg.querySelectorAll(".particle-1");
    particles1.forEach((p, i) => {
      tl.to(p, {
        motionPath: { path: pathEl1, align: pathEl1, alignOrigin: [0.5, 0.5] },
        duration: 1.8,
        delay: i * 0.35,
        repeat: -1,
        ease: "none",
      }, 1.0);
    });

    /* 1.5–2.5s: Stage 2 funnel bars scale in */
    tl.fromTo(
      root.querySelectorAll(".funnel-bar"),
      { scaleX: 0, transformOrigin: "left center" },
      { scaleX: 1, duration: 0.6, stagger: 0.15 },
      1.5
    );

    funnelCountRefs.current.forEach((el, i) => {
      if (!el) return;
      el.textContent = "0";
      tl.to(el, {
        textContent: FUNNEL[i].value,
        snap: { textContent: 1 },
        duration: 1.0,
      }, 1.5 + i * 0.15);
    });

    /* 2.5–3.2s: Classification nodes fade in */
    tl.fromTo(
      root.querySelectorAll(".class-node"),
      { opacity: 0, y: 15 },
      { opacity: 1, y: 0, duration: 0.5, stagger: 0.12 },
      2.5
    );

    classCountRefs.current.forEach((el, i) => {
      if (!el) return;
      el.textContent = "0";
      tl.to(el, {
        textContent: CLASSIFICATIONS[i].total,
        snap: { textContent: 1 },
        duration: 1.0,
      }, 2.6 + i * 0.12);
    });

    /* 3.2–4.0s: Path 2 draws, particles stream Stage 2→3 */
    tl.to(pathEl2, { strokeDashoffset: 0, duration: 0.7, ease: "power1.inOut" }, 3.2);

    const particles2 = svg.querySelectorAll(".particle-2");
    particles2.forEach((p, i) => {
      tl.to(p, {
        motionPath: { path: pathEl2, align: pathEl2, alignOrigin: [0.5, 0.5] },
        duration: 1.8,
        delay: i * 0.35,
        repeat: -1,
        ease: "none",
      }, 3.5);
    });

    /* 4.0–5.0s: Stage 3 clusters appear */
    tl.fromTo(
      root.querySelectorAll(".stage3-node"),
      { opacity: 0, x: 20 },
      { opacity: 1, x: 0, duration: 0.5, stagger: 0.08 },
      4.0
    );

    return () => {
      tl.kill();
    };
  }, []);

  return (
    <div
      id="pipeline-root"
      ref={rootRef}
      className="relative min-h-screen bg-slate-950 text-slate-50 font-sans overflow-x-auto"
    >
      {/* SVG Overlay */}
      <svg
        ref={svgRef}
        className="absolute inset-0 w-full h-full pointer-events-none z-10"
        preserveAspectRatio="none"
      >
        <defs>
          <filter id="glow">
            <feGaussianBlur stdDeviation="3" result="blur" />
            <feMerge>
              <feMergeNode in="blur" />
              <feMergeNode in="SourceGraphic" />
            </feMerge>
          </filter>
          <linearGradient id="cyanGrad" x1="0%" y1="0%" x2="100%" y2="0%">
            <stop offset="0%" stopColor="#0bcad9" stopOpacity="0.6" />
            <stop offset="100%" stopColor="#22d3ee" stopOpacity="0.3" />
          </linearGradient>
        </defs>

        {/* connection paths */}
        <path id="conn-path-1" d="" fill="none" stroke="url(#cyanGrad)" strokeWidth="2" filter="url(#glow)" />
        <path id="conn-path-2" d="" fill="none" stroke="url(#cyanGrad)" strokeWidth="2" filter="url(#glow)" />

        {/* particles for path 1 */}
        {[0, 1, 2].map(i => (
          <circle key={`p1-${i}`} className="particle-1" r="2.5" fill="#0bcad9" opacity="0.7" filter="url(#glow)" />
        ))}
        {/* particles for path 2 */}
        {[0, 1, 2].map(i => (
          <circle key={`p2-${i}`} className="particle-2" r="2.5" fill="#0bcad9" opacity="0.7" filter="url(#glow)" />
        ))}
      </svg>

      {/* 3-column layout */}
      <div className="relative z-20 min-w-[1200px] flex items-start gap-6 p-8 pt-6">

        {/* ── Stage 1: Discovery ── */}
        <div ref={stage1Ref} className="flex-1 min-w-[320px] max-w-[380px] space-y-3">
          <div className="mb-4">
            <h2 className="text-lg font-bold text-white tracking-wide">Stage 1 — Discovery</h2>
            <p className="text-xs text-slate-500 mt-1">Observation Planes</p>
          </div>

          {PLANES.map((p, i) => (
            <div
              key={p.name}
              className="plane-node flex items-center justify-between px-4 py-3 bg-slate-900/50 rounded-lg border border-slate-800 hover:border-cyan-800/50 hover:shadow-[0_0_15px_rgba(11,202,217,0.08)] transition-all duration-300 opacity-0"
            >
              <div className="flex items-center gap-3">
                <div className="w-2 h-2 rounded-full" style={{ backgroundColor: p.accent, boxShadow: `0 0 8px ${p.accent}60` }} />
                <span className="text-sm font-medium text-slate-300">{p.name}</span>
              </div>
              <span ref={setPlaneRef(i)} className={`text-sm font-bold tabular-nums ${p.color}`}>
                {p.count}
              </span>
            </div>
          ))}

          <div className="mt-4 px-4 py-3 bg-slate-800/30 rounded-lg border border-slate-700/50 text-center">
            <span className="text-xs text-slate-500 uppercase tracking-wider">Total Observations</span>
            <div className="text-2xl font-bold text-cyan-400 tabular-nums mt-1">
              <span ref={totalRef}>{TOTAL_OBS}</span>
            </div>
          </div>
        </div>

        {/* ── Stage 2: Classification ── */}
        <div ref={stage2Ref} className="flex-1 min-w-[340px] max-w-[420px] space-y-5">
          <div className="mb-4">
            <h2 className="text-lg font-bold text-white tracking-wide">Stage 2 — Classification</h2>
            <p className="text-xs text-slate-500 mt-1">Lifecycle Funnel</p>
          </div>

          {/* Funnel */}
          <div className="space-y-3 bg-slate-900/30 rounded-lg border border-slate-800 p-4">
            {FUNNEL.map((f, i) => (
              <div key={f.label} className="space-y-1">
                <div className="flex justify-between text-xs">
                  <span className={`font-medium ${f.label === "Rejected" ? "text-red-400" : "text-slate-400"}`}>
                    {f.label}
                  </span>
                  <span ref={setFunnelRef(i)} className={`font-bold tabular-nums ${f.label === "Rejected" ? "text-red-400" : "text-cyan-400"}`}>
                    {f.value}
                  </span>
                </div>
                <div className="h-2.5 bg-slate-800 rounded-full overflow-hidden">
                  <div
                    className={`funnel-bar h-full rounded-full ${f.color}`}
                    style={{ width: f.width, transformOrigin: "left center" }}
                  />
                </div>
              </div>
            ))}
          </div>

          {/* Classification breakdown */}
          <div>
            <p className="text-xs text-slate-500 mb-3 uppercase tracking-wider">Classification Breakdown</p>
            <div className="grid grid-cols-2 gap-2">
              {CLASSIFICATIONS.map((c, i) => (
                <div
                  key={c.name}
                  className={`class-node px-3 py-3 rounded-lg border ${c.border} ${c.bg} opacity-0 hover:shadow-[0_0_12px_rgba(11,202,217,0.06)] transition-all duration-300`}
                >
                  <div className={`text-xs font-medium ${c.color} mb-1`}>{c.name}</div>
                  <div className="flex items-baseline gap-1">
                    <span ref={setClassRef(i)} className={`text-lg font-bold tabular-nums ${c.color}`}>
                      {c.total}
                    </span>
                    <span className="text-[10px] text-slate-500">found</span>
                  </div>
                  <div className="text-[10px] text-slate-500 mt-0.5">
                    {c.candidates} candidate{c.candidates !== 1 ? "s" : ""}
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* ── Stage 3: Handoff → AAM ── */}
        <div ref={stage3Ref} className="flex-1 min-w-[320px] max-w-[380px] space-y-5">
          <div className="mb-4">
            <h2 className="text-lg font-bold text-white tracking-wide">Stage 3 — Handoff → AAM</h2>
            <p className="text-xs text-slate-500 mt-1">Connection Readiness</p>
          </div>

          {/* Fabric Planes */}
          <div>
            <p className="text-xs text-slate-500 mb-2 uppercase tracking-wider">Fabric Planes</p>
            <div className="grid grid-cols-2 gap-2">
              {FABRIC_PLANES.map(fp => (
                <div
                  key={fp.name}
                  className="stage3-node flex items-center justify-between px-3 py-2.5 bg-slate-900/50 rounded-lg border border-slate-800 opacity-0"
                >
                  <span className="text-xs font-medium text-slate-300">{fp.name}</span>
                  <span className="text-[10px] font-bold text-green-400 bg-green-500/10 px-1.5 py-0.5 rounded">
                    {fp.status}
                  </span>
                </div>
              ))}
            </div>
          </div>

          {/* Systems of Record */}
          <div>
            <p className="text-xs text-slate-500 mb-2 uppercase tracking-wider">Systems of Record</p>
            <div className="grid grid-cols-2 gap-2">
              {SORS.map(s => (
                <div
                  key={s.name}
                  className="stage3-node flex items-center justify-between px-3 py-2.5 bg-slate-900/50 rounded-lg border border-slate-800 opacity-0"
                >
                  <span className="text-xs font-medium text-slate-300">{s.name}</span>
                  <span className={`text-[10px] font-bold px-1.5 py-0.5 rounded ${
                    s.confidence === "HIGH"
                      ? "text-green-400 bg-green-500/10"
                      : "text-amber-400 bg-amber-500/10"
                  }`}>
                    {s.confidence}
                  </span>
                </div>
              ))}
            </div>
          </div>

          {/* Connection Candidates */}
          <div>
            <p className="text-xs text-slate-500 mb-2 uppercase tracking-wider">Connection Candidates</p>
            <div className="flex flex-wrap gap-2">
              {CANDIDATES.map(c => (
                <div
                  key={c.name}
                  className={`stage3-node inline-flex items-center gap-1.5 px-3 py-2 bg-slate-900/50 rounded-lg border border-slate-800 opacity-0`}
                >
                  <span className={`text-xs font-medium ${c.color}`}>{c.name}</span>
                  <span className={`text-xs font-bold tabular-nums ${c.color}`}>
                    {c.count}{c.of ? <span className="text-slate-500 font-normal">/{c.of}</span> : null}
                  </span>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
