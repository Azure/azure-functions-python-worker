/**
 * Deterministic Compound Sugiyama / Swimlane Architecture Layout Engine.
 *
 * Computes topological ranks, nested container swimlanes, port ordering, and
 * bidirectional cubic/orthogonal SVG paths with zero hardcoded coordinates.
 */
(function () {
  const NODE_W = 252;
  const NODE_H = 92;

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

  function layoutCompoundGraph(era, orientation, edgesOverride) {
    const isLR = orientation !== "TB";
    const activeEdgeList = edgesOverride || era.edges;
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

    const rootContainers = [...(childContainers.get("__root__") || [])].sort((a, b) => {
      const la = descendantLeaves(a.id);
      const lb = descendantLeaves(b.id);
      const avgA = la.length ? la.reduce((s, n) => s + (ranks.get(n.id) || 0), 0) / la.length : 0;
      const avgB = lb.length ? lb.reduce((s, n) => s + (ranks.get(n.id) || 0), 0) / lb.length : 0;
      return avgA - avgB;
    });

    const PAD_TOP = 44;
    const PAD_SIDE = 22;
    const PAD_BOTTOM = 22;
    const COL_GAP = isLR ? 132 : 44;
    const ROW_GAP = isLR ? 34 : 84;
    const SUB_GAP = isLR ? 108 : 64;
    const ROOT_GAP = isLR ? 138 : 92;

    function layoutLeafGroup(leaves, originX, originY) {
      if (!leaves.length) return { w: 180, h: 90 };
      const uniqueRanks = [...new Set(leaves.map((n) => ranks.get(n.id) || 0))].sort((a, b) => a - b);
      const rankIndex = new Map(uniqueRanks.map((r, i) => [r, i]));

      const buckets = new Map();
      for (const n of leaves) {
        const ri = rankIndex.get(ranks.get(n.id) || 0) || 0;
        if (!buckets.has(ri)) buckets.set(ri, []);
        buckets.get(ri).push(n);
      }

      let maxCrossCount = 1;
      for (const arr of buckets.values()) {
        maxCrossCount = Math.max(maxCrossCount, arr.length);
      }

      const numLayers = uniqueRanks.length;
      const totalPrimary = isLR
        ? numLayers * NODE_W + (numLayers - 1) * COL_GAP
        : numLayers * NODE_H + (numLayers - 1) * ROW_GAP;
      const totalCross = isLR
        ? maxCrossCount * NODE_H + (maxCrossCount - 1) * ROW_GAP
        : maxCrossCount * NODE_W + (maxCrossCount - 1) * COL_GAP;

      for (const [layerIdx, arr] of buckets.entries()) {
        const spanCross = isLR
          ? arr.length * NODE_H + (arr.length - 1) * ROW_GAP
          : arr.length * NODE_W + (arr.length - 1) * COL_GAP;
        const crossOffset = (totalCross - spanCross) / 2;

        arr.forEach((node, idx) => {
          const x = isLR
            ? originX + layerIdx * (NODE_W + COL_GAP)
            : originX + crossOffset + idx * (NODE_W + COL_GAP);
          const y = isLR
            ? originY + crossOffset + idx * (NODE_H + ROW_GAP)
            : originY + layerIdx * (NODE_H + ROW_GAP);
          nodePositions.set(node.id, { x, y, w: NODE_W, h: NODE_H, node });
        });
      }

      return {
        w: isLR ? totalPrimary : totalCross,
        h: isLR ? totalCross : totalPrimary,
      };
    }

    let cursorPrimary = 36;
    const rootMetrics = rootContainers.map((rc) => {
      const subs = [...(childContainers.get(rc.id) || [])].sort((a, b) => {
        const la = descendantLeaves(a.id);
        const lb = descendantLeaves(b.id);
        const avgA = la.length ? la.reduce((s, n) => s + (ranks.get(n.id) || 0), 0) / la.length : 0;
        const avgB = lb.length ? lb.reduce((s, n) => s + (ranks.get(n.id) || 0), 0) / lb.length : 0;
        return avgA - avgB;
      });
      return { rc, subs };
    });

    const placedRoots = [];
    for (const { rc, subs } of rootMetrics) {
      if (subs.length === 0) {
        const leaves = leavesByContainer.get(rc.id) || [];
        const startX = isLR ? cursorPrimary + PAD_SIDE : 36 + PAD_SIDE;
        const startY = isLR ? 36 + PAD_TOP : cursorPrimary + PAD_TOP;
        const inner = layoutLeafGroup(leaves, startX, startY);
        const boxW = inner.w + PAD_SIDE * 2;
        const boxH = inner.h + PAD_TOP + PAD_BOTTOM;
        placedRoots.push({
          id: rc.id,
          label: rc.label,
          tone: rc.tone,
          isNested: false,
          x: isLR ? cursorPrimary : 36,
          y: isLR ? 36 : cursorPrimary,
          w: boxW,
          h: boxH,
          leafIds: leaves.map((l) => l.id),
          subIds: [],
        });
        cursorPrimary += (isLR ? boxW : boxH) + ROOT_GAP;
      } else {
        let subCursor = (isLR ? cursorPrimary : 36) + PAD_SIDE;
        if (!isLR) subCursor = cursorPrimary + PAD_TOP;

        const subBoxes = [];
        let maxSubCross = 0;

        for (const sub of subs) {
          const leaves = leavesByContainer.get(sub.id) || [];
          const sx = isLR ? subCursor + PAD_SIDE : 36 + PAD_SIDE * 2;
          const sy = isLR ? 36 + PAD_TOP * 2 : subCursor + PAD_TOP;
          const inner = layoutLeafGroup(leaves, sx, sy);
          const sw = inner.w + PAD_SIDE * 2;
          const sh = inner.h + PAD_TOP + PAD_BOTTOM;
          subBoxes.push({
            id: sub.id,
            label: sub.label,
            tone: sub.tone,
            isNested: true,
            x: isLR ? subCursor : 36 + PAD_SIDE,
            y: isLR ? 36 + PAD_TOP : subCursor,
            w: sw,
            h: sh,
            leafIds: leaves.map((l) => l.id),
          });
          maxSubCross = Math.max(maxSubCross, isLR ? sh : sw);
          subCursor += (isLR ? sw : sh) + SUB_GAP;
        }

        for (const sBox of subBoxes) {
          const delta = isLR ? (maxSubCross - sBox.h) / 2 : (maxSubCross - sBox.w) / 2;
          if (delta > 0) {
            if (isLR) sBox.y += delta;
            else sBox.x += delta;
            for (const lid of sBox.leafIds) {
              const np = nodePositions.get(lid);
              if (np) {
                if (isLR) np.y += delta;
                else np.x += delta;
              }
            }
          }
          containerBoxes.push(sBox);
        }

        const totalSubSpan =
          subBoxes.reduce((acc, b) => acc + (isLR ? b.w : b.h), 0) +
          Math.max(0, subBoxes.length - 1) * SUB_GAP;
        const boxW = isLR ? totalSubSpan + PAD_SIDE * 2 : maxSubCross + PAD_SIDE * 2;
        const boxH = isLR ? maxSubCross + PAD_TOP + PAD_BOTTOM : totalSubSpan + PAD_TOP + PAD_BOTTOM;

        placedRoots.push({
          id: rc.id,
          label: rc.label,
          tone: rc.tone,
          isNested: false,
          x: isLR ? cursorPrimary : 36,
          y: isLR ? 36 : cursorPrimary,
          w: boxW,
          h: boxH,
          leafIds: descendantLeaves(rc.id).map((l) => l.id),
          subIds: subBoxes.map((b) => b.id),
        });
        cursorPrimary += (isLR ? boxW : boxH) + ROOT_GAP;
      }
    }

    const maxRootCross = Math.max(...placedRoots.map((r) => (isLR ? r.h : r.w)), 240);
    const subById = new Map(containerBoxes.map((b) => [b.id, b]));
    for (const rBox of placedRoots) {
      const delta = isLR ? (maxRootCross - rBox.h) / 2 : (maxRootCross - rBox.w) / 2;
      if (delta > 0) {
        if (isLR) rBox.y += delta;
        else rBox.x += delta;
        for (const sid of rBox.subIds) {
          const sb = subById.get(sid);
          if (sb) {
            if (isLR) sb.y += delta;
            else sb.x += delta;
          }
        }
        for (const lid of rBox.leafIds) {
          const np = nodePositions.get(lid);
          if (np) {
            if (isLR) np.y += delta;
            else np.x += delta;
          }
        }
      }
    }

    const allContainers = [...placedRoots, ...containerBoxes];

    const outPorts = new Map();
    const inPorts = new Map();
    for (const e of activeEdgeList) {
      if (!outPorts.has(e.source)) outPorts.set(e.source, []);
      outPorts.get(e.source).push(e.id);
      if (!inPorts.has(e.target)) inPorts.set(e.target, []);
      inPorts.get(e.target).push(e.id);
    }

    for (const [, eids] of outPorts.entries()) {
      eids.sort((a, b) => {
        const ea = activeEdgeList.find((x) => x.id === a);
        const eb = activeEdgeList.find((x) => x.id === b);
        const pa = nodePositions.get(ea.target);
        const pb = nodePositions.get(eb.target);
        return isLR ? (pa?.y || 0) - (pb?.y || 0) : (pa?.x || 0) - (pb?.x || 0);
      });
    }
    for (const [, eids] of inPorts.entries()) {
      eids.sort((a, b) => {
        const ea = activeEdgeList.find((x) => x.id === a);
        const eb = activeEdgeList.find((x) => x.id === b);
        const pa = nodePositions.get(ea.source);
        const pb = nodePositions.get(eb.source);
        return isLR ? (pa?.y || 0) - (pb?.y || 0) : (pa?.x || 0) - (pb?.x || 0);
      });
    }

    const pairKeys = new Set(activeEdgeList.map((e) => `${e.source}->${e.target}`));

    const routedEdges = activeEdgeList
      .map((e, idx) => {
        const s = nodePositions.get(e.source);
        const t = nodePositions.get(e.target);
        if (!s || !t) return null;

        const hasReverse = pairKeys.has(`${e.target}->${e.source}`);
        const sList = outPorts.get(e.source) || [e.id];
        const tList = inPorts.get(e.target) || [e.id];
        const sSlot = (sList.indexOf(e.id) + 1) / (sList.length + 1);
        const tSlot = (tList.indexOf(e.id) + 1) / (tList.length + 1);

        let x1, y1, x2, y2, path, labelX, labelY;
        if (isLR) {
          const sameColumn = Math.abs(s.x - t.x) < 20;
          if (sameColumn) {
            const xOff = hasReverse ? (s.y < t.y ? -22 : 22) : 0;
            x1 = s.x + s.w * 0.5 + xOff;
            y1 = s.y < t.y ? s.y + s.h : s.y;
            x2 = t.x + t.w * 0.5 + xOff;
            y2 = s.y < t.y ? t.y : t.y + t.h;
            path = `M ${x1} ${y1} L ${x2} ${y2}`;
            labelX = x1;
            labelY = (y1 + y2) / 2;
          } else if (s.x < t.x) {
            x1 = s.x + s.w;
            x2 = t.x;
            const laneShift = hasReverse ? -18 : 0;
            y1 = s.y + 18 + sSlot * (s.h - 36) + laneShift;
            y2 = t.y + 18 + tSlot * (t.h - 36) + laneShift;
            const dx = Math.max(48, Math.abs(x2 - x1) * 0.45);
            const bow = hasReverse ? -24 : 0;
            path = `M ${x1} ${y1} C ${x1 + dx} ${y1 + bow}, ${x2 - dx} ${y2 + bow}, ${x2} ${y2}`;
            const tParam = 0.48 + ((idx % 3) - 1) * 0.06;
            labelX = x1 + (x2 - x1) * tParam;
            labelY = y1 + (y2 - y1) * tParam + bow * 0.72;
          } else {
            x1 = s.x;
            x2 = t.x + t.w;
            const laneShift = hasReverse ? 18 : 0;
            y1 = s.y + 18 + sSlot * (s.h - 36) + laneShift;
            y2 = t.y + 18 + tSlot * (t.h - 36) + laneShift;
            const dx = Math.max(48, Math.abs(x1 - x2) * 0.45);
            const bow = hasReverse ? 26 : 0;
            path = `M ${x1} ${y1} C ${x1 - dx} ${y1 + bow}, ${x2 + dx} ${y2 + bow}, ${x2} ${y2}`;
            const tParam = 0.5 + ((idx % 3) - 1) * 0.06;
            labelX = x1 + (x2 - x1) * tParam;
            labelY = y1 + (y2 - y1) * tParam + bow * 0.72;
          }
        } else {
          const forward = s.y <= t.y;
          const laneShift = hasReverse ? (forward ? -28 : 28) : 0;
          x1 = s.x + 24 + sSlot * (s.w - 48) + laneShift;
          y1 = forward ? s.y + s.h : s.y;
          x2 = t.x + 24 + tSlot * (t.w - 48) + laneShift;
          y2 = forward ? t.y : t.y + t.h;
          const dy = Math.max(42, Math.abs(y2 - y1) * 0.45);
          path = forward
            ? `M ${x1} ${y1} C ${x1} ${y1 + dy}, ${x2} ${y2 - dy}, ${x2} ${y2}`
            : `M ${x1} ${y1} C ${x1} ${y1 - dy}, ${x2} ${y2 + dy}, ${x2} ${y2}`;
          labelX = (x1 + x2) / 2;
          labelY = (y1 + y2) / 2;
        }

        return { ...e, x1, y1, x2, y2, path, labelX, labelY };
      })
      .filter(Boolean);

    const totalW = Math.max(...allContainers.map((c) => c.x + c.w), 800) + 48;
    const totalH = Math.max(...allContainers.map((c) => c.y + c.h), 480) + 48;

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
