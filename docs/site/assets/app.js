/**
 * Interactive DeepWiki-style Architecture Portal for Azure Functions Python Worker.
 * Renders:
 *  - Evolution Overview (side-by-side matrix + 4-repo map)
 *  - 4-Repo Ecosystem Topology + 3 Era Architecture Pages (<=3.12, 3.13-3.14, 3.15+ R2P2)
 *  - Auto-laid-out Compound Swimlane SVG Canvas (pan/zoom, LR/TB toggle, animated packet traces)
 *  - Interactive Multi-Actor Sequence Diagram
 *  - Exportable Deterministic Mermaid Source
 *  - Dependency Isolation & Auto-Update CI Pipeline Inspector
 */
(function () {
  const graph = window.__ARCH_GRAPH__;
  if (!graph) return;

  const EDGE_PALETTE = {
    "grpc-wire": { color: "#38bdf8", label: "gRPC Wire (FunctionRpc)" },
    "thread-queue": { color: "#a78bfa", label: "Thread / Async Channel" },
    "inproc-contract": { color: "#34d399", label: "In-Proc Python Contract" },
    "pyo3-hot": { color: "#fb923c", label: "PyO3 Hot Tuple FFI" },
    "pyo3-control": { color: "#f472b6", label: "PyO3 Control / Extensions" },
    "syspath-mutation": { color: "#fbbf24", label: "Import / EntryPoint" },
    "exec-dispatch": { color: "#60a5fa", label: "Handler Execution" },
  };

  const CONTAINER_TONES = {
    proto: { stroke: "#fbbf24", fill: "rgba(120, 53, 15, 0.14)", head: "rgba(146, 64, 14, 0.32)", text: "#fde68a" },
    host: { stroke: "#38bdf8", fill: "rgba(12, 74, 110, 0.14)", head: "rgba(14, 116, 144, 0.30)", text: "#bae6fd" },
    python: { stroke: "#64748b", fill: "rgba(15, 23, 42, 0.50)", head: "rgba(30, 41, 59, 0.80)", text: "#e2e8f0" },
    "rust-proc": { stroke: "#fb923c", fill: "rgba(67, 20, 7, 0.22)", head: "rgba(124, 45, 18, 0.42)", text: "#fed7aa" },
    rust: { stroke: "#fb923c", fill: "rgba(124, 45, 18, 0.16)", head: "rgba(154, 52, 18, 0.36)", text: "#ffedd5" },
    transport: { stroke: "#a78bfa", fill: "rgba(76, 29, 149, 0.15)", head: "rgba(91, 33, 182, 0.32)", text: "#ddd6fe" },
    bridge: { stroke: "#f472b6", fill: "rgba(131, 24, 67, 0.16)", head: "rgba(157, 23, 77, 0.34)", text: "#fbcfe8" },
    runtime: { stroke: "#34d399", fill: "rgba(6, 78, 59, 0.16)", head: "rgba(6, 95, 70, 0.34)", text: "#a7f3d0" },
    lib: { stroke: "#34d399", fill: "rgba(6, 78, 59, 0.12)", head: "rgba(4, 120, 87, 0.28)", text: "#6ee7b7" },
    ext: { stroke: "#c084fc", fill: "rgba(88, 28, 135, 0.16)", head: "rgba(107, 33, 168, 0.34)", text: "#e9d5ff" },
  };

  const state = {
    page: "py315_r2p2", // overview | ecosystem | py312 | py313_314 | py315_r2p2 | dep_iso | pipeline
    diagramMode: "topology", // topology | sequence | compare_phase | mermaid
    orientation: "LR", // LR | TB
    phaseId: "init", // all | init | specialization | metadata | function_load | invocation | worker_status | worker_logs
    flowId: "idle",
    stepIdx: -1, // -1 = full phase view; 0..N-1 = specific step hop
    selectedNodeId: null,
    selectedEdgeId: null,
    zoom: 0.86,
    panX: 18,
    panY: 16,
    copied: false,
    sidebarCollapsed: false,
    mobileMenuOpen: false,
  };

  function syncHashToState() {
    const raw = (window.location.hash || "").replace(/^#\/?/, "");
    if (!raw) return;
    const [p, ph, m] = raw.split("/");
    if (p) state.page = p;
    if (ph) state.phaseId = ph;
    if (m) state.diagramMode = m;
  }

  function writeStateToHash() {
    const next = `#${state.page}/${state.phaseId}/${state.diagramMode}`;
    if (window.location.hash !== next) {
      history.replaceState(null, "", next);
    }
  }

  function esc(str) {
    return String(str ?? "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function mdInline(str) {
    return esc(str)
      .replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>")
      .replace(/`([^`]+)`/g, "<code>$1</code>");
  }

  function currentEra() {
    return graph.eras.find((e) => e.id === state.page) || null;
  }

  function currentPhase(era) {
    if (!era || !era.phases || !era.phases.length || state.phaseId === "all") return null;
    return era.phases.find((p) => p.id === state.phaseId) || era.phases[0] || null;
  }

  let needsAutoFit = true;

  function selectPage(pageId) {
    state.page = pageId;
    state.flowId = "idle";
    state.stepIdx = -1;
    state.selectedEdgeId = null;
    if (pageId === "ecosystem" && state.diagramMode === "compare_phase") {
      state.diagramMode = "topology";
    }
    const era = currentEra();
    const ph = currentPhase(era);
    state.selectedNodeId = ph?.activeNodes?.[0] || era?.nodes?.[0]?.id || null;
    needsAutoFit = true;
    writeStateToHash();
    render();
  }

  function fitDiagramToStage(era) {
    if (!era) return;
    const ph = currentPhase(era);
    const layout = window.ArchLayoutEngine.layoutCompoundGraph(
      era,
      state.orientation,
      ph ? ph.topologyEdges : null
    );
    const stageEl = document.getElementById("diagram-stage");
    const availW = Math.max(480, (stageEl ? stageEl.clientWidth : window.innerWidth - 650) - 36);
    const availH = Math.max(320, (stageEl ? stageEl.clientHeight : window.innerHeight - 260) - 64);
    const scale = Math.min(1.0, availW / layout.width, availH / layout.height);
    state.zoom = Math.max(0.14, Number(scale.toFixed(3)));
    state.panX = Math.round(((stageEl ? stageEl.clientWidth : availW) - layout.width * state.zoom) / 2);
    state.panY = Math.max(14, Math.round(((stageEl ? stageEl.clientHeight : availH) - layout.height * state.zoom) / 2 - 8));
    const vp = document.getElementById("viewport-g");
    if (vp) vp.setAttribute("transform", `translate(${state.panX}, ${state.panY}) scale(${state.zoom})`);
  }

  function renderTopbar() {
    return `
      <header class="topbar">
        <div class="brand">
          <button class="ctrl-btn" id="btn-toggle-nav" title="Toggle navigation" style="padding:4px 8px">☰</button>
          <div class="brand-mark">λ</div>
          <div>
            <span class="brand-title">Azure Functions Python Runtime</span>
            <span class="brand-sub">Architecture Atlas</span>
          </div>
        </div>
        <div class="topbar-meta">
          <select class="flow-select" id="quick-era-select" title="Switch Architecture View">
            <option value="overview" ${state.page === "overview" ? "selected" : ""}>Evolution Matrix</option>
            <option value="ecosystem" ${state.page === "ecosystem" ? "selected" : ""}>4-Repo Ecosystem</option>
            <option value="py312" ${state.page === "py312" ? "selected" : ""}>Python ≤ 3.12 (Monolith)</option>
            <option value="py313_314" ${state.page === "py313_314" ? "selected" : ""}>Python 3.13–3.14 (Split)</option>
            <option value="py315_r2p2" ${state.page === "py315_r2p2" ? "selected" : ""}>Python 3.15+ (R2P2 Rust)</option>
            <option value="dep_iso" ${state.page === "dep_iso" ? "selected" : ""}>Dependency Isolation</option>
            <option value="pipeline" ${state.page === "pipeline" ? "selected" : ""}>Commit Auto-Sync CI</option>
          </select>
          <a class="meta-chip" href="${esc(graph.repos["python-worker"].url)}/commit/${esc(graph.git.sha)}" target="_blank" rel="noreferrer">
            <span class="pulse-dot"></span>
            @${esc(graph.git.shortSha)}
          </a>
        </div>
      </header>
    `;
  }

  function renderSidebar() {
    const navEraItems = [
      { id: "overview", title: "Evolution Matrix", sub: "≤3.12 vs 3.13-14 vs 3.15+", tag: "Compare" },
      { id: "ecosystem", title: "4-Repo Ecosystem", sub: "Proto · Worker · SDK · Ext", tag: "All" },
      { id: "py312", title: "Python ≤ 3.12", sub: "workers/azure_functions_worker", tag: "Monolith" },
      { id: "py313_314", title: "Python 3.13 – 3.14", sub: "proxy_worker + runtimes/", tag: "Split" },
      { id: "py315_r2p2", title: "Python 3.15+ (R2P2)", sub: "workers/r2p2 + PyO3 + runtimes/", tag: "Rust" },
    ];
    const deepDiveItems = [
      { id: "dep_iso", title: "Dependency Isolation", sub: "sys.path & Namespace Eviction", tag: "Internals" },
      { id: "pipeline", title: "Commit Auto-Sync Engine", sub: "AST + Drift Diff + Pages CI", tag: "DeepWiki" },
    ];

    return `
      <aside class="sidebar">
        <div>
          <div class="nav-group-title">Architecture Views</div>
          ${navEraItems
            .map(
              (it) => `
            <button class="nav-btn ${state.page === it.id ? "active" : ""}" data-nav="${it.id}">
              <div class="nav-btn-row">
                <span>${esc(it.title)}</span>
                <span class="nav-tag">${esc(it.tag)}</span>
              </div>
              <div class="nav-btn-sub">${esc(it.sub)}</div>
            </button>
          `
            )
            .join("")}
        </div>

        <div>
          <div class="nav-group-title">Runtime Deep Dives</div>
          ${deepDiveItems
            .map(
              (it) => `
            <button class="nav-btn ${state.page === it.id ? "active" : ""}" data-nav="${it.id}">
              <div class="nav-btn-row">
                <span>${esc(it.title)}</span>
                <span class="nav-tag">${esc(it.tag)}</span>
              </div>
              <div class="nav-btn-sub">${esc(it.sub)}</div>
            </button>
          `
            )
            .join("")}
        </div>

        <div>
          <div class="nav-group-title">Linked GitHub Repositories (4)</div>
          <div class="repo-legend-list">
            ${Object.values(graph.repos)
              .map(
                (r) => `
              <a class="repo-legend-item" href="${esc(r.url)}" target="_blank" rel="noreferrer" title="${esc(r.role)}">
                <span class="repo-dot-wrap">
                  <span class="repo-dot" style="background:${esc(r.color)}"></span>
                  <span>${esc(r.shortName)}</span>
                </span>
                <span style="color:var(--text-dim);font-size:10px">↗</span>
              </a>
            `
              )
              .join("")}
          </div>
        </div>
      </aside>
    `;
  }

  function renderTopologySVG(era, activePhase, activeStep) {
    const layout = window.ArchLayoutEngine.layoutCompoundGraph(
      era,
      state.orientation,
      activePhase ? activePhase.topologyEdges : null
    );
    const phaseNodeSet = activePhase ? new Set(activePhase.activeNodes) : null;
    const stepNodeSet = activeStep ? new Set(activeStep.activeNodes) : null;
    const stepEdgeSet = activeStep ? new Set(activeStep.activeEdges) : null;

    const markers = Object.entries(EDGE_PALETTE)
      .map(
        ([k, v]) => `
        <marker id="mk-${k}" markerWidth="9" markerHeight="9" refX="8" refY="4.5" orient="auto">
          <path d="M0,0 L9,4.5 L0,9 Z" fill="${v.color}" />
        </marker>
      `
      )
      .join("");

    const containersSvg = layout.containers
      .map((c) => {
        const t = CONTAINER_TONES[c.tone] || CONTAINER_TONES.python;
        const r = c.isNested ? 9 : 13;
        return `
          <g class="svg-container">
            <rect x="${c.x}" y="${c.y}" width="${c.w}" height="${c.h}" rx="${r}"
              fill="${t.fill}" stroke="${t.stroke}" stroke-opacity="0.52"
              stroke-width="${c.isNested ? 1.3 : 1.7}"
              ${c.isNested ? 'stroke-dasharray="6 4"' : ""} />
            <rect x="${c.x}" y="${c.y}" width="${c.w}" height="28" rx="${r}"
              fill="${t.head}" />
            <text x="${c.x + 12}" y="${c.y + 18}" fill="${t.text}" font-size="10.5"
              font-weight="700" letter-spacing="0.04em">${esc(c.label.toUpperCase())}</text>
          </g>
        `;
      })
      .join("");

    const edgesSvg = layout.edges
      .map((e) => {
        const pal = EDGE_PALETTE[e.kind] || EDGE_PALETTE["inproc-contract"];
        const isStepActive = stepEdgeSet ? stepEdgeSet.has(e.id) : false;
        const isPhaseFlowing = Boolean(activePhase) && !stepEdgeSet;
        const isSelected = state.selectedEdgeId === e.id;
        const isDim = stepEdgeSet && !isStepActive;
        const opacity = isDim ? 0.16 : 0.96;
        const strokeW = isStepActive || isSelected ? 3.3 : isPhaseFlowing ? 2.3 : 1.9;
        const labelW = Math.max(78, e.label.length * 6.3 + 16);

        return `
          <g class="svg-edge" data-edge="${e.id}" style="cursor:pointer" opacity="${opacity}">
            <path d="${e.path}" fill="none" stroke="transparent" stroke-width="14" />
            <path id="epath-${e.id}" d="${e.path}" fill="none" stroke="${pal.color}"
              stroke-width="${strokeW}"
              class="${isStepActive || isPhaseFlowing ? "edge-animated" : ""}"
              ${e.dashed && !isStepActive ? 'stroke-dasharray="6 4"' : ""}
              marker-end="url(#mk-${e.kind})" />
            ${
              isStepActive
                ? `<circle r="4.8" fill="#fff" stroke="${pal.color}" stroke-width="2">
                     <animateMotion dur="1.1s" repeatCount="indefinite">
                       <mpath href="#epath-${e.id}" />
                     </animateMotion>
                   </circle>`
                : ""
            }
            <g transform="translate(${e.labelX - labelW / 2}, ${e.labelY - 10})">
              <rect width="${labelW}" height="20" rx="5"
                fill="${isStepActive ? "#1e1b4b" : "#0b1220"}"
                stroke="${pal.color}" stroke-width="${isStepActive || isSelected ? 1.5 : 0.9}" />
              <text x="${labelW / 2}" y="13.5" text-anchor="middle" fill="#e2e8f0"
                font-size="9.8" font-family="ui-monospace, Menlo, monospace" font-weight="600">
                ${esc(e.label)}
              </text>
            </g>
          </g>
        `;
      })
      .join("");

    const nodesSvg = layout.nodes
      .map((p) => {
        const n = p.node;
        const repo = graph.repos[n.repo] || graph.repos["python-worker"];
        const isBypassedInPhase = phaseNodeSet ? !phaseNodeSet.has(n.id) : false;
        const isStepActive = stepNodeSet ? stepNodeSet.has(n.id) : false;
        const isDim = isBypassedInPhase || (stepNodeSet && !isStepActive);
        const isSel = state.selectedNodeId === n.id;
        const borderCol = isStepActive ? "#fb923c" : isSel ? "#38bdf8" : !isBypassedInPhase && phaseNodeSet ? "#3b527e" : "#24324d";
        const borderW = isStepActive || isSel ? 2.4 : 1.4;
        const shortFile = n.file.split("/").slice(-2).join("/");
        const lineTag = n.line > 1 ? `:${n.line}` : "";

        return `
          <g class="svg-node" data-node="${n.id}" transform="translate(${p.x}, ${p.y})"
             style="cursor:pointer" opacity="${isBypassedInPhase ? 0.23 : isDim ? 0.32 : 1}">
            <rect width="${p.w}" height="${p.h}" rx="10"
              fill="${isSel ? "#15233c" : "#0e1729"}"
              stroke="${borderCol}" stroke-width="${borderW}" />
            <rect x="0" y="0" width="4.5" height="${p.h}" rx="2.5" fill="${repo.color}" />

            <!-- Repo badge + Sub-badge -->
            <rect x="13" y="9" width="${repo.shortName.length * 6.2 + 12}" height="17" rx="4"
              fill="rgba(15,23,42,0.9)" stroke="${repo.color}" stroke-width="0.9" />
            <text x="19" y="20.5" fill="${repo.color}" font-size="9.3"
              font-family="ui-monospace, Menlo, monospace" font-weight="700">${esc(repo.shortName)}</text>

            <text x="${p.w - 10}" y="20.5" text-anchor="end" fill="${isBypassedInPhase ? "#fbbf24" : "#94a3b8"}" font-size="9.5"
              font-family="ui-monospace, Menlo, monospace">${esc(isBypassedInPhase ? "BYPASSED" : n.badge.slice(0, 22))}</text>

            <!-- Title -->
            <text x="14" y="46" fill="#f8fafc" font-size="12.3" font-weight="700">
              ${esc(n.label.length > 31 ? n.label.slice(0, 30) + "…" : n.label)}
            </text>

            <!-- File & symbol anchor -->
            <text x="14" y="74" fill="#7dd3fc" font-size="10.2"
              font-family="ui-monospace, Menlo, monospace">
              ${esc((shortFile + lineTag).slice(0, 33))}
            </text>
            ${
              n.extractedSymbols && n.extractedSymbols.length
                ? `<text x="${p.w - 10}" y="74" text-anchor="end" fill="#64748b" font-size="9.5"
                     font-family="ui-monospace, Menlo, monospace">${n.extractedSymbols.length} AST</text>`
                : ""
            }
          </g>
        `;
      })
      .join("");

    return `
      <div class="diagram-stage" id="diagram-stage">
        <svg id="topology-svg" width="100%" height="100%">
          <defs>${markers}</defs>
          <g id="viewport-g" transform="translate(${state.panX}, ${state.panY}) scale(${state.zoom})">
            ${containersSvg}
            ${edgesSvg}
            ${nodesSvg}
          </g>
        </svg>

        <div class="zoom-hud">
          <button class="ctrl-btn" id="btn-zoom-in" title="Zoom in">+</button>
          <button class="ctrl-btn" id="btn-zoom-out" title="Zoom out">−</button>
          <button class="ctrl-btn" id="btn-zoom-fit">Fit</button>
          <button class="ctrl-btn" id="btn-orient">
            Layout: ${state.orientation === "LR" ? "Left → Right" : "Top → Bottom"}
          </button>
        </div>

        <div class="edge-legend-hud">
          ${Object.values(EDGE_PALETTE)
            .slice(0, 5)
            .map(
              (p) => `
            <span class="edge-legend-item">
              <span class="edge-swatch" style="background:${p.color}"></span>
              <span>${esc(p.label)}</span>
            </span>
          `
            )
            .join("")}
        </div>
      </div>
    `;
  }

  function renderSequenceSVG(flow) {
    if (!flow) return `<div class="scroll-page">Select a lifecycle flow above.</div>`;
    const colW = 188;
    const padX = 115;
    const startY = 96;
    const rowH = 68;
    const width = Math.max(760, padX * 2 + (flow.actors.length - 1) * colW);
    const height = startY + flow.steps.length * rowH + 46;
    const actorX = new Map(flow.actors.map((a, i) => [a.id, padX + i * colW]));

    return `
      <div class="scroll-page" style="background:#060a12">
        <div style="margin-bottom:12px;display:flex;justify-content:space-between;align-items:center">
          <div>
            <strong style="font-size:14px">${esc(flow.title)}</strong>
            <div style="font-size:12px;color:var(--text-muted);margin-top:2px">${esc(flow.summary)}</div>
          </div>
          <span class="meta-chip">Click any message row to synchronize active path</span>
        </div>
        <div style="overflow-x:auto;border:1px solid var(--border);border-radius:12px;background:#090f1d;padding:12px">
          <svg viewBox="0 0 ${width} ${height}" width="100%" style="min-width:${width}px;display:block">
            <defs>
              <marker id="sq-req" markerWidth="9" markerHeight="9" refX="8" refY="4.5" orient="auto">
                <path d="M0,0 L9,4.5 L0,9 Z" fill="#38bdf8" />
              </marker>
              <marker id="sq-ret" markerWidth="9" markerHeight="9" refX="8" refY="4.5" orient="auto">
                <path d="M0,0 L9,4.5 L0,9 Z" fill="#34d399" />
              </marker>
              <marker id="sq-act" markerWidth="10" markerHeight="10" refX="8.5" refY="5" orient="auto">
                <path d="M0,0 L10,5 L0,10 Z" fill="#fb923c" />
              </marker>
            </defs>
            ${flow.actors
              .map((a) => {
                const x = actorX.get(a.id);
                return `
                  <line x1="${x}" y1="58" x2="${x}" y2="${height - 20}" stroke="#273654" stroke-width="1.5" stroke-dasharray="5 5"/>
                  <rect x="${x - 76}" y="20" width="152" height="36" rx="8" fill="#111b2e" stroke="#3b527e" stroke-width="1.3"/>
                  <text x="${x}" y="42" text-anchor="middle" fill="#f8fafc" font-size="11.5" font-weight="700">${esc(a.label)}</text>
                `;
              })
              .join("")}
            ${flow.steps
              .map((st, idx) => {
                const x1 = actorX.get(st.from);
                const x2 = actorX.get(st.to);
                const y = startY + idx * rowH;
                const isAct = state.stepIdx === idx;
                const stroke = isAct ? "#fb923c" : st.isReturn ? "#34d399" : "#38bdf8";
                const mk = isAct ? "url(#sq-act)" : st.isReturn ? "url(#sq-ret)" : "url(#sq-req)";
                const mid = x1 === x2 ? x1 + 60 : (x1 + x2) / 2;
                return `
                  <g data-seq-step="${idx}" data-seq-flow="${flow.id}" style="cursor:pointer">
                    <rect x="16" y="${y - 26}" width="${width - 32}" height="54" rx="8"
                      fill="${isAct ? "rgba(251,146,60,0.12)" : "transparent"}"
                      stroke="${isAct ? "rgba(251,146,60,0.45)" : "transparent"}"/>
                    <circle cx="40" cy="${y}" r="11" fill="${isAct ? "#fb923c" : "#162138"}" stroke="${stroke}"/>
                    <text x="40" y="${y + 4}" text-anchor="middle" fill="${isAct ? "#090f1d" : "#e2e8f0"}" font-size="10.5" font-weight="700">${idx + 1}</text>
                    <line x1="${x1}" y1="${y + 4}" x2="${x2 + (x2 > x1 ? -6 : 6)}" y2="${y + 4}"
                      stroke="${stroke}" stroke-width="${isAct ? 2.8 : 1.9}"
                      ${st.isReturn ? 'stroke-dasharray="6 4"' : ""} marker-end="${mk}"/>
                    <text x="${mid}" y="${y - 6}" text-anchor="middle" fill="${isAct ? "#fed7aa" : "#f1f5f9"}" font-size="11.5" font-weight="650">${esc(st.message)}</text>
                    <text x="${mid}" y="${y + 20}" text-anchor="middle" fill="#94a3b8" font-size="10.2" font-family="ui-monospace, Menlo, monospace">${esc(st.payload)}</text>
                  </g>
                `;
              })
              .join("")}
          </svg>
        </div>
      </div>
    `;
  }

  function renderMermaidTab(era, activePhase) {
    const topoMmd = activePhase ? activePhase.topologyMermaid : era.topologyMermaid;
    const seqTarget = activePhase || era.flows[0];
    return `
      <div class="scroll-page">
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:10px">
          <div>
            <strong>Auto-Compiled Mermaid Source — ${esc(activePhase ? activePhase.title : era.title)}</strong>
            <div style="font-size:12px;color:var(--text-muted)">Deterministically compiled from <code>architecture-graph.json</code> for PRs &amp; design docs.</div>
          </div>
          <button class="ctrl-btn primary" id="btn-copy-mermaid">${state.copied ? "Copied!" : "Copy Topology Mermaid"}</button>
        </div>
        <pre class="code-pre" id="mermaid-topo-src">${esc(topoMmd)}</pre>
        ${
          seqTarget
            ? `
          <div style="margin:18px 0 8px;font-weight:700;font-size:13px">Sequence Diagram — ${esc(seqTarget.title)}</div>
          <pre class="code-pre">${esc(seqTarget.sequenceMermaid)}</pre>
        `
            : ""
        }
      </div>
    `;
  }

  function renderComparePhaseTab(phaseId) {
    const targetId = phaseId === "all" ? "init" : phaseId;
    const cat = (graph.phaseCatalog || []).find((p) => p.id === targetId) || { short: targetId, proto: "" };
    const workerEras = graph.eras.filter((e) => e.phases && e.phases.length);

    return `
      <div class="scroll-page">
        <div style="margin-bottom:14px">
          <span class="status-pill">${esc(cat.proto)}</span>
          <h2 style="margin:8px 0 4px;font-size:19px">Cross-Era Comparison — ${esc(cat.short)}</h2>
          <div style="font-size:12.5px;color:var(--text-muted)">How Python ≤ 3.12, 3.13–3.14, and 3.15+ (R2P2) each handle this exact lifecycle phase.</div>
        </div>
        <div class="compare-grid">
          ${workerEras
            .map((e) => {
              const ph = e.phases.find((p) => p.id === targetId);
              if (!ph) return "";
              return `
                <div class="era-card">
                  <div style="display:flex;justify-content:space-between;align-items:center">
                    <strong style="font-size:14.5px">${esc(e.shortTitle)}</strong>
                    <button class="ctrl-btn" data-jump-era="${esc(e.id)}" data-jump-phase="${esc(ph.id)}">Open Topology →</button>
                  </div>
                  <div style="font-size:11px;font-family:var(--mono);color:#7dd3fc">${esc(ph.proto)}</div>
                  <p style="font-size:12px;color:#cbd5e1;line-height:1.5;margin:4px 0">${mdInline(ph.summary)}</p>
                  <div class="phase-bypassed-note">⚡ ${mdInline(ph.bypassedNote)}</div>
                  <div class="insp-kicker" style="margin-top:8px">Sequence Hops (${ph.steps.length})</div>
                  <ol class="detail-bullets" style="padding-left:18px;font-size:11.5px">
                    ${ph.steps
                      .map(
                        (s) => `<li><strong>${esc(s.message)}</strong><br/><span style="color:var(--text-dim);font-family:var(--mono);font-size:10.5px">${esc(s.payload)}</span></li>`
                      )
                      .join("")}
                  </ol>
                </div>
              `;
            })
            .join("")}
        </div>
      </div>
    `;
  }

  function renderInspector(era, activePhase) {
    const edgePool = activePhase ? activePhase.topologyEdges : era.edges;
    const selEdge = state.selectedEdgeId ? edgePool.find((e) => e.id === state.selectedEdgeId) : null;
    if (selEdge) {
      const srcNode = era.nodes.find((n) => n.id === selEdge.source);
      const tgtNode = era.nodes.find((n) => n.id === selEdge.target);
      const pal = EDGE_PALETTE[selEdge.kind] || EDGE_PALETTE["inproc-contract"];
      return `
        <aside class="inspector">
          <div class="insp-card">
            <div class="insp-kicker" style="color:${pal.color}">Protocol / Interaction Edge</div>
            <h3 class="insp-title">${esc(selEdge.label)}</h3>
            <p class="insp-role"><strong>Channel Kind:</strong> ${esc(pal.label)}</p>
            <div style="margin-top:10px;font-size:12px;color:#cbd5e1">
              <div><strong>From:</strong> ${esc(srcNode?.label)} <code>(${esc(srcNode?.repo)})</code></div>
              <div style="margin-top:4px"><strong>To:</strong> ${esc(tgtNode?.label)} <code>(${esc(tgtNode?.repo)})</code></div>
            </div>
          </div>
          ${
            activePhase
              ? `
            <div class="insp-card">
              <div class="insp-kicker">Active Lifecycle Phase</div>
              <div style="font-size:12px;color:#e2e8f0;font-weight:700">${esc(activePhase.title)}</div>
              <div style="font-size:11px;color:#7dd3fc;font-family:var(--mono);margin-top:4px">${esc(activePhase.proto)}</div>
            </div>
          `
              : ""
          }
        </aside>
      `;
    }

    const node = era.nodes.find((n) => n.id === state.selectedNodeId) || era.nodes[0];
    if (!node) return `<aside class="inspector"></aside>`;
    const repo = graph.repos[node.repo] || graph.repos["python-worker"];
    const inbound = edgePool.filter((e) => e.target === node.id);
    const outbound = edgePool.filter((e) => e.source === node.id);
    const isBypassed = activePhase ? !activePhase.activeNodes.includes(node.id) : false;

    return `
      <aside class="inspector">
        <div class="insp-card">
          <div class="insp-kicker" style="color:${repo.color}">${esc(repo.fullName)}</div>
          <h3 class="insp-title">${esc(node.label)}</h3>
          ${
            isBypassed
              ? `<div style="margin-bottom:6px;font-size:11px;color:#fbbf24;font-family:var(--mono)">⚡ Bypassed / Idle in ${esc(activePhase.title)}</div>`
              : ""
          }
          <p class="insp-role">${mdInline(node.role)}</p>

          <a class="gh-deep-link" href="${esc(node.githubUrl)}" target="_blank" rel="noreferrer">
            <span>${esc(node.file)}${node.line > 1 ? `:L${node.line}` : ""}</span>
            <span>GitHub ↗</span>
          </a>

          <ul class="detail-bullets">
            ${node.details.map((d) => `<li>${mdInline(d)}</li>`).join("")}
          </ul>
        </div>

        ${
          node.extractedSymbols && node.extractedSymbols.length
            ? `
          <div class="insp-card">
            <div class="insp-kicker">Live Extracted AST / Rust Symbols (${node.fileLines} LOC)</div>
            <div class="sym-list">
              ${node.extractedSymbols
                .map((s) => {
                  const baseUrl = node.githubUrl.split("#")[0];
                  return `
                    <a class="sym-item" href="${esc(baseUrl)}#L${s.line}" target="_blank" rel="noreferrer">
                      <span><span style="color:var(--text-dim)">${esc(s.kind)}</span> ${esc(s.signature)}</span>
                      <span class="sym-line">L${s.line}</span>
                    </a>
                  `;
                })
                .join("")}
            </div>
          </div>
        `
            : ""
        }

        <div class="insp-card">
          <div class="insp-kicker">Connected Boundaries (${inbound.length} in · ${outbound.length} out)</div>
          <div class="sym-list">
            ${inbound
              .map((e) => {
                const sn = era.nodes.find((x) => x.id === e.source);
                return `<div class="sym-item" data-node="${esc(e.source)}" style="cursor:pointer">
                  <span>← ${esc(sn?.label)}</span><span class="sym-line">${esc(e.label)}</span>
                </div>`;
              })
              .join("")}
            ${outbound
              .map((e) => {
                const tn = era.nodes.find((x) => x.id === e.target);
                return `<div class="sym-item" data-node="${esc(e.target)}" style="cursor:pointer">
                  <span>→ ${esc(tn?.label)}</span><span class="sym-line">${esc(e.label)}</span>
                </div>`;
              })
              .join("")}
          </div>
        </div>
      </aside>
    `;
  }

  function renderEraWorkspace(era) {
    const hasPhases = Boolean(era.phases && era.phases.length);
    const activePhase = currentPhase(era);
    const seqSource = activePhase || era.flows[0];
    const stepList = activePhase ? activePhase.steps : [];
    const activeStep =
      activePhase && state.stepIdx >= 0 && state.stepIdx < stepList.length
        ? stepList[state.stepIdx]
        : null;

    return `
      <main class="workspace">
        <div class="era-header">
          <div>
            <div class="era-title-row">
              <h1 class="era-h1">${esc(era.title)}</h1>
              <span class="status-pill">${esc(era.pythonVersions)}</span>
            </div>
            ${
              !activePhase
                ? `<p class="era-tagline">${mdInline(era.summary)}</p>`
                : ""
            }
          </div>
          <div class="mode-tabs">
            <button class="mode-tab ${state.diagramMode === "topology" ? "active" : ""}" data-mode="topology">
              Compound Topology
            </button>
            <button class="mode-tab ${state.diagramMode === "sequence" ? "active" : ""}" data-mode="sequence">
              Sequence Flow
            </button>
            ${
              hasPhases
                ? `<button class="mode-tab ${state.diagramMode === "compare_phase" ? "active" : ""}" data-mode="compare_phase">
                     Compare Phase (3 Eras)
                   </button>`
                : ""
            }
            <button class="mode-tab ${state.diagramMode === "mermaid" ? "active" : ""}" data-mode="mermaid">
              Mermaid Code
            </button>
          </div>
        </div>

        ${
          hasPhases
            ? `
          <div class="phase-bar">
            <span class="toolbar-label" style="margin-right:4px">Lifecycle Phase:</span>
            <button class="phase-pill ${state.phaseId === "all" ? "active" : ""}" data-phase="all">
              <span class="phase-num">∗</span> All Edges
            </button>
            ${(graph.phaseCatalog || [])
              .map(
                (p) => `
              <button class="phase-pill ${state.phaseId === p.id ? "active" : ""}" data-phase="${esc(p.id)}" title="${esc(p.proto)}">
                <span class="phase-num">${esc(p.num)}</span>
                <span>${esc(p.short)}</span>
              </button>
            `
              )
              .join("")}
          </div>
        `
            : ""
        }

        ${
          activePhase
            ? `
          <div class="phase-context-strip">
            <div style="max-width:860px">
              <div style="display:flex;align-items:center;gap:8px;flex-wrap:wrap">
                <strong style="font-size:13.5px;color:#f8fafc">${esc(activePhase.title)}</strong>
                <span class="meta-chip" style="color:#7dd3fc">${esc(activePhase.proto)}</span>
                <span class="nav-tag">${esc(activePhase.scope)}</span>
              </div>
              <div style="font-size:12px;color:#cbd5e1;margin-top:4px;line-height:1.45">${mdInline(activePhase.summary)}</div>
              <div class="phase-bypassed-note">⚡ ${mdInline(activePhase.bypassedNote)}</div>
            </div>

            <div class="flow-controls" style="align-self:center">
              ${
                state.stepIdx >= 0
                  ? `
                <button class="ctrl-btn" id="step-prev" ${state.stepIdx <= 0 ? "disabled" : ""}>◀ Prev</button>
                <span class="meta-chip">Hop ${state.stepIdx + 1} / ${stepList.length}</span>
                <button class="ctrl-btn primary" id="step-next" ${
                  state.stepIdx >= stepList.length - 1 ? "disabled" : ""
                }>Next ▶</button>
                <button class="ctrl-btn" id="step-reset">Full Phase</button>
              `
                  : `
                <button class="ctrl-btn primary" id="btn-start-trace">▶ Step Hop-by-Hop (${stepList.length})</button>
              `
              }
            </div>
          </div>
          ${
            activeStep
              ? `
            <div class="diagram-toolbar" style="padding:6px 18px">
              <div class="active-step-banner">
                <strong>Hop ${state.stepIdx + 1}: ${esc(activeStep.message)}</strong>
                <span class="active-step-payload">[${esc(activeStep.payload)}]</span>
              </div>
            </div>
          `
              : ""
          }
        `
            : ""
        }

        ${
          state.diagramMode === "topology"
            ? `<div class="canvas-split">
                 ${renderTopologySVG(era, activePhase, activeStep)}
                 ${renderInspector(era, activePhase)}
               </div>`
            : state.diagramMode === "sequence"
            ? renderSequenceSVG(seqSource)
            : state.diagramMode === "compare_phase"
            ? renderComparePhaseTab(state.phaseId)
            : renderMermaidTab(era, activePhase)
        }
      </main>
    `;
  }

  function renderOverviewPage() {
    const threeEras = graph.eras.filter((e) => e.id !== "ecosystem");
    return `
      <main class="workspace">
        <div class="scroll-page">
          <span class="status-pill">Architecture Evolution · Python 3.7 → 3.15+</span>
          <h1 style="margin:10px 0 6px;font-size:24px">Azure Functions Python Runtime — Three-Generation Evolution</h1>
          <p style="color:var(--text-muted);max-width:860px;font-size:13.5px;line-height:1.55">
            While preserving the exact same <code>FunctionRpc.proto</code> Host contract and customer
            <code>azure-functions</code> programming models (V1 <code>function.json</code> &amp; V2 <code>@app</code> decorators),
            the worker evolved from a single CPython monolith (≤3.12), to a decoupled Python Proxy + PyPI Runtime split (3.13–3.14),
            to <strong>R2P2</strong> — a native Rust <code>tonic</code>/<code>prost</code> shell embedding CPython via <code>PyO3</code> (3.15+).
          </p>

          <div class="compare-grid">
            ${threeEras
              .map(
                (e) => `
              <div class="era-card">
                <div style="display:flex;justify-content:space-between;align-items:center">
                  <strong style="font-size:15px">${esc(e.shortTitle)}</strong>
                  <span class="nav-tag">${esc(e.pythonVersions)}</span>
                </div>
                <div style="font-size:12px;color:#7dd3fc;font-family:var(--mono)">${esc(e.packagePath)}</div>
                <p style="font-size:12.5px;color:var(--text-muted);line-height:1.48;margin:2px 0">${esc(e.tagline)}</p>
                <ul class="detail-bullets" style="margin-top:2px">
                  ${e.tradeoffs
                    .map(
                      (t) =>
                        `<li><span style="color:${t.kind === "strength" ? "#34d399" : "#fb923c"}">${
                          t.kind === "strength" ? "✓" : "⚠"
                        }</span> ${esc(t.text)}</li>`
                    )
                    .join("")}
                </ul>
                <button class="ctrl-btn primary" style="margin-top:auto" data-nav="${e.id}">
                  Open Interactive Diagram →
                </button>
              </div>
            `
              )
              .join("")}
          </div>

          <table class="matrix-table">
            <thead>
              <tr>
                <th>Architectural Dimension</th>
                <th>Python ≤ 3.12 (Monolith)</th>
                <th>Python 3.13 – 3.14 (Proxy Split)</th>
                <th>Python 3.15+ (R2P2 Rust Proxy)</th>
              </tr>
            </thead>
            <tbody>
              <tr>
                <td><strong>Launcher &amp; Process</strong></td>
                <td><code>prodV4/worker.py</code> → CPython</td>
                <td><code>proxyV4/worker.py</code> → CPython</td>
                <td>Compiled <code>r2p2</code> Rust binary + embedded <code>libpython3.15</code> (GIL)</td>
              </tr>
              <tr>
                <td><strong>gRPC &amp; Wire Codec</strong></td>
                <td>Python <code>grpcio</code> + <code>google.protobuf</code></td>
                <td>Python <code>grpcio</code> + worker <code>protobuf</code> + <code>uvloop</code></td>
                <td>Native Rust <code>tonic</code> + <code>prost</code> + <code>tokio</code> (0 Python protobuf)</td>
              </tr>
              <tr>
                <td><strong>Proxy ↔ Runtime Seam</strong></td>
                <td>None (internal module imports)</td>
                <td>In-proc <code>WorkerRequest</code> + injected <code>protos</code></td>
                <td>PyO3 FFI: <code>invoke_native</code> Datum tuples (hot) + <code>protos_adapter</code> dicts (control)</td>
              </tr>
              <tr>
                <td><strong>Day-1 New Python Support</strong></td>
                <td>Blocked on <code>grpcio</code>/<code>protobuf</code> wheels</td>
                <td>Blocked on <code>grpcio</code>/<code>protobuf</code> wheels</td>
                <td><strong>Unblocked</strong> — Rust owns wire; runtime is pure Python</td>
              </tr>
              <tr>
                <td><strong>WorkerStatus Scale Probe</strong></td>
                <td>Handled inside Python Dispatcher</td>
                <td>Fast-path in <code>proxy_worker</code></td>
                <td><strong>Zero-GIL</strong> pure Rust reply in <code>bridge.rs</code></td>
              </tr>
              <tr>
                <td><strong>Measured GIL Throughput</strong></td>
                <td>Baseline (~339 req/s, p50 145ms)</td>
                <td>Parity (~339 req/s; PyPI agility win)</td>
                <td><strong>+122% (754 req/s, p50 64ms)</strong></td>
              </tr>
            </tbody>
          </table>
        </div>
      </main>
    `;
  }

  function renderDepIsoPage() {
    return `
      <main class="workspace">
        <div class="scroll-page">
          <span class="status-pill">Runtime Internals · Dependency Isolation</span>
          <h1 style="margin:10px 0 6px;font-size:22px">Dependency Isolation &amp; Namespace-Safe Promotion Across Eras</h1>
          <p style="color:var(--text-muted);max-width:860px;font-size:13px;line-height:1.55">
            In Flex Consumption and Linux Consumption, warm placeholder containers boot <em>before</em> customer packages are mounted,
            then specialize on <code>FunctionEnvironmentReloadRequest</code> (or <code>WorkerInitRequest</code>).
          </p>

          <div class="compare-grid" style="grid-template-columns:repeat(2, 1fr)">
            <div class="era-card">
              <strong>Python ≤ 3.14 (<code>DependencyManager</code>)</strong>
              <p style="font-size:12.5px;color:var(--text-muted)">
                <code>proxy_worker/utils/dependency.py</code> boots with <code>use_worker_dependencies()</code> so worker
                <code>grpcio</code> and <code>google.protobuf</code> C-extensions load from the worker directory, then switches
                <code>sys.path</code> to <code>[cx_deps, cx_working_dir, worker_deps]</code>.
                <br/><br/>
                <strong>Historical Pain (D-003..D-005):</strong> Because <code>google.protobuf</code> uses a process-global C descriptor pool,
                once loaded at boot it could still collide with customer-pinned <code>protobuf</code> versions.
              </p>
            </div>
            <div class="era-card">
              <strong>Python 3.15+ R2P2 (<code>bridge.py</code> + Zero Protobuf)</strong>
              <p style="font-size:12.5px;color:var(--text-muted)">
                Because Rust (<code>tonic</code>/<code>prost</code>) owns the wire and <code>protos_adapter.py</code> is pure Python,
                <strong>neither <code>grpcio</code> nor <code>google.protobuf</code> ever enters <code>sys.modules</code></strong>!
                <br/><br/>
                On specialization, <code>_clear_modules_from_path()</code> (<code>workers/r2p2/bridge/bridge.py:L328</code>)
                evicts file-backed worker packages &amp; cached descendants and detaches stale child attributes from retained parents,
                while <strong>preserving shared PEP 420 namespace parents</strong> (<code>azure</code>, <code>azurefunctions</code>) so customer extensions stay attached.
              </p>
            </div>
          </div>

          <h3 style="margin-top:22px;font-size:14px"><code>sys.path</code> Priority Order After Specialization</h3>
          <pre class="code-pre">1. Customer Packages (.python_packages/lib/site-packages)   # Customer-pinned azure-functions / extensions win!
2. Worker Bundled Runtime Dependencies (workers_dir)        # Fallback azure_functions_runtime (v2 / v1)
3. Customer Function App Directory (function_app_directory) # function_app.py &amp; user modules
   [Protected in R2P2: bridge, protos_adapter, runtime prefixes]</pre>
        </div>
      </main>
    `;
  }

  function renderPipelinePage() {
    const invRows = Object.entries(graph.packageInventories)
      .map(
        ([pkg, files]) => `
        <tr>
          <td><code>${esc(pkg)}</code></td>
          <td>${files.length} source files</td>
          <td>${files.reduce((s, f) => s + f.lines, 0).toLocaleString()} LOC</td>
          <td><code>${esc(files[0]?.path || "")}</code> …</td>
        </tr>
      `
      )
      .join("");

    return `
      <main class="workspace">
        <div class="scroll-page">
          <span class="status-pill">DeepWiki Auto-Sync Pipeline · Commit-Driven</span>
          <h1 style="margin:10px 0 6px;font-size:22px">How Diagrams &amp; Pages Stay Live on Every Commit</h1>
          <p style="color:var(--text-muted);max-width:860px;font-size:13px;line-height:1.55">
            Rather than brittle hand-positioned boxes or unconstrained LLM prose, the documentation pipeline separates
            <strong>deterministic code-graph extraction + algorithmic compound layout</strong> (every commit) from
            <strong>drift-gated AI narrative synthesis</strong> (only when structural contracts change).
          </p>

          <div class="compare-grid">
            <div class="era-card">
              <strong>1. Deterministic AST + Rust + Proto Extractor</strong>
              <div style="font-size:11px;font-family:var(--mono);color:#7dd3fc">eng/docs/extract_arch.py · &lt; 0.5s</div>
              <p style="font-size:12px;color:var(--text-muted)">
                Parses Python <code>ast</code>, Rust <code>workers/r2p2/src/*.rs</code>, and <code>FunctionRpc.proto</code>,
                and links sibling contracts in <code>python-library</code>, <code>python-extensions</code>, and <code>language-worker-protobuf</code>.
                Computes SHA-256 <code>structuralFingerprint</code> (currently <code>${esc(graph.structuralFingerprint)}</code>).
              </p>
            </div>
            <div class="era-card">
              <strong>2. Algorithmic Compound Diagram Engine</strong>
              <div style="font-size:11px;font-family:var(--mono);color:#34d399">site/assets/layoutEngine.js</div>
              <p style="font-size:12px;color:var(--text-muted)">
                Computes topological layer ranks, nested container swimlanes, port ordering, and Bezier/orthogonal routes
                automatically from JSON — plus deterministic Mermaid compilation. Adding a module or edge never breaks layout.
              </p>
            </div>
            <div class="era-card">
              <strong>3. Drift-Gated AI Refresher + Pages Deploy</strong>
              <div style="font-size:11px;font-family:var(--mono);color:#fb923c">.github/workflows/architecture-pages.yml</div>
              <p style="font-size:12px;color:var(--text-muted)">
                Every push to <code>dev</code> deploys live AST line anchors &amp; inventories to GitHub Pages.
                When <code>structuralFingerprint</code> changes (new router case, FFI signature, or module), GitHub Models
                (<code>models: read</code>) updates affected explanations with citation validation.
              </p>
            </div>
          </div>

          <h3 style="margin-top:22px;font-size:14px">Live Scanned Package Inventory (Commit <code>${esc(graph.git.shortSha)}</code>)</h3>
          <table class="matrix-table">
            <thead>
              <tr><th>Subsystem</th><th>Tracked Files</th><th>Total Lines</th><th>Sample Entry</th></tr>
            </thead>
            <tbody>${invRows}</tbody>
          </table>
        </div>
      </main>
    `;
  }

  function render() {
    const root = document.getElementById("root");
    const era = currentEra();
    let mainHtml = "";
    if (state.page === "overview") mainHtml = renderOverviewPage();
    else if (state.page === "dep_iso") mainHtml = renderDepIsoPage();
    else if (state.page === "pipeline") mainHtml = renderPipelinePage();
    else if (era) mainHtml = renderEraWorkspace(era);

    const shellCls = [
      "app-shell",
      state.sidebarCollapsed ? "sidebar-collapsed" : "",
      state.mobileMenuOpen ? "sidebar-open-mobile" : "",
    ]
      .filter(Boolean)
      .join(" ");

    root.innerHTML = `
      <div class="${shellCls}">
        ${renderTopbar()}
        ${renderSidebar()}
        ${mainHtml}
      </div>
    `;
    if (needsAutoFit && era && state.diagramMode === "topology") {
      needsAutoFit = false;
      fitDiagramToStage(era);
    }
    bindEvents();
  }

  function bindEvents() {
    const toggleBtn = document.getElementById("btn-toggle-nav");
    if (toggleBtn) {
      toggleBtn.addEventListener("click", () => {
        if (window.innerWidth <= 1120) {
          state.mobileMenuOpen = !state.mobileMenuOpen;
        } else {
          state.sidebarCollapsed = !state.sidebarCollapsed;
        }
        needsAutoFit = true;
        render();
      });
    }

    const quickSel = document.getElementById("quick-era-select");
    if (quickSel) {
      quickSel.addEventListener("change", (ev) => {
        state.mobileMenuOpen = false;
        selectPage(ev.target.value);
      });
    }

    document.querySelectorAll("[data-nav]").forEach((el) => {
      el.addEventListener("click", () => {
        state.mobileMenuOpen = false;
        selectPage(el.getAttribute("data-nav"));
      });
    });

    document.querySelectorAll("[data-mode]").forEach((el) => {
      el.addEventListener("click", () => {
        state.diagramMode = el.getAttribute("data-mode");
        if (state.diagramMode === "topology") needsAutoFit = true;
        writeStateToHash();
        render();
      });
    });

    document.querySelectorAll("[data-phase]").forEach((el) => {
      el.addEventListener("click", () => {
        state.phaseId = el.getAttribute("data-phase");
        state.stepIdx = -1;
        state.selectedEdgeId = null;
        const era = currentEra();
        const ph = currentPhase(era);
        if (ph && ph.activeNodes?.length) {
          state.selectedNodeId = ph.activeNodes[0];
        }
        needsAutoFit = true;
        writeStateToHash();
        render();
      });
    });

    document.querySelectorAll("[data-jump-era]").forEach((el) => {
      el.addEventListener("click", () => {
        state.page = el.getAttribute("data-jump-era");
        state.phaseId = el.getAttribute("data-jump-phase") || state.phaseId;
        state.diagramMode = "topology";
        state.stepIdx = -1;
        needsAutoFit = true;
        writeStateToHash();
        render();
      });
    });

    const btnStart = document.getElementById("btn-start-trace");
    if (btnStart) {
      btnStart.addEventListener("click", () => {
        state.stepIdx = 0;
        render();
      });
    }

    const prev = document.getElementById("step-prev");
    if (prev) prev.addEventListener("click", () => { state.stepIdx = Math.max(0, state.stepIdx - 1); render(); });
    const next = document.getElementById("step-next");
    if (next) next.addEventListener("click", () => { state.stepIdx += 1; render(); });
    const reset = document.getElementById("step-reset");
    if (reset) reset.addEventListener("click", () => { state.stepIdx = -1; render(); });

    document.querySelectorAll("[data-node]").forEach((el) => {
      el.addEventListener("click", (ev) => {
        ev.stopPropagation();
        state.selectedNodeId = el.getAttribute("data-node");
        state.selectedEdgeId = null;
        render();
      });
    });

    document.querySelectorAll("[data-edge]").forEach((el) => {
      el.addEventListener("click", (ev) => {
        ev.stopPropagation();
        state.selectedEdgeId = el.getAttribute("data-edge");
        render();
      });
    });

    document.querySelectorAll("[data-seq-step]").forEach((el) => {
      el.addEventListener("click", () => {
        state.stepIdx = Number(el.getAttribute("data-seq-step"));
        render();
      });
    });

    const zin = document.getElementById("btn-zoom-in");
    if (zin) zin.addEventListener("click", () => { state.zoom = Math.min(1.6, +(state.zoom + 0.12).toFixed(2)); render(); });
    const zout = document.getElementById("btn-zoom-out");
    if (zout) zout.addEventListener("click", () => { state.zoom = Math.max(0.35, +(state.zoom - 0.12).toFixed(2)); render(); });
    const zfit = document.getElementById("btn-zoom-fit");
    if (zfit) zfit.addEventListener("click", () => { fitDiagramToStage(currentEra()); render(); });
    const bOrient = document.getElementById("btn-orient");
    if (bOrient) {
      bOrient.addEventListener("click", () => {
        state.orientation = state.orientation === "LR" ? "TB" : "LR";
        fitDiagramToStage(currentEra());
        render();
      });
    }

    const copyBtn = document.getElementById("btn-copy-mermaid");
    if (copyBtn) {
      copyBtn.addEventListener("click", () => {
        const era = currentEra();
        const ph = currentPhase(era);
        const mmd = ph ? ph.topologyMermaid : era?.topologyMermaid;
        if (mmd && navigator.clipboard) {
          navigator.clipboard.writeText(mmd);
          state.copied = true;
          render();
          setTimeout(() => { state.copied = false; render(); }, 1500);
        }
      });
    }

    // Drag-to-pan + wheel-to-zoom on topology stage
    const stage = document.getElementById("diagram-stage");
    const vp = document.getElementById("viewport-g");
    if (stage && vp) {
      let dragging = false;
      let sx = 0, sy = 0, ox = state.panX, oy = state.panY;
      stage.addEventListener("mousedown", (ev) => {
        if (ev.target.closest("button") || ev.target.closest(".svg-node") || ev.target.closest(".svg-edge")) return;
        dragging = true;
        sx = ev.clientX;
        sy = ev.clientY;
        ox = state.panX;
        oy = state.panY;
      });
      window.addEventListener("mousemove", (ev) => {
        if (!dragging) return;
        state.panX = ox + (ev.clientX - sx);
        state.panY = oy + (ev.clientY - sy);
        vp.setAttribute("transform", `translate(${state.panX}, ${state.panY}) scale(${state.zoom})`);
      });
      window.addEventListener("mouseup", () => { dragging = false; });
      stage.addEventListener(
        "wheel",
        (ev) => {
          ev.preventDefault();
          const factor = ev.deltaY < 0 ? 1.07 : 0.93;
          state.zoom = Math.max(0.32, Math.min(1.8, +(state.zoom * factor).toFixed(3)));
          vp.setAttribute("transform", `translate(${state.panX}, ${state.panY}) scale(${state.zoom})`);
        },
        { passive: false }
      );
    }
  }

  syncHashToState();
  window.addEventListener("hashchange", () => {
    syncHashToState();
    needsAutoFit = true;
    render();
  });
  const initEra = currentEra();
  const initPhase = currentPhase(initEra);
  state.selectedNodeId = initPhase?.activeNodes?.[0] || initEra?.nodes?.[0]?.id || null;
  writeStateToHash();
  render();
})();
