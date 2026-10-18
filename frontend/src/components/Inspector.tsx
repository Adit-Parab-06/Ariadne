import React, { useState, useEffect } from 'react';
import { Zap } from 'lucide-react';
import { useAppStore } from '../store';
import { api } from '../api/client';
import { Card, Chip, Tabs, AgentAvatar, Button } from '../ui';
import { TaskItem, NextEdge } from '../api/types';
import { GraphCanvas } from './GraphCanvas';
import { MemoryView } from './MemoryView';
import { ConcurrencyLabModal } from './ConcurrencyLabModal';

export const Inspector: React.FC = () => {
  const {
    tenant,
    activeRunId,
    inspectorTab,
    setInspectorTab,
    evidence,
    activeNodeId,
    setActiveNodeId,
  } = useAppStore();

  const [factsCount, setFactsCount] = useState<number | undefined>(undefined);
  const [tasks, setTasks] = useState<TaskItem[]>([]);
  const [nextEdges, setNextEdges] = useState<NextEdge[]>([]);

  // Concurrency lab modal
  const [isLabOpen, setIsLabOpen] = useState(false);

  // Load memory count for tab badge
  useEffect(() => {
    (async () => {
      try {
        const memData = await api.getMemory(tenant);
        if (memData?.facts) {
          setFactsCount(memData.facts.length);
        }
      } catch (e) {
        // Ignore
      }
    })();
  }, [tenant]);

  // Load task DAG if active run
  useEffect(() => {
    if (!activeRunId) return;
    (async () => {
      try {
        const taskData = await api.getTasks(tenant, activeRunId);
        if (taskData) {
          setTasks(taskData.tasks || []);
          setNextEdges(taskData.next || []);
        }
      } catch (e) {
        console.warn('Failed to load tasks', e);
      }
    })();
  }, [tenant, activeRunId]);

  const selectedNode = evidence.nodes.find((n) => n.id === activeNodeId);

  return (
    <aside className="w-[420px] h-full flex flex-col border-l apple-border bg-bg-2/75 backdrop-blur-md select-none flex-shrink-0 animate-in slide-in-from-right duration-200">
      {/* Tab Switcher */}
      <Tabs
        tabs={[
          { id: 'thread', label: 'Thread', badge: evidence.nodes.length || undefined },
          { id: 'memory', label: 'Memory', badge: factsCount },
          { id: 'coordination', label: 'Coordination', badge: tasks.length || undefined },
        ]}
        activeTab={inspectorTab}
        onChange={(t) => setInspectorTab(t as any)}
      />

      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {/* ================= TAB 1: THREAD ================= */}
        {inspectorTab === 'thread' && (
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <h3 className="text-sm font-bold text-label">Evidence Graph</h3>
              <span className="text-xs font-mono font-semibold text-label-2">
                {evidence.nodes.length} nodes
              </span>
            </div>

            {/* 2D Force-Directed Graph Canvas */}
            <GraphCanvas nodes={evidence.nodes} edges={evidence.edges} height={280} />

            {/* Discovered Graph Entities List */}
            {evidence.nodes.length > 0 && (
              <div className="bg-bg border apple-border rounded-2xl p-3 space-y-2">
                <div className="flex items-center justify-between">
                  <span className="text-[11px] font-bold text-label-2 uppercase tracking-wider">
                    Entities ({evidence.nodes.length})
                  </span>
                  {activeNodeId && (
                    <button
                      type="button"
                      onClick={() => setActiveNodeId(null)}
                      className="text-[10px] text-blue hover:underline font-semibold"
                    >
                      Clear
                    </button>
                  )}
                </div>

                <div className="flex flex-wrap gap-1.5 max-h-36 overflow-y-auto p-0.5">
                  {evidence.nodes.map((node) => (
                    <Chip
                      key={node.id}
                      label={node.name || node.id}
                      type={node.label}
                      active={node.id === activeNodeId}
                      onClick={() => setActiveNodeId(node.id)}
                    />
                  ))}
                </div>

                {evidence.edges.length > 0 && (
                  <div className="pt-2 border-t apple-border">
                    <span className="text-[10px] font-bold text-label-2 uppercase tracking-wider block mb-1">
                      Relationships ({evidence.edges.length})
                    </span>
                    <div className="space-y-1 max-h-28 overflow-y-auto text-[11px] font-mono text-label-2">
                      {evidence.edges.slice(0, 20).map((e, idx) => (
                        <div key={idx} className="flex items-center space-x-1.5 truncate">
                          <span className="text-blue font-bold">{e.src}</span>
                          <span className="text-label-2">-[{e.rel}]-&gt;</span>
                          <span className="text-purple font-bold">{e.dst}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            )}

            {/* Node Detail Card */}
            {selectedNode && (
              <Card className="space-y-2 border-blue/30 bg-blue/5">
                <div className="flex items-center justify-between">
                  <span className="text-[10px] font-bold uppercase tracking-wider text-blue">
                    {selectedNode.label} Details
                  </span>
                  <span className="font-mono text-xs font-semibold text-label">
                    {selectedNode.id}
                  </span>
                </div>
                <h4 className="text-sm font-bold text-label">{selectedNode.name}</h4>
                {selectedNode.kind && (
                  <p className="text-xs text-label-2">Kind: {selectedNode.kind}</p>
                )}
                {selectedNode.tier !== undefined && (
                  <p className="text-xs text-label-2">Tier: {selectedNode.tier}</p>
                )}
                {selectedNode.status && (
                  <p className="text-xs text-label-2">Status: {selectedNode.status}</p>
                )}
              </Card>
            )}
          </div>
        )}

        {/* ================= TAB 2: MEMORY ================= */}
        {inspectorTab === 'memory' && <MemoryView />}

        {/* ================= TAB 3: COORDINATION ================= */}
        {inspectorTab === 'coordination' && (
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <h3 className="text-sm font-bold text-label">Multi-Agent Coordination</h3>
              <Button
                variant="tinted"
                color="blue"
                size="sm"
                onClick={() => setIsLabOpen(true)}
                className="space-x-1"
              >
                <Zap className="w-3.5 h-3.5 text-blue" />
                <span>Lab</span>
              </Button>
            </div>

            {/* Task DAG Columns */}
            <div className="space-y-3">
              {['open', 'claimed', 'done'].map((statusKey) => {
                const groupTasks = tasks.filter((t) => t.status === statusKey);
                return (
                  <div key={statusKey} className="space-y-1.5">
                    <div className="flex items-center justify-between text-xs font-semibold px-1">
                      <span className="uppercase text-label-3">{statusKey}</span>
                      <span className="text-[10px] font-mono font-bold text-label-2">
                        {groupTasks.length}
                      </span>
                    </div>

                    {groupTasks.length === 0 ? (
                      <div className="p-2.5 rounded-xl border border-dashed apple-border text-center text-[11px] text-label-3">
                        No {statusKey} tasks
                      </div>
                    ) : (
                      groupTasks.map((t) => (
                        <div
                          key={t.id}
                          className="p-3 rounded-xl bg-bg border apple-border text-xs space-y-1 shadow-sm"
                        >
                          <div className="flex items-center justify-between">
                            <span className="font-mono font-bold text-blue capitalize">{t.kind}</span>
                            {t.owner && <AgentAvatar role={t.owner} size="sm" />}
                          </div>
                          <span className="text-[10px] font-mono text-label-3">{t.id}</span>
                        </div>
                      ))
                    )}
                  </div>
                );
              })}
            </div>

            {/* Handoff Next Edges */}
            {nextEdges.length > 0 && (
              <div className="pt-2 border-t apple-border space-y-1.5">
                <span className="text-[11px] font-semibold text-label-3 uppercase tracking-wider block">
                  [:NEXT] Handoff Edges ({nextEdges.length})
                </span>
                {nextEdges.map((e, idx) => (
                  <div
                    key={idx}
                    className="p-2 rounded-lg bg-fill/20 border apple-border text-[11px] font-mono text-label-2"
                  >
                    <div>{e.src} ➔ {e.dst}</div>
                    {e.note && <div className="text-[10px] text-label-3 italic mt-0.5">{e.note}</div>}
                  </div>
                ))}
              </div>
            )}
          </div>
        )}
      </div>

      {/* Concurrency Lab Modal Sheet */}
      <ConcurrencyLabModal
        isOpen={isLabOpen}
        onClose={() => setIsLabOpen(false)}
      />
    </aside>
  );
};
