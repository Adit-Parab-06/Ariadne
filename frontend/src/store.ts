import { create } from 'zustand';
import {
  ActionItem,
  AppEvent,
  Evidence,
  EvidenceEdge,
  EvidenceNode,
  MissionMode,
  RunMetrics,
  RunSummary,
  TenantId,
  ToolCallItem,
} from './api/types';
import { setMockMode, isMock } from './api/client';

export interface AgentLaneState {
  status: string;
  isWorking: boolean;
  tools: ToolCallItem[];
  findings: string;
}

export interface AppStore {
  tenant: TenantId;
  runs: RunSummary[];
  activeRunId: string | null;
  runStatus: 'idle' | 'running' | 'completed' | 'failed' | 'resolved';
  missionText: string;
  missionMode: MissionMode;
  appliedSeqs: number[];

  // Agent Lanes
  lanes: {
    scout: AgentLaneState;
    archivist: AgentLaneState;
    responder: AgentLaneState;
  };

  // Run artifacts
  recalledCount: number;
  recalledItems: any;
  evidence: Evidence;
  handoffs: Array<{ from: string; to: string; note: string }>;
  proposedActions: ActionItem[];
  answer: string;
  citations: string[];
  ungrounded: string[];
  metrics: RunMetrics | null;
  error: string | null;

  // UI state
  inspectorTab: 'thread' | 'memory' | 'coordination';
  activeNodeId: string | null;
  isApprovalSheetOpen: boolean;
  isResolveSheetOpen: boolean;
  isMockMode: boolean;
  memoryVersion: number;
  isSidebarOpen: boolean;
  isInspectorOpen: boolean;

  // Actions
  setTenant: (tenant: TenantId) => void;
  setSidebarOpen: (open: boolean) => void;
  toggleSidebar: () => void;
  setInspectorOpen: (open: boolean) => void;
  toggleInspector: () => void;
  setInspectorTab: (tab: 'thread' | 'memory' | 'coordination') => void;
  setActiveNodeId: (nodeId: string | null) => void;
  setApprovalSheetOpen: (open: boolean) => void;
  setResolveSheetOpen: (open: boolean) => void;
  setIsMockMode: (isMock: boolean) => void;
  incrementMemoryVersion: () => void;
  setRuns: (runs: RunSummary[]) => void;
  initMissionRun: (runId: string, text: string, mode: MissionMode) => void;
  applyEvent: (event: AppEvent) => void;
  resetRunState: () => void;
}

const initialLanes = {
  scout: { status: 'Idle', isWorking: false, tools: [], findings: '' },
  archivist: { status: 'Idle', isWorking: false, tools: [], findings: '' },
  responder: { status: 'Idle', isWorking: false, tools: [], findings: '' },
};

