import React, { useRef, useEffect, useState, useMemo, useCallback } from 'react';
import { createPortal } from 'react-dom';
import ForceGraph2D, { ForceGraphMethods } from 'react-force-graph-2d';
import {
  Maximize2,
  RotateCcw,
  ZoomIn,
  ZoomOut,
  X,
  Layers,
  ArrowRight,
  RefreshCw,
  PanelRight,
  Sparkles,
  Check,
} from 'lucide-react';
import { useAppStore } from '../store';
import { EvidenceNode, EvidenceEdge } from '../api/types';
import { Chip } from '../ui';
import { GraphBackdrop, GraphTheme } from './GraphBackdrop';

interface GraphCanvasProps {
  nodes: EvidenceNode[];
  edges: EvidenceEdge[];
  height?: number;
}

const LABEL_COLORS: Record<string, string> = {
  Service: '#0071e3',   // System Blue
  Person: '#ff9500',    // System Orange
  Incident: '#ff3b30',  // System Red
  Customer: '#34c759',  // System Green
  Doc: '#8e8e93',       // System Gray
  Runbook: '#8e8e93',   // System Gray
  Procedure: '#af52de', // System Purple
  Fact: '#bf5af2',      // Light Purple
  Episode: '#5856d6',   // Indigo
  Team: '#30b0c7',      // Teal
  Decision: '#ffd60a',  // Yellow
};

function drawRoundedRect(
  ctx: CanvasRenderingContext2D,
  x: number,
  y: number,
  w: number,
  h: number,
  r: number
) {
  if (typeof (ctx as any).roundRect === 'function') {
    (ctx as any).roundRect(x, y, w, h, r);
  } else {
    ctx.beginPath();
    ctx.moveTo(x + r, y);
    ctx.lineTo(x + w - r, y);
    ctx.quadraticCurveTo(x + w, y, x + w, y + r);
    ctx.lineTo(x + w, y + h - r);
    ctx.quadraticCurveTo(x + w, y + h, x + w - r, y + h);
    ctx.lineTo(x + r, y + h);
    ctx.quadraticCurveTo(x, y + h, x, y + h - r);
    ctx.lineTo(x, y + r);
    ctx.quadraticCurveTo(x, y, x + r, y);
    ctx.closePath();
  }
}

