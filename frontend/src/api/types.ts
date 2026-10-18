export type TenantId = 'northwind' | 'acme';

export interface Tenant {
  id: TenantId;
  name: string;
}

export type MissionMode = 'ask' | 'respond';

export type AgentRole = 'scout' | 'archivist' | 'responder' | 'orchestrator' | 'synthesizer' | 'system';

export interface EvidenceNode {
  id: string;
  label: string;
  name: string;
  [key: string]: any;
}

export interface EvidenceEdge {
  src: string;
  rel: string;
  dst: string;
}

export interface Evidence {
  nodes: EvidenceNode[];
  edges: EvidenceEdge[];
}

export interface ToolCallItem {
  id?: string;
  tool: string;
  args: Record<string, any>;
  summary?: string;
  cypher?: string[];
  ms?: number;
  evidence?: Evidence;
}

export interface ActionItem {
  id: string;
  kind: 'page_person' | 'create_ticket' | 'post_status_update' | string;
  status: 'proposed' | 'approved' | 'rejected' | 'executed';
  payload: Record<string, any>;
  ts?: number;
  decided_at?: number;
  side_effect_id?: string;
}

export interface AppEvent {
  seq: number;
  ts: number;
  type:
    | 'run.started'
    | 'task.created'
    | 'task.claimed'
    | 'task.done'
    | 'agent.status'
    | 'tool.call'
    | 'tool.result'
    | 'memory.recalled'
    | 'handoff'
    | 'action.proposed'
    | 'answer.final'
    | 'run.completed'
    | 'run.failed'
    | 'heartbeat';
  agent: string;
  data: any;
}

export interface TaskItem {
  id: string;
  run_id: string;
  kind: 'investigate' | 'recall' | 'act' | 'lab' | string;
  status: 'open' | 'claimed' | 'done' | 'failed';
  owner?: string;
  payload?: any;
  result?: any;
  created_at?: number;
  claimed_at?: number;
  done_at?: number;
}

export interface NextEdge {
  src: string;
  dst: string;
  note?: string;
}

export interface RunMetrics {
  tool_calls: number;
  duration_ms: number;
  memories_recalled?: number;
  ungrounded_count?: number;
  valid_citations_count?: number;
  evidence_nodes_count?: number;
}

export interface RunSummary {
  id: string;
  mission: string;
  mode: MissionMode;
  status: 'running' | 'completed' | 'failed' | 'resolved';
  started_at?: number;
  metrics: RunMetrics;
}

export interface RunDetail {
  id: string;
  status: 'running' | 'completed' | 'failed' | 'resolved';
  mission: string;
  mode: MissionMode;
  answer?: string;
  evidence: Evidence;
  metrics: RunMetrics;
  actions: ActionItem[];
}

export interface MemoryFact {
  id: string;
  subject_id: string;
  predicate: string;
  text: string;
  valid_from: number;
  valid_to: number;
  confidence: number;
}

export interface MemoryEpisode {
  id: string;
  summary: string;
  goal: string;
  outcome: string;
  ts: number;
}

export interface MemoryProcedure {
  id: string;
  name: string;
  trigger_text: string;
  steps: string[] | string;
  success_count: number;
  fail_count: number;
  last_used?: number;
}
