import {
  ActionItem,
  AppEvent,
  Evidence,
  MemoryEpisode,
  MemoryFact,
  MemoryProcedure,
  MissionMode,
  NextEdge,
  RunDetail,
  RunSummary,
  TaskItem,
  Tenant,
  TenantId,
} from './types';
import mockRunData from '../mocks/run1.json';

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000';
let currentMock = import.meta.env.VITE_MOCK === '1';

export function isMock(): boolean {
  return currentMock;
}

export function setMockMode(val: boolean) {
  currentMock = val;
}

export const IS_MOCK = currentMock;

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const url = `${API_BASE}${path}`;
  const res = await fetch(url, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...options?.headers,
    },
  });

  if (!res.ok) {
    let errMessage = `HTTP ${res.status}: ${res.statusText}`;
    try {
      const errJson = await res.json();
      if (errJson.error) errMessage = errJson.error;
      else if (errJson.detail) errMessage = errJson.detail;
    } catch {
      // Ignore
    }
    throw new Error(errMessage);
  }

  return res.json();
}

export const api = {
  async getHealth(): Promise<{ falkordb: boolean; model: string }> {
    if (isMock()) return { falkordb: true, model: 'gemini-3.5-flash-lite (Mock Mode)' };
    return request('/api/health');
  },

  async getTenants(): Promise<Tenant[]> {
    if (isMock()) {
      return [
        { id: 'northwind', name: 'Northwind Cloud' },
        { id: 'acme', name: 'Acme Corp' },
      ];
    }
    return request('/api/tenants');
  },

  async getTools(): Promise<any[]> {
    if (isMock()) {
      return [
        { name: 'resolve_service', description: 'Resolves service name or ID', agents: ['scout', 'archivist'], readonly: true },
        { name: 'blast_radius', description: 'Computes blast radius upstream or downstream', agents: ['scout'], readonly: true },
        { name: 'similar_incidents', description: 'Semantic vector search on past incidents', agents: ['archivist'], readonly: true },
        { name: 'find_experts', description: 'Ranks on-call and domain experts', agents: ['archivist'], readonly: true },
        { name: 'page_person', description: 'Pages available engineer', agents: ['responder'], readonly: false },
        { name: 'create_ticket', description: 'Creates ticket in tracking system', agents: ['responder'], readonly: false },
        { name: 'post_status_update', description: 'Broadcasts status update', agents: ['responder'], readonly: false },
      ];
    }
    return request('/api/tools');
  },

  async getGraphOverview(tenant: TenantId): Promise<Evidence> {
    if (isMock()) {
      if (tenant === 'acme') {
        const acmeNodes = [
          { id: 'svc_order_service', label: 'Service', name: 'order-service' },
          { id: 'svc_inventory_db', label: 'Service', name: 'inventory-db' },
          { id: 'svc_warehouse_api', label: 'Service', name: 'warehouse-api' },
          { id: 'svc_shipping_tracker', label: 'Service', name: 'shipping-tracker' },
          { id: 'svc_notification_worker', label: 'Service', name: 'notification-worker' },
          { id: 'cus_apex_logistics', label: 'Customer', name: 'Apex Logistics' },
          { id: 'cus_zenith_retail', label: 'Customer', name: 'Zenith Retail' },
          { id: 'per_elena_rostova', label: 'Person', name: 'Elena Rostova' },
          { id: 'inc_3102', label: 'Incident', name: 'warehouse-api 504 gateway timeout cascade' },
          { id: 'prc_wh_scale', label: 'Procedure', name: 'Warehouse API replica autoscaling' },
        ];
        const acmeEdges = [
          { src: 'svc_order_service', rel: 'DEPENDS_ON', dst: 'svc_warehouse_api' },
          { src: 'svc_order_service', rel: 'DEPENDS_ON', dst: 'svc_inventory_db' },
          { src: 'svc_warehouse_api', rel: 'DEPENDS_ON', dst: 'svc_shipping_tracker' },
          { src: 'cus_apex_logistics', rel: 'USES', dst: 'svc_order_service' },
          { src: 'cus_zenith_retail', rel: 'USES', dst: 'svc_order_service' },
          { src: 'inc_3102', rel: 'AFFECTED', dst: 'svc_order_service' },
          { src: 'inc_3102', rel: 'AFFECTED', dst: 'svc_warehouse_api' },
          { src: 'per_elena_rostova', rel: 'WORKED_ON', dst: 'svc_warehouse_api' },
        ];
        return { nodes: acmeNodes, edges: acmeEdges };
      }

      const heroNodes = [
        { id: 'svc_payments_api', label: 'Service', name: 'payments-api' },
        { id: 'svc_ledger_db', label: 'Service', name: 'ledger-db' },
        { id: 'svc_checkout_api', label: 'Service', name: 'checkout-api' },
        { id: 'svc_checkout_web', label: 'Service', name: 'checkout-web' },
        { id: 'svc_event_bus', label: 'Service', name: 'event-bus' },
        { id: 'svc_fraud_service', label: 'Service', name: 'fraud-service' },
        { id: 'cus_pinecrest_bank', label: 'Customer', name: 'Pinecrest Bank' },
        { id: 'cus_helios_retail', label: 'Customer', name: 'Helios Retail' },
        { id: 'cus_orbit_pay', label: 'Customer', name: 'Orbit Pay' },
        { id: 'per_priya_nair', label: 'Person', name: 'Priya Nair' },
        { id: 'per_dev_okafor', label: 'Person', name: 'Dev Okafor' },
        { id: 'inc_2041', label: 'Incident', name: 'payments-api p99 latency spike and elevated 5xx' },
        { id: 'doc_rb_ledger_pool', label: 'Doc', name: 'Ledger connection pool saturation' },
        { id: 'prc_ledger_pool', label: 'Procedure', name: 'Ledger pool saturation response' },
      ];
      const heroEdges = [
        { src: 'svc_checkout_web', rel: 'DEPENDS_ON', dst: 'svc_checkout_api' },
        { src: 'svc_checkout_api', rel: 'DEPENDS_ON', dst: 'svc_payments_api' },
        { src: 'svc_payments_api', rel: 'DEPENDS_ON', dst: 'svc_ledger_db' },
        { src: 'svc_payments_api', rel: 'DEPENDS_ON', dst: 'svc_event_bus' },
        { src: 'svc_payments_api', rel: 'DEPENDS_ON', dst: 'svc_fraud_service' },
        { src: 'cus_pinecrest_bank', rel: 'USES', dst: 'svc_checkout_web' },
        { src: 'inc_2041', rel: 'AFFECTED', dst: 'svc_payments_api' },
        { src: 'inc_2041', rel: 'AFFECTED', dst: 'svc_ledger_db' },
        { src: 'inc_2041', rel: 'RESOLVED_WITH', dst: 'doc_rb_ledger_pool' },
        { src: 'per_dev_okafor', rel: 'WORKED_ON', dst: 'svc_ledger_db' },
      ];
      return { nodes: heroNodes, edges: heroEdges };
    }
    return request(`/api/${tenant}/graph/overview`);
  },

  async startMission(
    tenant: TenantId,
    text: string,
    mode: MissionMode = 'respond',
    conversation_id?: string
  ): Promise<{ run_id: string; conversation_id: string }> {
    if (isMock()) {
      return {
        run_id: 'run_mock_hero_01',
        conversation_id: 'cnv_mock_01',
      };
    }
    return request(`/api/${tenant}/missions`, {
      method: 'POST',
      body: JSON.stringify({ text, mode, conversation_id }),
    });
  },

  async getRun(tenant: TenantId, run_id: string): Promise<RunDetail> {
    if (isMock()) {
      return {
        id: run_id,
        status: 'completed',
        mission: 'payments-api p99 latency is 4.2s and 5xx errors are at 8%',
        mode: 'respond',
        answer: 'Payments API pool saturation resolved.',
        evidence: { nodes: [], edges: [] },
        metrics: { tool_calls: 14, duration_ms: 14500 },
        actions: [],
      };
    }
    return request(`/api/${tenant}/runs/${run_id}`);
  },

  async listRuns(tenant: TenantId): Promise<RunSummary[]> {
    if (isMock()) {
      return [
        {
          id: 'run_mock_hero_01',
          mission: 'payments-api p99 latency is 4.2s and 5xx errors are at 8%',
          mode: 'respond',
          status: 'completed',
          started_at: Date.now() - 3600000,
          metrics: { tool_calls: 14, duration_ms: 35616 },
        },
      ];
    }
    return request(`/api/${tenant}/runs`);
  },

  async postActionDecision(
    tenant: TenantId,
    action_id: string,
    decision: 'approve' | 'reject'
  ): Promise<ActionItem> {
    if (isMock()) {
      return {
        id: action_id,
        kind: 'page_person',
        status: decision === 'approve' ? 'executed' : 'rejected',
        payload: { simulated: true },
        side_effect_id: `se_mock_${action_id}`,
      };
    }
    return request(`/api/${tenant}/actions/${action_id}/decision`, {
      method: 'POST',
      body: JSON.stringify({ decision }),
    });
  },

  async resolveRun(
    tenant: TenantId,
    run_id: string,
    note: string
  ): Promise<{ memory_written: Array<{ id: string; label: string; name: string }> }> {
    if (isMock()) {
      return {
        memory_written: [
          { id: 'prc_ledger_pool', label: 'Procedure', name: 'Ledger pool saturation response' },
          { id: 'epi_mock_02', label: 'Episode', name: 'Resolved payments-api latency via pool increase' },
          { id: 'fct_mock_02', label: 'Fact', name: 'pgbouncer max_client_conn is 400' },
        ],
      };
    }
    return request(`/api/${tenant}/runs/${run_id}/resolve`, {
      method: 'POST',
      body: JSON.stringify({ note }),
    });
  },

  async getMemory(
    tenant: TenantId,
    kind?: 'episode' | 'fact' | 'procedure'
  ): Promise<any> {
    if (isMock()) {
      if (kind === 'episode') {
        return [
          { id: 'epi_2041', summary: 'Outage due to ledger-db pool saturation', goal: 'Mitigate 5xx', outcome: 'success', ts: Date.now() - 86400000 },
        ] as MemoryEpisode[];
      }
      if (kind === 'fact') {
        return [
          { id: 'fct_ledger_pgb_200', subject_id: 'svc_ledger_db', predicate: 'pgbouncer_max_client_conn', text: 'ledger-db pgbouncer max_client_conn is 200', valid_from: Date.now() - 86400000, valid_to: 0, confidence: 1.0 },
        ] as MemoryFact[];
      }
      if (kind === 'procedure') {
        return [
          { id: 'prc_ledger_pool', name: 'Ledger pool saturation response', trigger_text: 'latency and 5xx on payments-api', steps: ['Inspect pools', 'Compare max_client_conn', 'Reload pgbouncer', 'Verify recovery'], success_count: 2, fail_count: 0 },
        ] as MemoryProcedure[];
      }
      return {
        episodes: [
          { id: 'epi_2041', summary: 'Outage due to ledger-db pool saturation', goal: 'Mitigate 5xx', outcome: 'success', ts: Date.now() - 86400000 },
        ],
        facts: [
          { id: 'fct_ledger_pgb_200', subject_id: 'svc_ledger_db', predicate: 'pgbouncer_max_client_conn', text: 'ledger-db pgbouncer max_client_conn is 200', valid_from: Date.now() - 86400000, valid_to: 0, confidence: 1.0 },
        ],
        procedures: [
          { id: 'prc_ledger_pool', name: 'Ledger pool saturation response', trigger_text: 'latency and 5xx on payments-api', steps: ['Inspect pools', 'Compare max_client_conn', 'Reload pgbouncer', 'Verify recovery'], success_count: 2, fail_count: 0 },
        ],
      };
    }
    const qParam = kind ? `?kind=${kind}` : '';
    return request(`/api/${tenant}/memory${qParam}`);
  },

  async getTasks(tenant: TenantId, run_id: string): Promise<{ tasks: TaskItem[]; next: NextEdge[] }> {
    if (isMock()) {
      return {
        tasks: [
          { id: 'tsk_inv_01', run_id, kind: 'investigate', status: 'done', owner: 'scout' },
          { id: 'tsk_rec_01', run_id, kind: 'recall', status: 'done', owner: 'archivist' },
          { id: 'tsk_act_01', run_id, kind: 'act', status: 'done', owner: 'responder' },
        ],
        next: [
          { src: 'tsk_inv_01', dst: 'tsk_act_01', note: 'Investigative findings handed off to Responder' },
          { src: 'tsk_rec_01', dst: 'tsk_act_01', note: 'Historical knowledge handed off to Responder' },
        ],
      };
    }
    return request(`/api/${tenant}/tasks?run_id=${run_id}`);
  },

  async postConcurrencyLab(
    tenant: TenantId,
    tasks: number = 200,
    workers: number = 8
  ): Promise<{ claimed: number; duplicates: number; seconds: number; throughput: number }> {
    if (isMock()) {
      return {
        claimed: tasks,
        duplicates: 0,
        seconds: 0.528,
        throughput: Math.round(tasks / 0.528),
      };
    }
    return request(`/api/${tenant}/lab/concurrency`, {
      method: 'POST',
      body: JSON.stringify({ tasks, workers }),
    });
  },

  /**
   * Subscribes to live or mock SSE event stream.
   * In Mock Mode: replays run1.json with random delays of 300 to 900 ms.
   * In Live Mode: connects EventSource to /api/{tenant}/runs/{run_id}/events.
   */
  subscribeRunEvents(
    tenant: TenantId,
    run_id: string,
    onEvent: (event: AppEvent) => void,
    onError?: (err: any) => void
  ): () => void {
    if (isMock()) {
      let cancelled = false;
      const events: AppEvent[] = (mockRunData as any).events;

      (async () => {
        for (const ev of events) {
          if (cancelled) break;
          // Random delay between 300 and 900 ms
          const delay = Math.floor(Math.random() * (900 - 300 + 1)) + 300;
          await new Promise((resolve) => setTimeout(resolve, delay));
          if (cancelled) break;
          onEvent(ev);
        }
      })();

      return () => {
        cancelled = true;
      };
    }

    const sseUrl = `${API_BASE}/api/${tenant}/runs/${run_id}/events`;
    const es = new EventSource(sseUrl);

    es.onmessage = (msg) => {
      try {
        const ev: AppEvent = JSON.parse(msg.data);
        onEvent(ev);
        if (ev.type === 'run.completed' || ev.type === 'run.failed') {
          es.close();
        }
      } catch (e) {
        console.warn('Failed to parse SSE event data', e);
      }
    };

    es.onerror = (err) => {
      console.warn('EventSource encountered error', err);
      if (onError) onError(err);
    };

    return () => {
      es.close();
    };
  },
};