export const GraphCanvas: React.FC<GraphCanvasProps> = ({ nodes, edges, height = 280 }) => {
  const containerRef = useRef<HTMLDivElement>(null);
  const fgRef = useRef<ForceGraphMethods>();
  const expandedFgRef = useRef<ForceGraphMethods>();
  const modalCanvasRef = useRef<HTMLDivElement>(null);

  const [dimensions, setDimensions] = useState({ width: 380, height });
  const [modalDimensions, setModalDimensions] = useState({ width: 900, height: 600 });
  const [hoveredNode, setHoveredNode] = useState<string | null>(null);
  const [activeFilter, setActiveFilter] = useState<'all' | 'Service' | 'Incident' | 'Person' | 'Memory'>('all');
  const [isExpanded, setIsExpanded] = useState(false);
  const [showStudioDrawer, setShowStudioDrawer] = useState(true);
  const [graphTheme, setGraphTheme] = useState<GraphTheme>(() => {
    try {
      return (localStorage.getItem('ariadne_graph_theme') as GraphTheme) || 'celestial';
    } catch {
      return 'celestial';
    }
  });
  const [showCompactThemeMenu, setShowCompactThemeMenu] = useState(false);
  const [showStudioThemeMenu, setShowStudioThemeMenu] = useState(false);

  const changeTheme = (t: GraphTheme) => {
    setGraphTheme(t);
    try {
      localStorage.setItem('ariadne_graph_theme', t);
    } catch {}
  };

  const { activeNodeId, setActiveNodeId, tenant } = useAppStore();

  // Resize observer to fill compact container width
  useEffect(() => {
    if (!containerRef.current) return;
    const observer = new ResizeObserver((entries) => {
      for (const entry of entries) {
        if (entry.contentRect.width > 0) {
          setDimensions({
            width: Math.floor(entry.contentRect.width),
            height,
          });
        }
      }
    });
    observer.observe(containerRef.current);
    return () => observer.disconnect();
  }, [height]);

  // Recalculate modal canvas size on expand or window resize
  useEffect(() => {
    if (!isExpanded) return;
    const measure = () => {
      if (modalCanvasRef.current) {
        const { clientWidth, clientHeight } = modalCanvasRef.current;
        if (clientWidth > 0 && clientHeight > 0) {
          setModalDimensions({
            width: Math.floor(clientWidth),
            height: Math.floor(clientHeight),
          });
        }
      }
    };

    measure();
    const t1 = setTimeout(measure, 60);
    const t2 = setTimeout(measure, 250);
    window.addEventListener('resize', measure);
    return () => {
      clearTimeout(t1);
      clearTimeout(t2);
      window.removeEventListener('resize', measure);
    };
  }, [isExpanded, showStudioDrawer, activeFilter]);

  // Close modal on Escape
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && isExpanded) {
        setIsExpanded(false);
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isExpanded]);

  // Filtered nodes
  const filteredNodes = useMemo(() => {
    if (activeFilter === 'all') return nodes;
    if (activeFilter === 'Service') return nodes.filter((n) => n.label === 'Service');
    if (activeFilter === 'Incident') return nodes.filter((n) => n.label === 'Incident');
    if (activeFilter === 'Person') return nodes.filter((n) => n.label === 'Person' || n.label === 'Team');
    if (activeFilter === 'Memory') {
      return nodes.filter((n) =>
        ['Doc', 'Runbook', 'Procedure', 'Fact', 'Episode', 'Decision'].includes(n.label)
      );
    }
    return nodes;
  }, [nodes, activeFilter]);

  // Construct valid graph data
  const graphData = useMemo(() => {
    const nodeMap = new Map<string, any>();
    filteredNodes.forEach((n) => {
      nodeMap.set(n.id, {
        id: n.id,
        name: n.name || n.id,
        label: n.label || 'Entity',
        tier: n.tier,
        kind: n.kind,
        status: n.status,
      });
    });

    // Only include links whose endpoints both exist in the active filter set
    const links = edges
      .filter((e) => nodeMap.has(e.src) && nodeMap.has(e.dst))
      .map((e) => ({
        source: e.src,
        target: e.dst,
        rel: e.rel,
      }));

    return {
      nodes: Array.from(nodeMap.values()),
      links,
    };
  }, [filteredNodes, edges]);

  // Apply D3 physics force tuning for uncluttered layout
  useEffect(() => {
    const configureForces = (ref: React.MutableRefObject<ForceGraphMethods | undefined>) => {
      if (!ref.current) return;
      try {
        const charge = (ref.current as any).d3Force?.('charge');
        if (charge) {
          charge.strength(-340);
          charge.distanceMax(550);
        }
        const link = (ref.current as any).d3Force?.('link');
        if (link) {
          link.distance(85);
        }
        (ref.current as any).d3ReheatSimulation?.();
      } catch (e) {
        // Ignore force configuration errors on teardown
      }
    };

    if (!isExpanded) {
      configureForces(fgRef);
    } else {
      setTimeout(() => configureForces(expandedFgRef), 100);
    }
  }, [graphData, isExpanded]);

  // Auto-center camera when activeNodeId changes
  useEffect(() => {
    if (!activeNodeId) return;
    const focusRef = (ref: React.MutableRefObject<ForceGraphMethods | undefined>) => {
      if (!ref.current) return;
      const targetNode = graphData.nodes.find((n: any) => n.id === activeNodeId);
      if (targetNode && typeof targetNode.x === 'number' && typeof targetNode.y === 'number') {
        ref.current.centerAt(targetNode.x, targetNode.y, 400);
        ref.current.zoom(2.2, 400);
      }
    };
    if (isExpanded) {
      focusRef(expandedFgRef);
    } else {
      focusRef(fgRef);
    }
  }, [activeNodeId, graphData.nodes, isExpanded]);

  // Auto-fit on first load or when dataset changes
  useEffect(() => {
    if (graphData.nodes.length > 0) {
      const timer = setTimeout(() => {
        if (isExpanded) {
          expandedFgRef.current?.zoomToFit(500, 40);
        } else {
          fgRef.current?.zoomToFit(500, 36);
        }
      }, 300);
      return () => clearTimeout(timer);
    }
  }, [graphData.nodes.length, isExpanded]);

  const handleZoomToFit = (ref = fgRef) => {
    ref.current?.zoomToFit(400, 36);
  };

  const handleReset = (ref = fgRef) => {
    ref.current?.centerAt(0, 0, 400);
    ref.current?.zoom(1.2, 400);
  };

  const handleZoomIn = (ref = fgRef) => {
    ref.current?.zoom(1.4, 300);
  };

  const handleZoomOut = (ref = fgRef) => {
    ref.current?.zoom(0.7, 300);
  };

  const handleReheat = (ref = fgRef) => {
    (ref.current as any)?.d3ReheatSimulation?.();
  };

  const handleOpenStudio = () => {
    setIsExpanded(true);
    setTimeout(() => {
      expandedFgRef.current?.zoomToFit(500, 40);
    }, 200);
  };

  // Node paint callback with scale-aware label rendering & Apple-style pill badges
  const drawNode = useCallback(
    (node: any, ctx: CanvasRenderingContext2D, globalScale: number) => {
      const isSelected = node.id === activeNodeId;
      const isHovered = node.id === hoveredNode;
      const baseColor = LABEL_COLORS[node.label] || '#0071e3';
      const isFocal = node.label === 'Service' || node.label === 'Incident';
      const r = isSelected ? 8.5 : isFocal ? 7 : 5.5;

      // Outer selection / hover aura
      if (isSelected || isHovered) {
        ctx.beginPath();
        ctx.arc(node.x, node.y, r + 6, 0, 2 * Math.PI, false);
        ctx.fillStyle = isSelected ? 'rgba(0, 113, 227, 0.28)' : 'rgba(142, 142, 147, 0.24)';
        ctx.fill();
        ctx.lineWidth = 1.5;
        ctx.strokeStyle = isSelected ? '#0071e3' : 'rgba(142, 142, 147, 0.7)';
        ctx.stroke();
      }

      // Core node circle
      ctx.beginPath();
      ctx.arc(node.x, node.y, r, 0, 2 * Math.PI, false);
      ctx.fillStyle = baseColor;
      ctx.fill();
      ctx.lineWidth = 1.5;
      ctx.strokeStyle = '#ffffff';
      ctx.stroke();

      // Adaptive text label with anti-clutter pill background
      const rawName = node.name || node.id || 'Entity';
      const cleanName = rawName.replace(/^(svc_|cus_|doc_|per_|inc_|prc_|epi_|fct_)/i, '');
      const showFull = isSelected || isHovered;
      const maxChars = showFull ? 30 : 16;
      const displayText = cleanName.length > maxChars ? `${cleanName.slice(0, maxChars - 1)}…` : cleanName;

      // Only draw label for selected, hovered, focal entities, small graphs, or zoomed-in view
      const shouldDrawLabel =
        isSelected ||
        isHovered ||
        isFocal ||
        graphData.nodes.length <= 12 ||
        globalScale >= 1.35;

      if (shouldDrawLabel) {
        const fontSize = Math.max(9.5 / Math.pow(globalScale, 0.25), 8);
        ctx.font = `${isSelected ? '600 ' : '500 '}${fontSize}px -apple-system, BlinkMacSystemFont, "SF Pro Text", sans-serif`;
        const textMetrics = ctx.measureText(displayText);
        const padX = 6;
        const padY = 2.5;
        const pillW = textMetrics.width + padX * 2;
        const pillH = fontSize + padY * 2;
        const pillX = node.x - pillW / 2;
        const pillY = node.y + r + 3;

        // Background pill
        ctx.beginPath();
        drawRoundedRect(ctx, pillX, pillY, pillW, pillH, 4);

        if (isSelected) {
          ctx.fillStyle = '#0071e3';
        } else if (isHovered) {
          ctx.fillStyle = '#ffffff';
        } else if (graphTheme === 'classic') {
          ctx.fillStyle = 'rgba(28, 28, 30, 0.9)';
        } else {
          ctx.fillStyle = 'rgba(8, 14, 26, 0.88)';
        }
        ctx.fill();

        ctx.lineWidth = 0.75;
        ctx.strokeStyle = isSelected
          ? '#0051a8'
          : isHovered
          ? 'rgba(0, 0, 0, 0.25)'
          : 'rgba(255, 255, 255, 0.22)';
        ctx.stroke();

        // Label text
        ctx.fillStyle = isHovered ? '#000000' : '#ffffff';
        ctx.textAlign = 'center';
        ctx.textBaseline = 'middle';
        ctx.fillText(displayText, node.x, pillY + pillH / 2);
      }
    },
    [activeNodeId, hoveredNode, graphData.nodes.length, graphTheme]
  );

  // Generous 22px hit-target for effortless clicking on canvas
  const drawPointerArea = useCallback(
    (node: any, color: string, ctx: CanvasRenderingContext2D) => {
      ctx.beginPath();
      ctx.arc(node.x, node.y, 22, 0, 2 * Math.PI, false);
      ctx.fillStyle = color;
      ctx.fill();
    },
    []
  );

  // Selected node inspector details
  const selectedNodeObj = useMemo(() => {
    if (!activeNodeId) return null;
    return nodes.find((n) => n.id === activeNodeId) || null;
  }, [activeNodeId, nodes]);

  // Connected edges for the selected node
  const connectedInfo = useMemo(() => {
    if (!activeNodeId) return { inbound: [], outbound: [] };
    const inbound = edges
      .filter((e) => e.dst === activeNodeId)
      .map((e) => {
        const srcNode = nodes.find((n) => n.id === e.src);
        return { ...e, targetNodeName: srcNode?.name || e.src, targetLabel: srcNode?.label || 'Entity' };
      });
    const outbound = edges
      .filter((e) => e.src === activeNodeId)
      .map((e) => {
        const dstNode = nodes.find((n) => n.id === e.dst);
        return { ...e, targetNodeName: dstNode?.name || e.dst, targetLabel: dstNode?.label || 'Entity' };
      });
    return { inbound, outbound };
  }, [activeNodeId, edges, nodes]);

  return (
    <>
      {/* ================= COMPACT CANVAS (hidden when expanded to prevent double-canvas collision) ================= */}
      <div
        ref={containerRef}
        className="relative w-full rounded-2xl border apple-border overflow-hidden shadow-xs"
        style={{ height }}
      >
        {/* Dynamic Illustrious Backdrop */}
        <GraphBackdrop theme={graphTheme} isExpanded={false} />

        {graphData.nodes.length === 0 ? (
          <div className="flex h-full flex-col items-center justify-center text-xs text-label-2 italic px-6 text-center space-y-1 relative z-10">
            <span>No entities</span>
            <button
              type="button"
              onClick={() => setActiveFilter('all')}
              className="text-blue underline not-italic hover:opacity-80 mt-1 font-semibold"
            >
              Reset filter
            </button>
          </div>
        ) : !isExpanded ? (
          <>
            <ForceGraph2D
              ref={fgRef as any}
              width={dimensions.width}
              height={dimensions.height}
              graphData={graphData}
              nodeCanvasObject={drawNode}
              nodePointerAreaPaint={drawPointerArea}
              enableNodeDrag={true}
              onNodeClick={(node: any) => {
                setActiveNodeId(node.id);
              }}
              onNodeHover={(node: any) => {
                setHoveredNode(node ? node.id : null);
              }}
              linkColor={(link: any) => {
                const srcId = typeof link.source === 'object' ? link.source.id : link.source;
                const dstId = typeof link.target === 'object' ? link.target.id : link.target;
                if (activeNodeId && (srcId === activeNodeId || dstId === activeNodeId)) {
                  return '#0071e3';
                }
                return 'rgba(142, 142, 147, 0.4)';
              }}
              linkWidth={(link: any) => {
                const srcId = typeof link.source === 'object' ? link.source.id : link.source;
                const dstId = typeof link.target === 'object' ? link.target.id : link.target;
                if (activeNodeId && (srcId === activeNodeId || dstId === activeNodeId)) return 2.2;
                return 1;
              }}
              linkDirectionalArrowLength={3.5}
              linkDirectionalArrowRelPos={0.85}
              linkDirectionalArrowColor={(link: any) => {
                const srcId = typeof link.source === 'object' ? link.source.id : link.source;
                const dstId = typeof link.target === 'object' ? link.target.id : link.target;
                if (activeNodeId && (srcId === activeNodeId || dstId === activeNodeId)) {
                  return '#0071e3';
                }
                return 'rgba(142, 142, 147, 0.7)';
              }}
              linkCurvature={0.08}
              warmupTicks={30}
              cooldownTicks={100}
              d3AlphaDecay={0.025}
              d3VelocityDecay={0.35}
              backgroundColor="transparent"
            />

            {/* Quick Filter Pill Group (Top Left) */}
            <div className="absolute top-2 left-2 z-10 flex items-center space-x-1 bg-bg-2/90 backdrop-blur-md border apple-border rounded-lg p-0.5 shadow-xs text-[10px]">
              {(['all', 'Service', 'Incident', 'Person', 'Memory'] as const).map((filterKey) => (
                <button
                  key={filterKey}
                  type="button"
                  onClick={() => setActiveFilter(filterKey)}
                  className={`px-2 py-0.5 rounded font-semibold transition-colors ${
                    activeFilter === filterKey
                      ? 'bg-blue text-white'
                      : 'text-label-2 hover:text-label hover:bg-fill/30'
                  }`}
                >
                  {filterKey === 'all' ? 'All' : filterKey}
                </button>
              ))}
            </div>

            {/* Compact Floating Toolbar (Top Right) */}
            <div className="absolute top-2 right-2 z-10 flex items-center space-x-1 bg-bg-2/90 backdrop-blur-md border apple-border rounded-lg p-1 shadow-xs">
              <button
                type="button"
                onClick={() => setShowCompactThemeMenu(!showCompactThemeMenu)}
                title="Graph Backdrop Theme"
                className={`p-1 rounded transition-colors ${
                  showCompactThemeMenu
                    ? 'bg-blue text-white'
                    : 'text-label-2 hover:text-label hover:bg-fill/40'
                }`}
              >
                <Sparkles className="w-3.5 h-3.5" />
              </button>
              <button
                type="button"
                onClick={handleOpenStudio}
                title="Expand Graph Studio"
                className="p-1 rounded hover:bg-fill/40 text-blue hover:text-blue transition-colors font-semibold flex items-center"
              >
                <Maximize2 className="w-3.5 h-3.5" />
              </button>
              <button
                type="button"
                onClick={() => handleReset(fgRef)}
                title="Reset View"
                className="p-1 rounded hover:bg-fill/40 text-label-2 hover:text-label transition-colors"
              >
                <RotateCcw className="w-3.5 h-3.5" />
              </button>
            </div>

            {/* Compact Theme Dropdown Popover */}
            {showCompactThemeMenu && (
              <div className="absolute top-11 right-2 z-30 bg-bg-2/95 backdrop-blur-xl border apple-border rounded-2xl p-1.5 shadow-2xl w-48 text-xs animate-in fade-in zoom-in-95 duration-150">
                <div className="flex items-center justify-between px-2 py-1 text-[10px] font-bold uppercase tracking-wider text-label-2 border-b apple-border mb-1">
                  <span>Graph Backdrop</span>
                  <button
                    type="button"
                    onClick={() => setShowCompactThemeMenu(false)}
                    className="p-0.5 rounded text-label-2 hover:text-label"
                  >
                    <X className="w-3 h-3" />
                  </button>
                </div>
                {[
                  { id: 'celestial', label: 'Celestial Nebula', desc: 'Cosmic glow & star chart' },
                  { id: 'radar', label: 'Digital Radar', desc: 'Tactical telemetry & grid' },
                  { id: 'obsidian', label: 'Obsidian Stars', desc: 'Clean starlight dots' },
                  { id: 'classic', label: 'Default Classic', desc: 'Original flat background' },
                ].map((item) => (
                  <button
                    key={item.id}
                    type="button"
                    onClick={() => {
                      changeTheme(item.id as GraphTheme);
                      setShowCompactThemeMenu(false);
                    }}
                    className={`w-full flex items-center justify-between px-2 py-1.5 rounded-xl transition-colors text-left my-0.5 ${
                      graphTheme === item.id
                        ? 'bg-blue text-white font-semibold'
                        : 'text-label hover:bg-fill/40'
                    }`}
                  >
                    <div>
                      <div className="text-[11px] font-medium">{item.label}</div>
                      <div className={`text-[9px] ${graphTheme === item.id ? 'text-white/80' : 'text-label-2'}`}>
                        {item.desc}
                      </div>
                    </div>
                    {graphTheme === item.id && <Check className="w-3.5 h-3.5 flex-shrink-0 ml-1" />}
                  </button>
                ))}
              </div>
            )}

            {/* Mini Legend Pill (Bottom Left) */}
            <div className="absolute bottom-2 left-2 flex items-center space-x-2 bg-bg-2/90 backdrop-blur-md border apple-border rounded-full px-2.5 py-1 text-[9px] text-label-2 font-semibold shadow-xs">
              <span className="flex items-center space-x-1">
                <span className="w-2 h-2 rounded-full bg-blue" />
                <span>Service</span>
              </span>
              <span className="flex items-center space-x-1">
                <span className="w-2 h-2 rounded-full bg-red" />
                <span>Incident</span>
              </span>
              <span className="flex items-center space-x-1">
                <span className="w-2 h-2 rounded-full bg-orange" />
                <span>Person</span>
              </span>
              <span className="flex items-center space-x-1">
                <span className="w-2 h-2 rounded-full bg-green" />
                <span>Customer</span>
              </span>
            </div>
          </>
        ) : (
          <div className="flex h-full items-center justify-center text-xs text-label-2 font-medium">
            Graph open in Studio
          </div>
        )}
      </div>

      {/* ================= EXPANDED GRAPH STUDIO MODAL (PORTALED TO DOCUMENT.BODY) ================= */}
      {isExpanded && typeof document !== 'undefined' && createPortal(
        <div className="fixed inset-0 z-[9999] flex items-center justify-center p-4 sm:p-6 md:p-8 bg-black/75 backdrop-blur-md animate-in fade-in duration-150">
          <div className="relative w-full max-w-7xl h-[90vh] bg-bg-2 border apple-border rounded-3xl shadow-2xl flex flex-col overflow-hidden animate-in zoom-in-95 duration-150">
            {/* Modal Header */}
            <div className="flex items-center justify-between px-5 py-3 border-b apple-border bg-bg/90 backdrop-blur-md flex-shrink-0">
              <div className="flex items-center space-x-3">
                <div className="w-8 h-8 rounded-xl bg-blue/15 text-blue flex items-center justify-center">
                  <Layers className="w-4.5 h-4.5" />
                </div>
                <div className="flex items-center space-x-2">
                  <h2 className="text-base font-bold text-label">Evidence Graph Studio</h2>
                  <span className="text-[10px] uppercase font-mono px-2 py-0.5 rounded-full bg-blue/15 text-blue font-bold">
                    {tenant}
                  </span>
                  <span className="text-xs font-mono text-label-2 font-bold">
                    ({graphData.nodes.length} nodes)
                  </span>
                </div>
              </div>

              {/* Center Filter Tabs */}
              <div className="hidden sm:flex items-center space-x-1 bg-fill/40 p-1 rounded-xl border apple-border">
                {(['all', 'Service', 'Incident', 'Person', 'Memory'] as const).map((filterKey) => (
                  <button
                    key={filterKey}
                    type="button"
                    onClick={() => setActiveFilter(filterKey)}
                    className={`px-3 py-1 rounded-lg text-xs font-semibold transition-all ${
                      activeFilter === filterKey
                        ? 'bg-bg text-blue font-bold shadow-xs'
                        : 'text-label-2 hover:text-label hover:bg-fill/30'
                    }`}
                  >
                    {filterKey === 'all' ? 'All' : filterKey}
                  </button>
                ))}
              </div>

              {/* Right Controls */}
              <div className="flex items-center space-x-2">
                <div className="flex items-center space-x-1 bg-fill/30 p-1 rounded-xl border apple-border">
                  <button
                    type="button"
                    onClick={() => handleZoomIn(expandedFgRef)}
                    title="Zoom In"
                    className="p-1.5 rounded-lg text-label-2 hover:text-label hover:bg-fill/40 transition-colors"
                  >
                    <ZoomIn className="w-4 h-4" />
                  </button>
                  <button
                    type="button"
                    onClick={() => handleZoomOut(expandedFgRef)}
                    title="Zoom Out"
                    className="p-1.5 rounded-lg text-label-2 hover:text-label hover:bg-fill/40 transition-colors"
                  >
                    <ZoomOut className="w-4 h-4" />
                  </button>
                  <button
                    type="button"
                    onClick={() => handleZoomToFit(expandedFgRef)}
                    title="Fit View"
                    className="p-1.5 rounded-lg text-label-2 hover:text-label hover:bg-fill/40 transition-colors"
                  >
                    <Maximize2 className="w-4 h-4" />
                  </button>
                  <button
                    type="button"
                    onClick={() => handleReheat(expandedFgRef)}
                    title="Re-relax layout"
                    className="p-1.5 rounded-lg text-label-2 hover:text-label hover:bg-fill/40 transition-colors"
                  >
                    <RefreshCw className="w-4 h-4" />
                  </button>
                  <button
                    type="button"
                    onClick={() => handleReset(expandedFgRef)}
                    title="Reset Position"
                    className="p-1.5 rounded-lg text-label-2 hover:text-label hover:bg-fill/40 transition-colors"
                  >
                    <RotateCcw className="w-4 h-4" />
                  </button>
                  <button
                    type="button"
                    onClick={() => setShowStudioDrawer(!showStudioDrawer)}
                    title="Toggle Inspector Drawer"
                    className={`p-1.5 rounded-lg transition-colors ${
                      showStudioDrawer
                        ? 'bg-bg text-blue font-bold shadow-xs'
                        : 'text-label-2 hover:text-label hover:bg-fill/40'
                    }`}
                  >
                    <PanelRight className="w-4 h-4" />
                  </button>
                  <button
                    type="button"
                    onClick={() => setShowStudioThemeMenu(!showStudioThemeMenu)}
                    title="Graph Backdrop Theme"
                    className={`p-1.5 rounded-lg transition-colors flex items-center space-x-1.5 ${
                      showStudioThemeMenu
                        ? 'bg-blue text-white font-semibold shadow-xs'
                        : 'text-label-2 hover:text-label hover:bg-fill/40'
                    }`}
                  >
                    <Sparkles className="w-4 h-4" />
                    <span className="text-xs font-semibold capitalize hidden md:inline">
                      {graphTheme === 'celestial' ? 'Celestial' : graphTheme === 'radar' ? 'Radar' : graphTheme === 'obsidian' ? 'Obsidian' : 'Classic'}
                    </span>
                  </button>
                </div>

                <button
                  type="button"
                  onClick={() => setIsExpanded(false)}
                  title="Close Studio (Esc)"
                  className="p-2 rounded-xl bg-fill/40 hover:bg-fill text-label-2 hover:text-label transition-colors"
                >
                  <X className="w-5 h-5" />
                </button>
              </div>
            </div>

            {/* Studio Theme Dropdown Popover */}
            {showStudioThemeMenu && (
              <div className="absolute top-14 right-20 z-50 bg-bg-2/95 backdrop-blur-xl border apple-border rounded-2xl p-1.5 shadow-2xl w-52 text-xs animate-in fade-in zoom-in-95 duration-150">
                <div className="flex items-center justify-between px-2.5 py-1 text-[10px] font-bold uppercase tracking-wider text-label-2 border-b apple-border mb-1">
                  <span>Graph Backdrop</span>
                  <button
                    type="button"
                    onClick={() => setShowStudioThemeMenu(false)}
                    className="p-0.5 rounded text-label-2 hover:text-label"
                  >
                    <X className="w-3 h-3" />
                  </button>
                </div>
                {[
                  { id: 'celestial', label: 'Celestial Nebula', desc: 'Cosmic glow & star chart' },
                  { id: 'radar', label: 'Digital Radar', desc: 'Tactical telemetry & grid' },
                  { id: 'obsidian', label: 'Obsidian Stars', desc: 'Clean starlight dots' },
                  { id: 'classic', label: 'Default Classic', desc: 'Original flat background' },
                ].map((item) => (
                  <button
                    key={item.id}
                    type="button"
                    onClick={() => {
                      changeTheme(item.id as GraphTheme);
                      setShowStudioThemeMenu(false);
                    }}
                    className={`w-full flex items-center justify-between px-2.5 py-1.5 rounded-xl transition-colors text-left my-0.5 ${
                      graphTheme === item.id
                        ? 'bg-blue text-white font-semibold'
                        : 'text-label hover:bg-fill/40'
                    }`}
                  >
                    <div>
                      <div className="text-xs font-medium">{item.label}</div>
                      <div className={`text-[10px] ${graphTheme === item.id ? 'text-white/80' : 'text-label-2'}`}>
                        {item.desc}
                      </div>
                    </div>
                    {graphTheme === item.id && <Check className="w-3.5 h-3.5 flex-shrink-0 ml-1.5" />}
                  </button>
                ))}
              </div>
            )}

            {/* Quick-Select Entity Strip for 1-Click Access */}
            <div className="flex items-center space-x-1.5 overflow-x-auto px-4 py-2 bg-bg border-b apple-border flex-shrink-0">
              <span className="text-[10px] font-bold uppercase text-label-2 mr-1 flex-shrink-0">
                Quick Select:
              </span>
              {graphData.nodes.map((n: any) => (
                <Chip
                  key={n.id}
                  label={n.name || n.id}
                  type={n.label}
                  active={n.id === activeNodeId}
                  onClick={() => {
                    setActiveNodeId(n.id);
                    setShowStudioDrawer(true);
                    const target = graphData.nodes.find((item: any) => item.id === n.id);
                    if (target && typeof target.x === 'number') {
                      expandedFgRef.current?.centerAt(target.x, target.y, 400);
                    }
                  }}
                  className="cursor-pointer flex-shrink-0 text-xs"
                />
              ))}
            </div>

            {/* Modal Body: Graph Canvas + Optional Inspector Sidebar */}
            <div className="flex-1 flex overflow-hidden relative">
              {/* Canvas viewport */}
              <div ref={modalCanvasRef} className="flex-1 h-full relative overflow-hidden cursor-grab active:cursor-grabbing">
                <GraphBackdrop theme={graphTheme} isExpanded={true} />
                <ForceGraph2D
                  ref={expandedFgRef as any}
                  width={modalDimensions.width}
                  height={modalDimensions.height}
                  graphData={graphData}
                  nodeCanvasObject={drawNode}
                  nodePointerAreaPaint={drawPointerArea}
                  enableNodeDrag={true}
                  onNodeClick={(node: any) => {
                    setActiveNodeId(node.id);
                    setShowStudioDrawer(true);
                    expandedFgRef.current?.centerAt(node.x, node.y, 400);
                  }}
                  onNodeHover={(node: any) => {
                    setHoveredNode(node ? node.id : null);
                  }}
                  linkColor={(link: any) => {
                    const srcId = typeof link.source === 'object' ? link.source.id : link.source;
                    const dstId = typeof link.target === 'object' ? link.target.id : link.target;
                    if (activeNodeId && (srcId === activeNodeId || dstId === activeNodeId)) {
                      return '#0071e3';
                    }
                    return 'rgba(142, 142, 147, 0.4)';
                  }}
                  linkWidth={(link: any) => {
                    const srcId = typeof link.source === 'object' ? link.source.id : link.source;
                    const dstId = typeof link.target === 'object' ? link.target.id : link.target;
                    if (activeNodeId && (srcId === activeNodeId || dstId === activeNodeId)) return 2.5;
                    return 1.2;
                  }}
                  linkDirectionalArrowLength={4}
                  linkDirectionalArrowRelPos={0.85}
                  linkDirectionalArrowColor={(link: any) => {
                    const srcId = typeof link.source === 'object' ? link.source.id : link.source;
                    const dstId = typeof link.target === 'object' ? link.target.id : link.target;
                    if (activeNodeId && (srcId === activeNodeId || dstId === activeNodeId)) {
                      return '#0071e3';
                    }
                    return 'rgba(142, 142, 147, 0.7)';
                  }}
                  linkCurvature={0.08}
                  warmupTicks={40}
                  cooldownTicks={120}
                  d3AlphaDecay={0.02}
                  d3VelocityDecay={0.3}
                  backgroundColor="transparent"
                />
              </div>

              {/* Right Side Inspector Drawer (340px) */}
              {showStudioDrawer && selectedNodeObj && (
                <div className="w-[340px] h-full border-l apple-border bg-bg-2/95 backdrop-blur-md p-4 flex flex-col overflow-y-auto space-y-4 animate-in slide-in-from-right duration-150 flex-shrink-0">
                  <div className="flex items-center justify-between">
                    <h3 className="text-xs font-bold uppercase tracking-wider text-label-2">
                      Entity Details
                    </h3>
                    <div className="flex items-center space-x-2">
                      <button
                        type="button"
                        onClick={() => setActiveNodeId(null)}
                        className="text-[11px] text-blue hover:underline font-semibold"
                      >
                        Deselect
                      </button>
                      <button
                        type="button"
                        onClick={() => setShowStudioDrawer(false)}
                        title="Close Inspector"
                        className="p-1 rounded text-label-2 hover:text-label hover:bg-fill/40"
                      >
                        <X className="w-4 h-4" />
                      </button>
                    </div>
                  </div>

                  {/* Entity Card */}
                  <div className="bg-bg border apple-border rounded-2xl p-3.5 space-y-2 shadow-xs">
                    <div className="flex items-start justify-between">
                      <Chip
                        label={selectedNodeObj.label || 'Entity'}
                        type={selectedNodeObj.label?.toLowerCase()}
                      />
                      <span className="text-[11px] font-mono text-label-2 font-bold">
                        {selectedNodeObj.id}
                      </span>
                    </div>
                    <div className="text-sm font-bold text-label">
                      {selectedNodeObj.name || selectedNodeObj.id}
                    </div>
                    {selectedNodeObj.tier && (
                      <div className="text-xs text-label-2">
                        Tier: <span className="font-mono font-bold text-label">{selectedNodeObj.tier}</span>
                      </div>
                    )}
                  </div>

                  {/* Relationships: Inbound */}
                  <div className="space-y-2">
                    <div className="text-[11px] font-bold text-label">
                      Inbound ({connectedInfo.inbound.length})
                    </div>
                    {connectedInfo.inbound.length === 0 ? (
                      <div className="text-xs text-label-2 italic">No inbound links</div>
                    ) : (
                      <div className="space-y-1.5 max-h-40 overflow-y-auto">
                        {connectedInfo.inbound.map((edge, idx) => (
                          <button
                            key={idx}
                            type="button"
                            onClick={() => {
                              setActiveNodeId(edge.src);
                              const target = graphData.nodes.find((item: any) => item.id === edge.src);
                              if (target && typeof target.x === 'number') {
                                expandedFgRef.current?.centerAt(target.x, target.y, 400);
                              }
                            }}
                            className="w-full text-left p-2 rounded-xl bg-bg border apple-border hover:bg-fill/30 transition-colors flex items-center justify-between text-xs group"
                          >
                            <div className="truncate pr-2">
                              <span className="font-mono text-[10px] text-blue font-bold mr-1">
                                {edge.rel}
                              </span>
                              <span className="text-label font-medium">{edge.targetNodeName}</span>
                            </div>
                            <ArrowRight className="w-3.5 h-3.5 text-label-2 group-hover:text-blue flex-shrink-0" />
                          </button>
                        ))}
                      </div>
                    )}
                  </div>

                  {/* Relationships: Outbound */}
                  <div className="space-y-2">
                    <div className="text-[11px] font-bold text-label">
                      Outbound ({connectedInfo.outbound.length})
                    </div>
                    {connectedInfo.outbound.length === 0 ? (
                      <div className="text-xs text-label-2 italic">No outbound links</div>
                    ) : (
                      <div className="space-y-1.5 max-h-40 overflow-y-auto">
                        {connectedInfo.outbound.map((edge, idx) => (
                          <button
                            key={idx}
                            type="button"
                            onClick={() => {
                              setActiveNodeId(edge.dst);
                              const target = graphData.nodes.find((item: any) => item.id === edge.dst);
                              if (target && typeof target.x === 'number') {
                                expandedFgRef.current?.centerAt(target.x, target.y, 400);
                              }
                            }}
                            className="w-full text-left p-2 rounded-xl bg-bg border apple-border hover:bg-fill/30 transition-colors flex items-center justify-between text-xs group"
                          >
                            <div className="truncate pr-2">
                              <span className="font-mono text-[10px] text-purple font-bold mr-1">
                                {edge.rel}
                              </span>
                              <span className="text-label font-medium">{edge.targetNodeName}</span>
                            </div>
                            <ArrowRight className="w-3.5 h-3.5 text-label-2 group-hover:text-blue flex-shrink-0" />
                          </button>
                        ))}
                      </div>
                    )}
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>,
        document.body
      )}
    </>
  );
};
