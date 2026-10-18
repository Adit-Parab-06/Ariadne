import React, { useState, useMemo, useEffect } from 'react';
import { Compass, Plus, History, Server, ShieldCheck, Search } from 'lucide-react';
import { useAppStore } from '../store';
import { SegmentedControl, Button } from '../ui';
import { TenantId } from '../api/types';

export const Sidebar: React.FC = () => {
  const {
    tenant,
    setTenant,
    runs,
    activeRunId,
    initMissionRun,
    resetRunState,
  } = useAppStore();

  const [searchQuery, setSearchQuery] = useState('');

  const tenantOptions: { value: TenantId; label: string }[] = [
    { value: 'northwind', label: 'Northwind' },
    { value: 'acme', label: 'Acme Corp' },
  ];

  // Cmd+N shortcut for New Mission
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'n' && !e.shiftKey) {
        e.preventDefault();
        resetRunState();
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [resetRunState]);

  const filteredRuns = useMemo(() => {
    if (!searchQuery.trim()) return runs;
    const q = searchQuery.toLowerCase();
    return runs.filter(
      (r) =>
        r.mission.toLowerCase().includes(q) ||
        r.id.toLowerCase().includes(q) ||
        r.mode.toLowerCase().includes(q)
    );
  }, [runs, searchQuery]);

  return (
    <aside className="w-[260px] h-full flex flex-col border-r apple-border bg-bg-2/75 backdrop-blur-md select-none flex-shrink-0 animate-in slide-in-from-left duration-200">
      {/* App brand & Tenant Picker */}
      <div className="p-4 border-b apple-border space-y-3">
        <div className="flex items-center justify-between">
          <div className="flex items-center space-x-2.5">
            <div className="w-8 h-8 rounded-xl bg-blue/15 flex items-center justify-center text-blue border border-blue/30 shadow-xs">
              <Compass className="w-5 h-5" />
            </div>
            <div>
              <h1 className="text-sm font-bold tracking-tight text-label">Ariadne</h1>
              <p className="text-[10px] text-label-2 font-medium">Company Brain</p>
            </div>
          </div>
          <span className="text-[10px] font-mono px-2 py-0.5 rounded-full bg-green/15 text-green border border-green/30 font-semibold">
            v1.0
          </span>
        </div>

        <div>
          <label className="text-[10px] font-semibold uppercase tracking-wider text-label-3 block mb-1">
            Active Tenant
          </label>
          <SegmentedControl
            name="tenant-selector"
            options={tenantOptions}
            value={tenant}
            onChange={(val) => setTenant(val)}
            className="w-full"
          />
        </div>
      </div>

      {/* New Mission Action */}
      <div className="p-3 border-b apple-border">
        <Button
          variant="tinted"
          color="blue"
          size="sm"
          onClick={() => resetRunState()}
          className="w-full justify-center space-x-1.5"
          title="Start fresh mission (⌘N)"
        >
          <Plus className="w-4 h-4" />
          <span>New Mission</span>
          <span className="text-[10px] opacity-60 font-mono ml-1">⌘N</span>
        </Button>
      </div>

      {/* Search Filter for Runs */}
      {runs.length > 4 && (
        <div className="px-3 pt-2">
          <div className="relative">
            <Search className="w-3.5 h-3.5 absolute left-2.5 top-2 text-label-3" />
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Search history..."
              className="w-full rounded-lg bg-fill/30 pl-8 pr-2 py-1 text-xs text-label placeholder-label-3 focus:outline-none focus:ring-1 focus:ring-blue"
            />
          </div>
        </div>
      )}

      {/* Run History List */}
      <div className="flex-1 overflow-y-auto p-3 space-y-1.5">
        <div className="flex items-center justify-between px-2 mb-1">
          <span className="text-[11px] font-semibold text-label-3 uppercase tracking-wider flex items-center">
            <History className="w-3.5 h-3.5 mr-1" />
            Mission History
          </span>
          <span className="text-[10px] text-label-3 font-mono font-bold">
            {filteredRuns.length}
          </span>
        </div>

        {filteredRuns.length === 0 ? (
          <div className="p-4 text-center text-xs text-label-3 italic">
            {runs.length === 0
              ? `No past runs recorded for ${tenant}.`
              : 'No matching missions found.'}
          </div>
        ) : (
          filteredRuns.map((r) => {
            const isSelected = r.id === activeRunId;
            return (
              <div
                key={r.id}
                role="button"
                tabIndex={0}
                onClick={() => initMissionRun(r.id, r.mission, r.mode)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' || e.key === ' ') {
                    e.preventDefault();
                    initMissionRun(r.id, r.mission, r.mode);
                  }
                }}
                className={`w-full p-2.5 rounded-xl text-left transition-all border cursor-pointer min-h-[44px] ${
                  isSelected
                    ? 'bg-blue/10 border-blue/40 text-blue shadow-xs'
                    : 'bg-bg/60 border-transparent hover:bg-fill/40 hover:border-apple text-label'
                }`}
              >
                <div className="flex items-center justify-between text-[11px] font-semibold mb-1">
                  <span className="capitalize">{r.mode} Mode</span>
                  <span
                    className={`px-1.5 py-0.2 rounded text-[9px] uppercase font-mono font-bold ${
                      r.status === 'completed' || r.status === 'resolved'
                        ? 'bg-green/15 text-green'
                        : r.status === 'running'
                        ? 'bg-orange/15 text-orange animate-pulse'
                        : 'bg-red/15 text-red'
                    }`}
                  >
                    {r.status}
                  </span>
                </div>
                <p className="text-xs text-label-2 truncate">{r.mission}</p>
                {r.metrics && (
                  <div className="mt-1 flex items-center space-x-2 text-[10px] font-mono text-label-2 font-medium">
                    <span>{r.metrics.tool_calls} tools</span>
                    <span>•</span>
                    <span>{(r.metrics.duration_ms / 1000).toFixed(1)}s</span>
                  </div>
                )}
              </div>
            );
          })
        )}
      </div>

      {/* Footer Info */}
      <div className="p-3 border-t apple-border bg-bg/40 text-[11px] text-label-2 font-medium flex items-center justify-between">
        <div className="flex items-center space-x-1.5">
          <Server className="w-3.5 h-3.5 text-blue" />
          <span>FalkorDB Graph</span>
        </div>
        <div className="flex items-center space-x-1 text-green">
          <ShieldCheck className="w-3.5 h-3.5" />
          <span className="font-medium">Active</span>
        </div>
      </div>
    </aside>
  );
};