export const useAppStore = create<AppStore>((set) => ({
  tenant: 'northwind',
  runs: [],
  activeRunId: null,
  runStatus: 'idle',
  missionText: '',
  missionMode: 'respond',
  appliedSeqs: [],

  lanes: initialLanes,
  recalledCount: 0,
  recalledItems: null,
  evidence: { nodes: [], edges: [] },
  handoffs: [],
  proposedActions: [],
  answer: '',
  citations: [],
  ungrounded: [],
  metrics: null,
  error: null,

  inspectorTab: 'thread',
  activeNodeId: null,
  isApprovalSheetOpen: false,
  isResolveSheetOpen: false,
  isMockMode: isMock(),
  memoryVersion: 0,
  isSidebarOpen: true,
  isInspectorOpen: true,

  setSidebarOpen: (isSidebarOpen) => set({ isSidebarOpen }),
  toggleSidebar: () => set((state) => ({ isSidebarOpen: !state.isSidebarOpen })),
  setInspectorOpen: (isInspectorOpen) => set({ isInspectorOpen }),
  toggleInspector: () => set((state) => ({ isInspectorOpen: !state.isInspectorOpen })),

  setTenant: (tenant) =>
    set({
      tenant,
      activeRunId: null,
      runStatus: 'idle',
      missionText: '',
      activeNodeId: null,
      lanes: initialLanes,
      evidence: { nodes: [], edges: [] },
      proposedActions: [],
      answer: '',
    }),

  setInspectorTab: (inspectorTab) => set({ inspectorTab }),
  setActiveNodeId: (activeNodeId) => set({ activeNodeId }),
  setApprovalSheetOpen: (isApprovalSheetOpen) => set({ isApprovalSheetOpen }),
  setResolveSheetOpen: (isResolveSheetOpen) => set({ isResolveSheetOpen }),
  setIsMockMode: (isMockMode) => {
    setMockMode(isMockMode);
    set({ isMockMode });
  },
  incrementMemoryVersion: () => set((state) => ({ memoryVersion: state.memoryVersion + 1 })),
  setRuns: (runs) => set({ runs }),

  initMissionRun: (runId, text, mode) =>
    set({
      activeRunId: runId,
      missionText: text,
      missionMode: mode,
      runStatus: 'running',
      appliedSeqs: [],
      lanes: {
        scout: { status: 'Scout standing by...', isWorking: false, tools: [], findings: '' },
        archivist: { status: 'Archivist standing by...', isWorking: false, tools: [], findings: '' },
        responder: { status: 'Responder standing by...', isWorking: false, tools: [], findings: '' },
      },
      recalledCount: 0,
      recalledItems: null,
      evidence: { nodes: [], edges: [] },
      handoffs: [],
      proposedActions: [],
      answer: '',
      citations: [],
      ungrounded: [],
      metrics: null,
      error: null,
    }),

  resetRunState: () =>
    set({
      activeRunId: null,
      runStatus: 'idle',
      lanes: initialLanes,
      evidence: { nodes: [], edges: [] },
      proposedActions: [],
      answer: '',
      citations: [],
      ungrounded: [],
      metrics: null,
      error: null,
    }),

  applyEvent: (event: AppEvent) =>
    set((state) => {
      // Idempotency: ignore already applied sequence numbers (skip keepalive heartbeats with seq < 0)
      if (event.seq >= 0 && state.appliedSeqs.includes(event.seq)) {
        return state;
      }
      const updatedSeqs = event.seq >= 0 ? [...state.appliedSeqs, event.seq] : state.appliedSeqs;

      const agentKey = event.agent as 'scout' | 'archivist' | 'responder';
      const data = event.data || {};

      switch (event.type) {
        case 'run.started':
          return {
            ...state,
            appliedSeqs: updatedSeqs,
            activeRunId: data.run_id || state.activeRunId,
            missionText: data.mission || state.missionText,
            missionMode: data.mode || state.missionMode,
            runStatus: 'running',
          };

        case 'agent.status':
          if (agentKey && state.lanes[agentKey]) {
            return {
              ...state,
              appliedSeqs: updatedSeqs,
              lanes: {
                ...state.lanes,
                [agentKey]: {
                  ...state.lanes[agentKey],
                  status: data.status || state.lanes[agentKey].status,
                  isWorking: true,
                },
              },
            };
          }
          return { ...state, appliedSeqs: updatedSeqs };

        case 'memory.recalled':
          return {
            ...state,
            appliedSeqs: updatedSeqs,
            recalledCount: data.count || 0,
            recalledItems: data.items || null,
          };

        case 'tool.call':
          if (agentKey && state.lanes[agentKey]) {
            const newToolCall: ToolCallItem = {
              tool: data.tool,
              args: data.args || {},
            };
            return {
              ...state,
              appliedSeqs: updatedSeqs,
              lanes: {
                ...state.lanes,
                [agentKey]: {
                  ...state.lanes[agentKey],
                  status: `Calling ${data.tool}...`,
                  isWorking: true,
                  tools: [...state.lanes[agentKey].tools, newToolCall],
                },
              },
            };
          }
          return { ...state, appliedSeqs: updatedSeqs };

        case 'tool.result':
          if (agentKey && state.lanes[agentKey]) {
            // Update the latest tool call in this lane
            const currentTools = [...state.lanes[agentKey].tools];
            if (currentTools.length > 0) {
              const lastIdx = currentTools.length - 1;
              currentTools[lastIdx] = {
                ...currentTools[lastIdx],
                summary: data.summary,
                cypher: data.cypher,
                ms: data.ms,
                evidence: data.evidence,
              };
            }

            // Merge evidence nodes and edges
            const newNodesMap = new Map<string, EvidenceNode>();
            state.evidence.nodes.forEach((n) => newNodesMap.set(n.id, n));
            (data.evidence?.nodes || []).forEach((n: EvidenceNode) => newNodesMap.set(n.id, n));

            const edgeKey = (e: EvidenceEdge) => `${e.src}:${e.rel}:${e.dst}`;
            const edgesMap = new Map<string, EvidenceEdge>();
            state.evidence.edges.forEach((e) => edgesMap.set(edgeKey(e), e));
            (data.evidence?.edges || []).forEach((e: EvidenceEdge) => edgesMap.set(edgeKey(e), e));

            return {
              ...state,
              appliedSeqs: updatedSeqs,
              lanes: {
                ...state.lanes,
                [agentKey]: {
                  ...state.lanes[agentKey],
                  status: data.summary || state.lanes[agentKey].status,
                  tools: currentTools,
                },
              },
              evidence: {
                nodes: Array.from(newNodesMap.values()),
                edges: Array.from(edgesMap.values()),
              },
            };
          }
          return { ...state, appliedSeqs: updatedSeqs };

        case 'task.done':
          if (agentKey && state.lanes[agentKey]) {
            return {
              ...state,
              appliedSeqs: updatedSeqs,
              lanes: {
                ...state.lanes,
                [agentKey]: {
                  ...state.lanes[agentKey],
                  status: 'Investigation complete',
                  isWorking: false,
                  findings: data.findings || state.lanes[agentKey].findings,
                },
              },
            };
          }
          return { ...state, appliedSeqs: updatedSeqs };

        case 'handoff':
          return {
            ...state,
            appliedSeqs: updatedSeqs,
            handoffs: [...state.handoffs, data],
          };

        case 'action.proposed':
          if (data.action) {
            const existingIds = state.proposedActions.map((a) => a.id);
            if (!existingIds.includes(data.action.id)) {
              return {
                ...state,
                appliedSeqs: updatedSeqs,
                proposedActions: [...state.proposedActions, data.action],
                isApprovalSheetOpen: true, // auto-surface approval sheet on action proposal
              };
            }
          }
          return { ...state, appliedSeqs: updatedSeqs };

        case 'answer.final':
          return {
            ...state,
            appliedSeqs: updatedSeqs,
            answer: data.text || '',
            citations: data.citations || [],
            ungrounded: data.ungrounded || [],
          };

        case 'run.completed':
          return {
            ...state,
            appliedSeqs: updatedSeqs,
            runStatus: 'completed',
            metrics: data.metrics || state.metrics,
            lanes: {
              scout: { ...state.lanes.scout, isWorking: false },
              archivist: { ...state.lanes.archivist, isWorking: false },
              responder: { ...state.lanes.responder, isWorking: false },
            },
          };

        case 'run.failed':
          return {
            ...state,
            appliedSeqs: updatedSeqs,
            runStatus: 'failed',
            error: data.error || 'Mission execution failed',
            lanes: {
              scout: { ...state.lanes.scout, isWorking: false },
              archivist: { ...state.lanes.archivist, isWorking: false },
              responder: { ...state.lanes.responder, isWorking: false },
            },
          };

        default:
          return { ...state, appliedSeqs: updatedSeqs };
      }
    }),
}));
