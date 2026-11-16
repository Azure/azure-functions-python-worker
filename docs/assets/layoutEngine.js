/**
 * Deterministic 2D Tiered Compound Architecture Layout Engine.
 *
 * Balances horizontal and vertical aspect ratio by:
 *  1. Grouping peer root containers into topological tiers (stacking independent
 *     repos like `python-library` and `python-extensions` in the same column).
 *  2. Using orthogonal intra-container stacking (vertical leaf stacks inside
 *     left-to-right swimlanes) to prevent 1D horizontal sprawl.
 *  3. Allocating ports per card face (top/bottom/left/right) with non-overlapping corridors.
 */
(function () {
  const NODE_W = 228;
  const NODE_H = 86;

  function computeRanks(nodes, edges) {
    const ids = nodes.map((n) => n.id);
    const incoming = new Map(ids.map((id) => [id, []]));
    for (const e of edges) {
      if (incoming.has(e.target) && e.source !== e.target) {
        incoming.get(e.target).push(e.source);
      }
    }
    const memo = new Map();
    const visiting = new Set();

    function rankOf(id) {
      if (memo.has(id)) return memo.get(id);
      if (visiting.has(id)) return 0;
      visiting.add(id);
      let r = 0;
      for (const pred of incoming.get(id) || []) {
        r = Math.max(r, rankOf(pred) + 1);
      }
      visiting.delete(id);
      memo.set(id, r);
      return r;
    }

    for (const id of ids) rankOf(id);
    return memo;
  }

  function shiftSubtree(box, dx, dy, subById, nodePositions) {
    box.x += dx;
    box.y += dy;
    for (const sid of box.subIds || []) {
      const sb = subById.get(sid);
      if (sb) {
        sb.x += dx;
        sb.y += dy;
      }
    }
    for (const lid of box.leafIds || []) {
      const np = nodePositions.get(lid);
      if (np) {
        np.x += dx;
        np.y += dy;
      }
    }
  }

  function layoutCompoundGraph(era, orientation, edgesOverride) {
    const isLR = orientation !== "TB";
    const activeEdgeList = edgesOverride || era.edges;
    const containerById = new Map(era.containers.map((c) => [c.id, c]));
    const childContainers = new Map();
    for (const c of era.containers) {
      const pid = c.parentId || "__root__";
      if (!childContainers.has(pid)) childContainers.set(pid, []);
      childContainers.get(pid).push(c);
    }

    const leavesByContainer = new Map();
    for (const n of era.nodes) {
      if (!leavesByContainer.has(n.containerId)) leavesByContainer.set(n.containerId, []);
      leavesByContainer.get(n.containerId).push(n);
    }

    const ranks = computeRanks(era.nodes, era.edges);
    const nodePositions = new Map();
    const containerBoxes = [];

    function descendantLeaves(cid) {
      const own = [...(leavesByContainer.get(cid) || [])];
      for (const sub of childContainers.get(cid) || []) {
        own.push(...descendantLeaves(sub.id));
      }
      return own;
    }

    function rootOfContainer(cid) {
      let cur = containerById.get(cid);
      while (cur && cur.parentId) {
        cur = containerById.get(cur.parentId);
      }
      return cur ? cur.id : cid;
    }

    const nodeRootMap = new Map(era.nodes.map((n) => [n.id, rootOfContainer(n.containerId)]));
    const rawRoots = [...(childContainers.get("__root__") || [])];

    // Compute root-container topological tier from cross-root edges when c.tier is omitted
    const rootPreds = new Map(rawRoots.map((r) => [r.id, new Set()]));
    for (const e of era.edges) {
      const sr = nodeRootMap.get(e.source);
      const tr = nodeRootMap.get(e.target);
      if (sr && tr && sr !== tr && rootPreds.has(tr)) {
        rootPreds.get(tr).add(sr);
      }
    }
    const computedTier = new Map();
    const visitingRoot = new Set();
    function getTier(rc) {
      if (typeof rc.tier === "number") return rc.tier;
      if (computedTier.has(rc.id)) return computedTier.get(rc.id);
      if (visitingRoot.has(rc.id)) return 0;
      visitingRoot.add(rc.id);
      let t = 0;
      for (const pId of rootPreds.get(rc.id) || []) {
        const pObj = containerById.get(pId);
        if (pObj) t = Math.max(t, getTier(pObj) + 1);
      }
      visitingRoot.delete(rc.id);
      computedTier.set(rc.id, t);
      return t;
    }

    const tiersMap = new Map();
    for (const rc of rawRoots) {
      const t = getTier(rc);
      if (!tiersMap.has(t)) tiersMap.set(t, []);
      tiersMap.get(t).push(rc);
    }
    const sortedTierKeys = [...tiersMap.keys()].sort((a, b) => a - b);

    const PAD_TOP = 40;
    const PAD_SIDE = 16;
    const PAD_BOTTOM = 18;
    const LEAF_COL_GAP = 48;
    const LEAF_ROW_GAP = 48;
    const SUB_GAP = 68;
    const SUB_STACK_GAP = 48;
    const PEER_ROOT_GAP = 50;
    const TIER_GAP = 76;

    // Orthogonal leaf placement: in LR mode leaves stack vertically (up to container.maxCols columns)
    function layoutLeafGroup(containerObj, leaves, originX, originY) {
      if (!leaves.length) return { w: NODE_W, h: NODE_H };
      const ordered = [...leaves].sort((a, b) => (ranks.get(a.id) || 0) - (ranks.get(b.id) || 0));
      const maxSpan = Math.max(1, containerObj?.maxCols || 1);

      let cols, rows;
      if (isLR) {
        cols = Math.min(ordered.length, maxSpan);
        rows = Math.ceil(ordered.length / cols);
      } else {
        rows = Math.min(ordered.length, maxSpan);
        cols = Math.ceil(ordered.length / rows);
      }

      ordered.forEach((node, idx) => {
        const c = isLR ? idx % cols : Math.floor(idx / rows);
        const r = isLR ? Math.floor(idx / cols) : idx % rows;
        const x = originX + c * (NODE_W + LEAF_COL_GAP);
        const y = originY + r * (NODE_H + LEAF_ROW_GAP);
        nodePositions.set(node.id, { x, y, w: NODE_W, h: NODE_H, node });
      });

      return {
        w: cols * NODE_W + (cols - 1) * LEAF_COL_GAP,
        h: rows * NODE_H + (rows - 1) * LEAF_ROW_GAP,
      };
    }

    // Build a root container at local (0, 0) and then translate into its tier slot
    function buildRootBoxAtOrigin(rc) {
      const subs = [...(childContainers.get(rc.id) || [])].sort((a, b) => {
        const la = descendantLeaves(a.id);
        const lb = descendantLeaves(b.id);
        const avgA = la.length ? la.reduce((s, n) => s + (ranks.get(n.id) || 0), 0) / la.length : 0;
        const avgB = lb.length ? lb.reduce((s, n) => s + (ranks.get(n.id) || 0), 0) / lb.length : 0;
        return avgA - avgB;
      });

      if (subs.length === 0) {
        const leaves = leavesByContainer.get(rc.id) || [];
        const inner = layoutLeafGroup(rc, leaves, PAD_SIDE, PAD_TOP);
        return {
          id: rc.id,
          label: rc.label,
          tone: rc.tone,
          isNested: false,
          x: 0,
          y: 0,
          w: inner.w + PAD_SIDE * 2,
          h: inner.h + PAD_TOP + PAD_BOTTOM,
          leafIds: leaves.map((l) => l.id),
          subIds: [],
        };
      }

      const stackSubs = rc.subFlow === "stack";
      // Flow subs along primary axis unless subFlow === "stack" (which stacks along cross axis)
      const subsHorizontal = isLR ? !stackSubs : stackSubs;
      const gap = stackSubs ? SUB_STACK_GAP : SUB_GAP;

      let cursor = subsHorizontal ? PAD_SIDE : PAD_TOP;
      const localSubs = [];
      let maxOrtho = 0;

      for (const sub of subs) {
        const leaves = leavesByContainer.get(sub.id) || [];
        const sx = subsHorizontal ? cursor : PAD_SIDE;
        const sy = subsHorizontal ? PAD_TOP : cursor;
        const inner = layoutLeafGroup(sub, leaves, sx + PAD_SIDE, sy + PAD_TOP);
        const sw = inner.w + PAD_SIDE * 2;
        const sh = inner.h + PAD_TOP + PAD_BOTTOM;
        localSubs.push({
          id: sub.id,
          label: sub.label,
          tone: sub.tone,
          isNested: true,
          x: sx,
          y: sy,
          w: sw,
          h: sh,
          leafIds: leaves.map((l) => l.id),
        });
        maxOrtho = Math.max(maxOrtho, subsHorizontal ? sh : sw);
        cursor += (subsHorizontal ? sw : sh) + gap;
      }

      for (const sBox of localSubs) {
        const delta = subsHorizontal ? (maxOrtho - sBox.h) / 2 : (maxOrtho - sBox.w) / 2;
        if (delta > 0) {
          if (subsHorizontal) sBox.y += delta;
          else sBox.x += delta;
          for (const lid of sBox.leafIds) {
            const np = nodePositions.get(lid);
            if (np) {
              if (subsHorizontal) np.y += delta;
              else np.x += delta;
            }
          }
        }
        containerBoxes.push(sBox);
      }

      const totalFlowSpan =
        localSubs.reduce((acc, b) => acc + (subsHorizontal ? b.w : b.h), 0) +
        Math.max(0, localSubs.length - 1) * gap;

      return {
        id: rc.id,
        label: rc.label,
        tone: rc.tone,
        isNested: false,
        x: 0,
        y: 0,
        w: subsHorizontal ? totalFlowSpan + PAD_SIDE * 2 : maxOrtho + PAD_SIDE * 2,
        h: subsHorizontal ? maxOrtho + PAD_TOP + PAD_BOTTOM : totalFlowSpan + PAD_TOP + PAD_BOTTOM,
        leafIds: descendantLeaves(rc.id).map((l) => l.id),
        subIds: localSubs.map((b) => b.id),
      };
    }

    const subById = new Map();
    const placedTiers = [];
    const placedRoots = [];
    let primaryCursor = 36;

    for (const tk of sortedTierKeys) {
      const peerRoots = tiersMap.get(tk) || [];
      const builtPeers = peerRoots.map((rc) => {
        const box = buildRootBoxAtOrigin(rc);
        for (const sb of containerBoxes) subById.set(sb.id, sb);
        return box;
      });

      const tierPrimarySpan = Math.max(...builtPeers.map((b) => (isLR ? b.w : b.h)));
      let crossCursor = 36;

      for (const pBox of builtPeers) {
        const primaryAlign = (tierPrimarySpan - (isLR ? pBox.w : pBox.h)) / 2;
        const dx = isLR ? primaryCursor + primaryAlign : crossCursor;
        const dy = isLR ? crossCursor : primaryCursor + primaryAlign;
        shiftSubtree(pBox, dx, dy, subById, nodePositions);
        crossCursor += (isLR ? pBox.h : pBox.w) + PEER_ROOT_GAP;
        placedRoots.push(pBox);
      }

      const tierCrossSpan = crossCursor - 36 - PEER_ROOT_GAP;
      placedTiers.push({ peers: builtPeers, crossSpan: tierCrossSpan });
      primaryCursor += tierPrimarySpan + TIER_GAP;
    }

    // Balance all tier columns along the cross axis
    const maxTierCross = Math.max(...placedTiers.map((t) => t.crossSpan), 220);
    for (const tier of placedTiers) {
      const delta = (maxTierCross - tier.crossSpan) / 2;
      if (delta > 0) {
        for (const pBox of tier.peers) {
          shiftSubtree(pBox, isLR ? 0 : delta, isLR ? delta : 0, subById, nodePositions);
        }
      }
    }

    const allContainers = [...placedRoots, ...containerBoxes];

    // Classify every edge's exit/entry card faces (top/bottom/left/right) and sort ports per face
    const facePorts = new Map();
    const edgeMeta = [];

    function addPort(nodeId, face, edgeId, sortCoord) {
      const key = `${nodeId}:${face}`;
      if (!facePorts.has(key)) facePorts.set(key, []);
      facePorts.get(key).push({ edgeId, sortCoord });
    }

    for (const e of activeEdgeList) {
      const s = nodePositions.get(e.source);
      const t = nodePositions.get(e.target);
      if (!s || !t) continue;

      const scx = s.x + s.w / 2;
      const scy = s.y + s.h / 2;
      const tcx = t.x + t.w / 2;
      const tcy = t.y + t.h / 2;
      const dx = tcx - scx;
      const dy = tcy - scy;

      let sFace, tFace, mode;
      const useVertical = isLR
        ? Math.abs(dx) < NODE_W * 0.68
        : Math.abs(dy) >= NODE_H * 0.68;

      if (useVertical) {
        mode = "V";
        sFace = dy >= 0 ? "bottom" : "top";
        tFace = dy >= 0 ? "top" : "bottom";
        addPort(e.source, sFace, e.id, tcx);
        addPort(e.target, tFace, e.id, scx);
      } else if (dx >= 0) {
        mode = "H_FWD";
        sFace = "right";
        tFace = "left";
        addPort(e.source, sFace, e.id, tcy);
        addPort(e.target, tFace, e.id, scy);
      } else {
        mode = "H_REV";
        sFace = "left";
        tFace = "right";
        addPort(e.source, sFace, e.id, tcy);
        addPort(e.target, tFace, e.id, scy);
      }
      edgeMeta.push({ e, s, t, sFace, tFace, mode });
    }

    for (const list of facePorts.values()) {
      list.sort((a, b) => a.sortCoord - b.sortCoord);
    }

    function portFraction(nodeId, face, edgeId) {
      const list = facePorts.get(`${nodeId}:${face}`) || [{ edgeId }];
      const idx = list.findIndex((x) => x.edgeId === edgeId);
      return (Math.max(0, idx) + 1) / (list.length + 1);
    }

    const pairKeys = new Set(activeEdgeList.map((e) => `${e.source}->${e.target}`));

    const routedEdges = edgeMeta.map(({ e, s, t, sFace, tFace, mode }, idx) => {
      const hasReverse = pairKeys.has(`${e.target}->${e.source}`);
      const sf = portFraction(e.source, sFace, e.id);
      const tf = portFraction(e.target, tFace, e.id);

      let x1, y1, x2, y2, path, labelX, labelY;
      if (mode === "V") {
        const downward = sFace === "bottom";
        const laneShift = hasReverse ? (downward ? -22 : 22) : 0;
        x1 = s.x + 28 + sf * (s.w - 56) + laneShift;
        y1 = downward ? s.y + s.h : s.y;
        x2 = t.x + 28 + tf * (t.w - 56) + laneShift;
        y2 = downward ? t.y : t.y + t.h;
        const dy = Math.max(24, Math.abs(y2 - y1) * 0.45);
        path = downward
          ? `M ${x1} ${y1} C ${x1} ${y1 + dy}, ${x2} ${y2 - dy}, ${x2} ${y2}`
          : `M ${x1} ${y1} C ${x1} ${y1 - dy}, ${x2} ${y2 + dy}, ${x2} ${y2}`;
        labelX = (x1 + x2) / 2;
        labelY = (y1 + y2) / 2;
      } else if (mode === "H_FWD") {
        x1 = s.x + s.w;
        x2 = t.x;
        const laneShift = hasReverse ? -16 : 0;
        y1 = s.y + 16 + sf * (s.h - 32) + laneShift;
        y2 = t.y + 16 + tf * (t.h - 32) + laneShift;
        const dx = Math.max(42, Math.abs(x2 - x1) * 0.44);
        const bow = hasReverse ? -20 : 0;
        path = `M ${x1} ${y1} C ${x1 + dx} ${y1 + bow}, ${x2 - dx} ${y2 + bow}, ${x2} ${y2}`;
        const shortGap = Math.abs(x2 - x1) < 90;
        const tParam = shortGap ? 0.5 : 0.48 + ((idx % 3) - 1) * 0.08;
        labelX = x1 + (x2 - x1) * tParam;
        labelY = shortGap ? Math.min(y1, y2) - 22 : y1 + (y2 - y1) * tParam + bow * 0.7;
      } else {
        x1 = s.x;
        x2 = t.x + t.w;
        const laneShift = hasReverse ? 16 : 0;
        y1 = s.y + 16 + sf * (s.h - 32) + laneShift;
        y2 = t.y + 16 + tf * (t.h - 32) + laneShift;
        const dx = Math.max(42, Math.abs(x1 - x2) * 0.44);
        const bow = hasReverse ? 22 : 0;
        path = `M ${x1} ${y1} C ${x1 - dx} ${y1 + bow}, ${x2 + dx} ${y2 + bow}, ${x2} ${y2}`;
        const tParam = 0.5 + ((idx % 3) - 1) * 0.08;
        labelX = x1 + (x2 - x1) * tParam;
        labelY = y1 + (y2 - y1) * tParam + bow * 0.7;
      }

      return { ...e, x1, y1, x2, y2, path, labelX, labelY };
    });

    const totalW = Math.max(...allContainers.map((c) => c.x + c.w), 640) + 44;
    const totalH = Math.max(...allContainers.map((c) => c.y + c.h), 380) + 44;

    return {
      width: totalW,
      height: totalH,
      containers: allContainers,
      nodes: [...nodePositions.values()],
      edges: routedEdges,
    };
  }

  window.ArchLayoutEngine = { layoutCompoundGraph };
})();
