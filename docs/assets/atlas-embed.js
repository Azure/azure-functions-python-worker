/**
 * Embeddable Interactive Architecture Atlas for MkDocs Material pages.
 *
 * Mounts into any `<div class="arch-atlas-mount" data-era="py315_r2p2"></div>`
 * while preserving static Markdown & Mermaid documentation below it on the page.
 */
(function () {
  const ZOOM_MIN = 0.12;
  const ZOOM_MAX = 1.8;
  const ZOOM_STEP = 0.12;

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
    host: { stroke: "#f87171", fill: "rgba(127, 29, 29, 0.14)", head: "rgba(153, 27, 27, 0.32)", text: "#fecaca" },
    python: { stroke: "#64748b", fill: "rgba(15, 23, 42, 0.50)", head: "rgba(30, 41, 59, 0.80)", text: "#e2e8f0" },
    "rust-proc": { stroke: "#fb923c", fill: "rgba(67, 20, 7, 0.22)", head: "rgba(124, 45, 18, 0.42)", text: "#fed7aa" },
    rust: { stroke: "#fb923c", fill: "rgba(124, 45, 18, 0.16)", head: "rgba(154, 52, 18, 0.36)", text: "#ffedd5" },
    transport: { stroke: "#a78bfa", fill: "rgba(76, 29, 149, 0.15)", head: "rgba(91, 33, 182, 0.32)", text: "#ddd6fe" },
    bridge: { stroke: "#f472b6", fill: "rgba(131, 24, 67, 0.16)", head: "rgba(157, 23, 77, 0.34)", text: "#fbcfe8" },
    runtime: { stroke: "#34d399", fill: "rgba(6, 78, 59, 0.16)", head: "rgba(6, 95, 70, 0.34)", text: "#a7f3d0" },
    lib: { stroke: "#34d399", fill: "rgba(6, 78, 59, 0.12)", head: "rgba(4, 120, 87, 0.28)", text: "#6ee7b7" },
    ext: { stroke: "#c084fc", fill: "rgba(88, 28, 135, 0.16)", head: "rgba(107, 33, 168, 0.34)", text: "#e9d5ff" },
  };

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

  let activeDisposers = [];

  function mountWidget(hostEl, graph, mountIdx) {
    const eraId = hostEl.getAttribute("data-era") || "py315_r2p2";
    const era = graph.eras.find((e) => e.id === eraId);
    if (!era) return () => {};

    const hasPhases = Boolean(era.phases && era.phases.length);
    const defaultPhase = hostEl.getAttribute("data-phase") || (hasPhases ? "init" : "all");

    const initialOrientation = (hostEl.clientWidth || window.innerWidth) < 520 ? "TB" : "LR";

    const st = {
      mode: "topology", // topology | sequence | compare_phase
      orientation: initialOrientation,
      phaseId: defaultPhase,
      stepIdx: -1,
      selectedNodeId: null,
      selectedEdgeId: null,
      zoom: 0.75,
      panX: 16,
      panY: 16,
      fullscreen: false,
      needsFit: true,
    };

    // Optional URL hash sync (`#phase=worker_logs&mode=sequence`) without breaking heading anchors
    const rawHash = (window.location.hash || "").replace(/^#/, "");
    if (rawHash.startsWith("phase=")) {
      const params = new URLSearchParams(rawHash);
      if (params.get("phase")) st.phaseId = params.get("phase");
      if (params.get("mode")) st.mode = params.get("mode");
    }

    let stageAbort = null;
    const globalAbort = new AbortController();

    function activePhase() {
      if (!hasPhases || st.phaseId === "all") return null;
      return era.phases.find((p) => p.id === st.phaseId) || era.phases[0] || null;
    }

    const initPh = activePhase();
    st.selectedNodeId = initPh?.activeNodes?.[0] || era.nodes[0]?.id || null;

    function fitToStage() {
      const ph = activePhase();
      const layout = window.ArchLayoutEngine.layoutCompoundGraph(
        era,
        st.orientation,
        ph ? ph.topologyEdges : null
      );
      const stageEl = hostEl.querySelector(".aa-stage");
      const availW = Math.max(360, (stageEl ? stageEl.clientWidth : 780) - 28);
      const availH = Math.max(280, (stageEl ? stageEl.clientHeight : 460) - 58);
      const scale = Math.min(1.0, availW / layout.width, availH / layout.height);
      st.zoom = Math.max(ZOOM_MIN, Math.min(ZOOM_MAX, Number(scale.toFixed(3))));
      st.panX = Math.round(((stageEl ? stageEl.clientWidth : availW) - layout.width * st.zoom) / 2);
      st.panY = Math.max(10, Math.round(((stageEl ? stageEl.clientHeight : availH) - layout.height * st.zoom) / 2 - 6));
      const vp = hostEl.querySelector(".aa-viewport-g");
      if (vp) vp.setAttribute("transform", `translate(${st.panX}, ${st.panY}) scale(${st.zoom})`);
    }

    function captureFocus() {
      const a = document.activeElement;
      if (!a || !hostEl.contains(a)) return null;
      for (const attr of ["data-node", "data-edge", "data-seq-step", "data-phase", "data-mode", "data-act"]) {
        if (a.hasAttribute && a.hasAttribute(attr)) {
          return { attr, val: a.getAttribute(attr) };
        }
      }
      if (a.hasAttribute && a.hasAttribute("data-boundary-node")) {
        return { attr: "data-node", val: a.getAttribute("data-boundary-node") };
      }
      return null;
    }

    function restoreFocus(desc) {
      if (!desc) return;
      const target = hostEl.querySelector(`[${desc.attr}="${CSS.escape(desc.val)}"]`);
      if (target && typeof target.focus === "function") {
        target.focus({ preventScroll: true });
      }
    }

    function renderTopology(ph, activeStep) {
      const layout = window.ArchLayoutEngine.layoutCompoundGraph(
        era,
        st.orientation,
        ph ? ph.topologyEdges : null
      );
      const phaseNodes = ph ? new Set(ph.activeNodes) : null;
      const stepNodes = activeStep ? new Set(activeStep.activeNodes) : null;
      const stepEdges = activeStep ? new Set(activeStep.activeEdges) : null;
      const pfx = `m${mountIdx}`;

      const markers = Object.entries(EDGE_PALETTE)
        .map(
          ([k, v]) => `
          <marker id="${pfx}-mk-${k}" markerWidth="9" markerHeight="9" refX="8" refY="4.5" orient="auto">
            <path d="M0,0 L9,4.5 L0,9 Z" fill="${v.color}" />
          </marker>
        `
        )
        .join("");

      const containersSvg = layout.containers
        .map((c) => {
          const t = CONTAINER_TONES[c.tone] || CONTAINER_TONES.python;
          const r = c.isNested ? 9 : 13;
          const rawTitle = c.label.toUpperCase();
          const maxChars = Math.max(16, Math.floor((c.w - 22) / 6.3));
          const displayTitle = rawTitle.length > maxChars ? rawTitle.slice(0, maxChars - 1) + "…" : rawTitle;
          return `
            <g>
              <title>${esc(c.label)}</title>
              <rect x="${c.x}" y="${c.y}" width="${c.w}" height="${c.h}" rx="${r}"
                fill="${t.fill}" stroke="${t.stroke}" stroke-opacity="0.52"
                stroke-width="${c.isNested ? 1.3 : 1.7}"
                ${c.isNested ? 'stroke-dasharray="6 4"' : ""} />
              <rect x="${c.x}" y="${c.y}" width="${c.w}" height="28" rx="${r}" fill="${t.head}" />
              <text x="${c.x + 11}" y="${c.y + 18}" fill="${t.text}" font-size="10.2"
                font-weight="700" letter-spacing="0.03em">${esc(displayTitle)}</text>
            </g>
          `;
        })
        .join("");

      const edgesSvg = layout.edges
        .map((e) => {
          const pal = EDGE_PALETTE[e.kind] || EDGE_PALETTE["inproc-contract"];
          const isStepAct = stepEdges ? stepEdges.has(e.id) : false;
          const isPhaseFlow = Boolean(ph) && !stepEdges;
          const isSel = st.selectedEdgeId === e.id;
          const isDim = stepEdges && !isStepAct;
          const strokeW = isStepAct || isSel ? 3.3 : isPhaseFlow ? 2.3 : 1.9;
          const labelW = Math.max(78, e.label.length * 6.3 + 16);
          const pathId = `${pfx}-ep-${e.id}`;

          return `
            <g class="svg-edge" data-edge="${esc(e.id)}" role="button" tabindex="0"
               aria-pressed="${isSel ? "true" : "false"}"
               aria-label="Inspect protocol edge ${esc(e.label)}"
               style="cursor:pointer" opacity="${isDim ? 0.16 : 0.96}">
              <path d="${e.path}" fill="none" stroke="transparent" stroke-width="14" />
              <path id="${pathId}" d="${e.path}" fill="none" stroke="${pal.color}"
                stroke-width="${strokeW}"
                class="${isStepAct || isPhaseFlow ? "aa-edge-animated" : ""}"
                ${e.dashed && !isStepAct ? 'stroke-dasharray="6 4"' : ""}
                marker-end="url(#${pfx}-mk-${e.kind})" />
              ${
                isStepAct
                  ? `<circle r="4.8" fill="#fff" stroke="${pal.color}" stroke-width="2">
                       <animateMotion dur="1.1s" repeatCount="indefinite">
                         <mpath href="#${pathId}" />
                       </animateMotion>
                     </circle>`
                  : ""
              }
              <g transform="translate(${e.labelX - labelW / 2}, ${e.labelY - 10})">
                <rect width="${labelW}" height="20" rx="5"
                  fill="${isStepAct ? "#1e1b4b" : "#0b1220"}"
                  stroke="${pal.color}" stroke-width="${isStepAct || isSel ? 1.5 : 0.9}" />
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
          const isBypassed = phaseNodes ? !phaseNodes.has(n.id) : false;
          const isStepAct = stepNodes ? stepNodes.has(n.id) : false;
          const isDim = isBypassed || (stepNodes && !isStepAct);
          const isSel = st.selectedNodeId === n.id;
          const borderCol = isStepAct ? "#fb923c" : isSel ? "#38bdf8" : !isBypassed && phaseNodes ? "#3b527e" : "#24324d";
          const shortFile = n.file.split("/").slice(-2).join("/");
          const lineTag = n.line > 1 ? `:${n.line}` : "";

          return `
            <g class="svg-node" data-node="${esc(n.id)}" role="button" tabindex="0"
               aria-pressed="${isSel ? "true" : "false"}"
               aria-label="Inspect component ${esc(n.label)} (${esc(repo.shortName)})"
               transform="translate(${p.x}, ${p.y})"
               style="cursor:pointer" opacity="${isBypassed ? 0.23 : isDim ? 0.32 : 1}">
              <rect width="${p.w}" height="${p.h}" rx="10"
                fill="${isSel ? "#15233c" : "#0e1729"}"
                stroke="${borderCol}" stroke-width="${isStepAct || isSel ? 2.4 : 1.4}" />
              <rect x="0" y="0" width="4.5" height="${p.h}" rx="2.5" fill="${repo.color}" />
              <rect x="13" y="9" width="${repo.shortName.length * 6.2 + 12}" height="17" rx="4"
                fill="rgba(15,23,42,0.9)" stroke="${repo.color}" stroke-width="0.9" />
              <text x="19" y="20.5" fill="${repo.color}" font-size="9.3"
                font-family="ui-monospace, Menlo, monospace" font-weight="700">${esc(repo.shortName)}</text>
              <text x="${p.w - 10}" y="20.5" text-anchor="end" fill="${isBypassed ? "#fbbf24" : "#94a3b8"}" font-size="9.2"
                font-family="ui-monospace, Menlo, monospace">${esc(isBypassed ? "BYPASSED" : n.badge.slice(0, 17))}</text>
              <text x="14" y="46" fill="#f8fafc" font-size="11.8" font-weight="700">
                ${esc(n.label.length > 29 ? n.label.slice(0, 28) + "…" : n.label)}
              </text>
              <text x="14" y="72" fill="#7dd3fc" font-size="9.8"
                font-family="ui-monospace, Menlo, monospace">${esc((shortFile + lineTag).slice(0, 29))}</text>
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
        <div class="aa-stage">
          <svg width="100%" height="100%">
            <defs>${markers}</defs>
            <g class="aa-viewport-g" transform="translate(${st.panX}, ${st.panY}) scale(${st.zoom})">
              ${containersSvg}
              ${nodesSvg}
              ${edgesSvg}
            </g>
          </svg>
          <div class="aa-zoom-hud">
            <button type="button" class="aa-btn" data-act="zoom-in" title="Zoom in">+</button>
            <button type="button" class="aa-btn" data-act="zoom-out" title="Zoom out">−</button>
            <button type="button" class="aa-btn" data-act="zoom-fit">Fit</button>
            <button type="button" class="aa-btn" data-act="orient">${st.orientation === "LR" ? "Left → Right" : "Top → Bottom"}</button>
          </div>
          <div class="aa-legend-hud">
            ${Object.values(EDGE_PALETTE)
              .slice(0, 5)
              .map(
                (p) => `<span style="display:inline-flex;align-items:center;gap:5px">
                  <span style="width:12px;height:2.5px;background:${p.color};display:inline-block"></span>
                  <span>${esc(p.label)}</span>
                </span>`
              )
              .join("")}
          </div>
        </div>
      `;
    }

    function renderInspector(ph) {
      const edgePool = ph ? ph.topologyEdges : era.edges;
      const selEdge = st.selectedEdgeId ? edgePool.find((e) => e.id === st.selectedEdgeId) : null;
      if (selEdge) {
        const srcNode = era.nodes.find((n) => n.id === selEdge.source);
        const tgtNode = era.nodes.find((n) => n.id === selEdge.target);
        const pal = EDGE_PALETTE[selEdge.kind] || EDGE_PALETTE["inproc-contract"];
        return `
          <aside class="aa-inspector">
            <div class="aa-card">
              <div class="aa-kicker" style="color:${pal.color}">Protocol / Interaction Edge</div>
              <div style="font-size:13.5px;font-weight:700;margin-bottom:6px">${esc(selEdge.label)}</div>
              <div style="font-size:11.5px;color:#cbd5e1">
                <div><strong>Channel:</strong> ${esc(pal.label)}</div>
                <div style="margin-top:4px"><strong>From:</strong> ${esc(srcNode?.label)}</div>
                <div style="margin-top:3px"><strong>To:</strong> ${esc(tgtNode?.label)}</div>
              </div>
            </div>
          </aside>
        `;
      }

      const node = era.nodes.find((n) => n.id === st.selectedNodeId) || era.nodes[0];
      if (!node) return `<aside class="aa-inspector"></aside>`;
      const repo = graph.repos[node.repo] || graph.repos["python-worker"];
      const inbound = edgePool.filter((e) => e.target === node.id);
      const outbound = edgePool.filter((e) => e.source === node.id);
      const isBypassed = ph ? !ph.activeNodes.includes(node.id) : false;

      return `
        <aside class="aa-inspector">
          <div class="aa-card">
            <div class="aa-kicker" style="color:${repo.color}">${esc(repo.fullName)}</div>
            <div style="font-size:14px;font-weight:750;margin-bottom:4px">${esc(node.label)}</div>
            ${isBypassed ? `<div style="font-size:10.5px;color:#fbbf24;font-family:var(--aa-mono);margin-bottom:5px">⚡ Bypassed in ${esc(ph.title)}</div>` : ""}
            <div style="font-size:11.5px;color:var(--aa-muted);line-height:1.45">${mdInline(node.role)}</div>
            <a class="aa-gh-link" href="${esc(node.githubUrl)}" target="_blank" rel="noreferrer">
              <span>${esc(node.file)}${node.line > 1 ? `:L${node.line}` : ""}</span>
              <span>GitHub ↗</span>
            </a>
          </div>
          ${
            node.extractedSymbols && node.extractedSymbols.length
              ? `
            <div class="aa-card">
              <div class="aa-kicker">Extracted AST / Rust Symbols (${node.fileLines} LOC)</div>
              <div class="aa-sym-list">
                ${node.extractedSymbols
                  .slice(0, 7)
                  .map((s) => {
                    const baseUrl = node.githubUrl.split("#")[0];
                    return `<a class="aa-sym-item" href="${esc(baseUrl)}#L${s.line}" target="_blank" rel="noreferrer">
                      <span><span style="color:var(--aa-dim)">${esc(s.kind)}</span> ${esc(s.signature)}</span>
                      <span style="color:var(--aa-dim)">L${s.line}</span>
                    </a>`;
                  })
                  .join("")}
              </div>
            </div>`
              : ""
          }
          <div class="aa-card">
            <div class="aa-kicker">Connected Boundaries (${inbound.length} in · ${outbound.length} out)</div>
            <div class="aa-sym-list">
              ${inbound
                .map((e) => {
                  const sn = era.nodes.find((x) => x.id === e.source);
                  return `<button type="button" class="aa-sym-item" data-boundary-node="${esc(e.source)}">
                    <span>← ${esc(sn?.label)}</span><span style="color:var(--aa-dim)">${esc(e.label)}</span>
                  </button>`;
                })
                .join("")}
              ${outbound
                .map((e) => {
                  const tn = era.nodes.find((x) => x.id === e.target);
                  return `<button type="button" class="aa-sym-item" data-boundary-node="${esc(e.target)}">
                    <span>→ ${esc(tn?.label)}</span><span style="color:var(--aa-dim)">${esc(e.label)}</span>
                  </button>`;
                })
                .join("")}
            </div>
          </div>
        </aside>
      `;
    }

    function renderSequence(flow) {
      if (!flow) return `<div class="aa-scroll-pane">No sequence flow defined.</div>`;
      const colW = 182;
      const padX = 110;
      const startY = 88;
      const rowH = 64;
      const width = Math.max(720, padX * 2 + (flow.actors.length - 1) * colW);
      const height = startY + flow.steps.length * rowH + 36;
      const actorX = new Map(flow.actors.map((a, i) => [a.id, padX + i * colW]));
      const pfx = `sq${mountIdx}`;

      return `
        <div class="aa-scroll-pane">
          <svg viewBox="0 0 ${width} ${height}" width="100%" style="min-width:${width}px;display:block">
            <defs>
              <marker id="${pfx}-req" markerWidth="9" markerHeight="9" refX="8" refY="4.5" orient="auto">
                <path d="M0,0 L9,4.5 L0,9 Z" fill="#38bdf8" />
              </marker>
              <marker id="${pfx}-ret" markerWidth="9" markerHeight="9" refX="8" refY="4.5" orient="auto">
                <path d="M0,0 L9,4.5 L0,9 Z" fill="#34d399" />
              </marker>
              <marker id="${pfx}-act" markerWidth="10" markerHeight="10" refX="8.5" refY="5" orient="auto">
                <path d="M0,0 L10,5 L0,10 Z" fill="#fb923c" />
              </marker>
            </defs>
            ${flow.actors
              .map((a) => {
                const x = actorX.get(a.id);
                return `
                  <line x1="${x}" y1="52" x2="${x}" y2="${height - 16}" stroke="#273654" stroke-width="1.5" stroke-dasharray="5 5"/>
                  <rect x="${x - 74}" y="16" width="148" height="34" rx="8" fill="#111b2e" stroke="#3b527e" stroke-width="1.3"/>
                  <text x="${x}" y="37" text-anchor="middle" fill="#f8fafc" font-size="11" font-weight="700">${esc(a.label)}</text>
                `;
              })
              .join("")}
            ${flow.steps
              .map((s, idx) => {
                const x1 = actorX.get(s.from);
                const x2 = actorX.get(s.to);
                const y = startY + idx * rowH;
                const isAct = st.stepIdx === idx;
                const stroke = isAct ? "#fb923c" : s.isReturn ? "#34d399" : "#38bdf8";
                const mk = isAct ? `url(#${pfx}-act)` : s.isReturn ? `url(#${pfx}-ret)` : `url(#${pfx}-req)`;
                const mid = x1 === x2 ? x1 + 60 : (x1 + x2) / 2;
                return `
                  <g data-seq-step="${idx}" role="button" tabindex="0"
                     aria-pressed="${isAct ? "true" : "false"}"
                     aria-label="Step ${idx + 1}: ${esc(s.message)}"
                     style="cursor:pointer">
                    <rect x="14" y="${y - 24}" width="${width - 28}" height="50" rx="7"
                      fill="${isAct ? "rgba(251,146,60,0.12)" : "transparent"}"
                      stroke="${isAct ? "rgba(251,146,60,0.45)" : "transparent"}"/>
                    <circle cx="36" cy="${y}" r="10.5" fill="${isAct ? "#fb923c" : "#162138"}" stroke="${stroke}"/>
                    <text x="36" y="${y + 3.5}" text-anchor="middle" fill="${isAct ? "#090f1d" : "#e2e8f0"}" font-size="10" font-weight="700">${idx + 1}</text>
                    <line x1="${x1}" y1="${y + 4}" x2="${x2 + (x2 > x1 ? -6 : 6)}" y2="${y + 4}"
                      stroke="${stroke}" stroke-width="${isAct ? 2.7 : 1.8}"
                      ${s.isReturn ? 'stroke-dasharray="6 4"' : ""} marker-end="${mk}"/>
                    <text x="${mid}" y="${y - 5}" text-anchor="middle" fill="${isAct ? "#fed7aa" : "#f1f5f9"}" font-size="11" font-weight="650">${esc(s.message)}</text>
                    <text x="${mid}" y="${y + 19}" text-anchor="middle" fill="#94a3b8" font-size="9.8" font-family="ui-monospace, Menlo, monospace">${esc(s.payload)}</text>
                  </g>
                `;
              })
              .join("")}
          </svg>
        </div>
      `;
    }

    function renderComparePhase() {
      const targetId = st.phaseId === "all" ? "init" : st.phaseId;
      const workerEras = graph.eras.filter((e) => e.phases && e.phases.length);
      return `
        <div class="aa-scroll-pane">
          <div class="aa-compare-grid">
            ${workerEras
              .map((e) => {
                const p = e.phases.find((x) => x.id === targetId);
                if (!p) return "";
                return `
                  <div class="aa-card">
                    <div style="font-size:13px;font-weight:750;color:#f8fafc">${esc(e.shortTitle)}</div>
                    <div style="font-size:10.5px;font-family:var(--aa-mono);color:#7dd3fc;margin:3px 0 6px">${esc(p.proto)}</div>
                    <div style="font-size:11.5px;color:#cbd5e1;line-height:1.45">${mdInline(p.summary)}</div>
                    <div class="aa-bypassed">⚡ ${mdInline(p.bypassedNote)}</div>
                  </div>
                `;
              })
              .join("")}
          </div>
        </div>
      `;
    }

    function render() {
      if (stageAbort) {
        stageAbort.abort();
        stageAbort = null;
      }
      const focusDesc = captureFocus();
      const ph = activePhase();
      const seqSource = ph || era.flows[0];
      const stepList = seqSource ? seqSource.steps : [];
      const activeStep =
        seqSource && st.stepIdx >= 0 && st.stepIdx < stepList.length
          ? stepList[st.stepIdx]
          : null;

      hostEl.innerHTML = `
        <section class="arch-atlas-widget ${st.fullscreen ? "is-fullscreen" : ""}" aria-label="Interactive Architecture Explorer">
          <div class="aa-header">
            <div class="aa-title-group">
              <strong style="font-size:13px">Interactive Architecture Explorer</strong>
              <a class="aa-badge" href="${esc(graph.repos["python-worker"].url)}/commit/${esc(graph.git.sha)}" target="_blank" rel="noreferrer">
                worker@${esc(graph.git.shortSha)} · fingerprint ${esc(graph.structuralFingerprint.slice(0, 8))}
              </a>
            </div>
            <div style="display:flex;align-items:center;gap:8px;flex-wrap:wrap">
              <div class="aa-mode-tabs">
                <button type="button" class="aa-tab ${st.mode === "topology" ? "active" : ""}" data-mode="topology">Compound Topology</button>
                <button type="button" class="aa-tab ${st.mode === "sequence" ? "active" : ""}" data-mode="sequence">Sequence Flow</button>
                ${hasPhases ? `<button type="button" class="aa-tab ${st.mode === "compare_phase" ? "active" : ""}" data-mode="compare_phase">Compare 3 Eras</button>` : ""}
              </div>
              <button type="button" class="aa-btn" data-act="fullscreen">
                ${st.fullscreen ? "✕ Exit Fullscreen" : "⛶ Expand"}
              </button>
            </div>
          </div>

          ${
            hasPhases
              ? `
            <div class="aa-phase-bar">
              <span style="font-size:10.5px;font-weight:700;color:var(--aa-dim);text-transform:uppercase">Phase:</span>
              <button type="button" class="aa-phase-pill ${st.phaseId === "all" ? "active" : ""}" data-phase="all">
                <span class="aa-phase-num">∗</span> All Edges
              </button>
              ${(graph.phaseCatalog || [])
                .map(
                  (p) => `
                <button type="button" class="aa-phase-pill ${st.phaseId === p.id ? "active" : ""}" data-phase="${esc(p.id)}" title="${esc(p.proto)}">
                  <span class="aa-phase-num">${esc(p.num)}</span>
                  <span>${esc(p.short)}</span>
                </button>`
                )
                .join("")}
            </div>`
              : ""
          }

          ${
            seqSource && stepList.length
              ? `
            <div class="aa-context-strip">
              <div style="max-width:740px">
                <div style="font-size:12.5px;font-weight:700;color:#f8fafc">${esc(ph ? ph.title : seqSource.title)}</div>
                ${ph ? `<div class="aa-bypassed">⚡ ${mdInline(ph.bypassedNote)}</div>` : ""}
              </div>
              <div style="display:flex;align-items:center;gap:6px;flex-wrap:wrap">
                ${
                  st.stepIdx >= 0
                    ? `
                  <button type="button" class="aa-btn" data-act="step-prev" ${st.stepIdx <= 0 ? "disabled" : ""}>◀ Prev</button>
                  <span class="aa-badge">Hop ${st.stepIdx + 1} / ${stepList.length}</span>
                  <button type="button" class="aa-btn primary" data-act="step-next" ${st.stepIdx >= stepList.length - 1 ? "disabled" : ""}>Next ▶</button>
                  <button type="button" class="aa-btn" data-act="step-reset">Full View</button>`
                    : `<button type="button" class="aa-btn primary" data-act="step-start">▶ Step Hop-by-Hop (${stepList.length})</button>`
                }
              </div>
            </div>`
              : ""
          }

          ${
            activeStep
              ? `<div class="aa-step-banner">
                   <strong>Hop ${st.stepIdx + 1}: ${esc(activeStep.message)}</strong>
                   <span style="font-family:var(--aa-mono);color:#fdba74;font-size:10.5px">[${esc(activeStep.payload)}]</span>
                 </div>`
              : ""
          }

          ${
            st.mode === "topology"
              ? `<div class="aa-split">${renderTopology(ph, activeStep)}${renderInspector(ph)}</div>`
              : st.mode === "sequence"
              ? renderSequence(seqSource)
              : renderComparePhase()
          }
        </section>
      `;

      if (st.needsFit && st.mode === "topology") {
        st.needsFit = false;
        fitToStage();
      }
      bindWidgetEvents();
      restoreFocus(focusDesc);
    }

    function onKeyActivate(el, fn) {
      el.addEventListener("keydown", (ev) => {
        if (ev.key === "Enter" || ev.key === " ") {
          ev.preventDefault();
          ev.stopPropagation();
          fn(ev);
        }
      });
    }

    function bindWidgetEvents() {
      hostEl.querySelectorAll("[data-mode]").forEach((el) => {
        el.addEventListener("click", () => {
          st.mode = el.getAttribute("data-mode");
          if (st.mode === "topology") st.needsFit = true;
          render();
        });
      });

      hostEl.querySelectorAll("[data-phase]").forEach((el) => {
        el.addEventListener("click", () => {
          st.phaseId = el.getAttribute("data-phase");
          st.stepIdx = -1;
          st.selectedEdgeId = null;
          const ph = activePhase();
          if (ph && ph.activeNodes?.length) st.selectedNodeId = ph.activeNodes[0];
          st.needsFit = true;
          render();
        });
      });

      hostEl.querySelectorAll("[data-act]").forEach((el) => {
        el.addEventListener("click", () => {
          const act = el.getAttribute("data-act");
          if (act === "step-start") st.stepIdx = 0;
          else if (act === "step-prev") st.stepIdx = Math.max(0, st.stepIdx - 1);
          else if (act === "step-next") st.stepIdx += 1;
          else if (act === "step-reset") st.stepIdx = -1;
          else if (act === "zoom-in") st.zoom = Math.min(ZOOM_MAX, Math.max(ZOOM_MIN, +(st.zoom + ZOOM_STEP).toFixed(2)));
          else if (act === "zoom-out") st.zoom = Math.max(ZOOM_MIN, Math.min(ZOOM_MAX, +(st.zoom - ZOOM_STEP).toFixed(2)));
          else if (act === "zoom-fit") fitToStage();
          else if (act === "orient") {
            st.orientation = st.orientation === "LR" ? "TB" : "LR";
            st.needsFit = true;
          } else if (act === "fullscreen") {
            st.fullscreen = !st.fullscreen;
            document.body.style.overflow = st.fullscreen ? "hidden" : "";
            st.needsFit = true;
          }
          render();
        });
      });

      hostEl.querySelectorAll("[data-node]").forEach((el) => {
        const fn = (ev) => {
          ev.stopPropagation();
          st.selectedNodeId = el.getAttribute("data-node");
          st.selectedEdgeId = null;
          render();
        };
        el.addEventListener("click", fn);
        onKeyActivate(el, fn);
      });

      hostEl.querySelectorAll("[data-boundary-node]").forEach((el) => {
        el.addEventListener("click", (ev) => {
          ev.stopPropagation();
          st.selectedNodeId = el.getAttribute("data-boundary-node");
          st.selectedEdgeId = null;
          render();
        });
      });

      hostEl.querySelectorAll("[data-edge]").forEach((el) => {
        const fn = (ev) => {
          ev.stopPropagation();
          st.selectedEdgeId = el.getAttribute("data-edge");
          render();
        };
        el.addEventListener("click", fn);
        onKeyActivate(el, fn);
      });

      hostEl.querySelectorAll("[data-seq-step]").forEach((el) => {
        const fn = () => {
          st.stepIdx = Number(el.getAttribute("data-seq-step"));
          render();
        };
        el.addEventListener("click", fn);
        onKeyActivate(el, fn);
      });

      const stage = hostEl.querySelector(".aa-stage");
      const vp = hostEl.querySelector(".aa-viewport-g");
      if (stage && vp) {
        stageAbort = new AbortController();
        const { signal } = stageAbort;
        let activePointerId = null;
        let sx = 0, sy = 0, ox = st.panX, oy = st.panY;

        const endPan = (ev) => {
          if (activePointerId === null || (ev && ev.pointerId !== activePointerId)) return;
          if (stage.hasPointerCapture && stage.hasPointerCapture(activePointerId)) {
            try { stage.releasePointerCapture(activePointerId); } catch (_) {}
          }
          activePointerId = null;
        };

        stage.addEventListener("pointerdown", (ev) => {
          if (ev.pointerType === "mouse" && ev.button !== 0) return;
          if (ev.target.closest("button") || ev.target.closest(".svg-node") || ev.target.closest(".svg-edge")) return;
          activePointerId = ev.pointerId;
          sx = ev.clientX;
          sy = ev.clientY;
          ox = st.panX;
          oy = st.panY;
          if (stage.setPointerCapture) {
            try { stage.setPointerCapture(ev.pointerId); } catch (_) {}
          }
        });

        window.addEventListener(
          "pointermove",
          (ev) => {
            if (activePointerId === null || ev.pointerId !== activePointerId) return;
            st.panX = ox + (ev.clientX - sx);
            st.panY = oy + (ev.clientY - sy);
            vp.setAttribute("transform", `translate(${st.panX}, ${st.panY}) scale(${st.zoom})`);
          },
          { signal }
        );
        window.addEventListener("pointerup", endPan, { signal });
        window.addEventListener("pointercancel", endPan, { signal });
        stage.addEventListener("lostpointercapture", endPan);
        stage.addEventListener(
          "wheel",
          (ev) => {
            ev.preventDefault();
            const factor = ev.deltaY < 0 ? 1.07 : 0.93;
            st.zoom = Math.max(ZOOM_MIN, Math.min(ZOOM_MAX, +(st.zoom * factor).toFixed(3)));
            vp.setAttribute("transform", `translate(${st.panX}, ${st.panY}) scale(${st.zoom})`);
          },
          { passive: false }
        );
      }
    }

    window.addEventListener(
      "keydown",
      (ev) => {
        if (ev.key === "Escape" && st.fullscreen) {
          st.fullscreen = false;
          document.body.style.overflow = "";
          st.needsFit = true;
          render();
        }
      },
      { signal: globalAbort.signal }
    );

    render();

    return () => {
      if (stageAbort) stageAbort.abort();
      globalAbort.abort();
      document.body.style.overflow = "";
    };
  }

  function initAllMounts() {
    activeDisposers.forEach((fn) => fn());
    activeDisposers = [];
    const graph = window.__ARCH_GRAPH__;
    if (!graph || !window.ArchLayoutEngine) return;
    document.querySelectorAll(".arch-atlas-mount").forEach((el, idx) => {
      activeDisposers.push(mountWidget(el, graph, idx));
    });
  }

  if (window.document$ && typeof window.document$.subscribe === "function") {
    window.document$.subscribe(() => initAllMounts());
  } else if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initAllMounts);
  } else {
    initAllMounts();
  }
})();
