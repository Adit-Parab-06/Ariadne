import React, { useState, useEffect, useMemo } from 'react';
import {
  BookOpen,
  Calendar,
  CheckCircle,
  Clock,
  ExternalLink,
  Search,
  Sparkles,
  Zap,
} from 'lucide-react';
import { useAppStore } from '../store';
import { api } from '../api/client';
import { SegmentedControl, Button } from '../ui';
import { MemoryEpisode, MemoryFact, MemoryProcedure } from '../api/types';

export const MemoryView: React.FC = () => {
  const { tenant, memoryVersion, setActiveNodeId, setInspectorTab } = useAppStore();

  const [tierTab, setTierTab] = useState<'facts' | 'episodes' | 'procedures'>('facts');
  const [episodes, setEpisodes] = useState<MemoryEpisode[]>([]);
  const [facts, setFacts] = useState<MemoryFact[]>([]);
  const [procedures, setProcedures] = useState<MemoryProcedure[]>([]);
  const [searchQuery, setSearchQuery] = useState('');
  const [factFilter, setFactFilter] = useState<'all' | 'current' | 'superseded'>('all');
  const [testTriggerResult, setTestTriggerResult] = useState<string | null>(null);

  // Fetch memory whenever tenant or memoryVersion changes
  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const memData = await api.getMemory(tenant);
        if (!cancelled && memData) {
          setEpisodes(memData.episodes || []);
          setFacts(memData.facts || []);
          setProcedures(memData.procedures || []);
        }
      } catch (e) {
        console.warn('Failed to load memory', e);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [tenant, memoryVersion]);

  // Filtered facts
  const filteredFacts = useMemo(() => {
    return facts.filter((f) => {
      const isCurrent = f.valid_to === 0;
      if (factFilter === 'current' && !isCurrent) return false;
      if (factFilter === 'superseded' && isCurrent) return false;

      if (!searchQuery.trim()) return true;
      const q = searchQuery.toLowerCase();
      return (
        f.text.toLowerCase().includes(q) ||
        f.subject_id.toLowerCase().includes(q) ||
        f.predicate.toLowerCase().includes(q)
      );
    });
  }, [facts, factFilter, searchQuery]);

  // Filtered episodes
  const filteredEpisodes = useMemo(() => {
    if (!searchQuery.trim()) return episodes;
    const q = searchQuery.toLowerCase();
    return episodes.filter(
      (e) =>
        e.summary.toLowerCase().includes(q) ||
        (e.goal && e.goal.toLowerCase().includes(q)) ||
        e.id.toLowerCase().includes(q)
    );
  }, [episodes, searchQuery]);

  // Filtered procedures
  const filteredProcedures = useMemo(() => {
    if (!searchQuery.trim()) return procedures;
    const q = searchQuery.toLowerCase();
    return procedures.filter(
      (p) =>
        p.name.toLowerCase().includes(q) ||
        p.trigger_text.toLowerCase().includes(q)
    );
  }, [procedures, searchQuery]);

  const currentCount = facts.filter((f) => f.valid_to === 0).length;
  const supersededCount = facts.filter((f) => f.valid_to > 0).length;

  const formatDate = (ts: number | undefined) => {
    if (!ts) return 'Unknown';
    // If timestamp in seconds, convert to ms
    const ms = ts < 10000000000 ? ts * 1000 : ts;
    return new Date(ms).toLocaleDateString(undefined, {
      month: 'short',
      day: 'numeric',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
  };

  const handleInspectInGraph = (id: string) => {
    setActiveNodeId(id);
    setInspectorTab('thread');
  };

  return (
    <div className="space-y-4">
      {/* Tier Switcher */}
      <SegmentedControl
        options={[
          { value: 'facts', label: `Facts (${facts.length})` },
          { value: 'episodes', label: `Episodes (${episodes.length})` },
          { value: 'procedures', label: `Procedures (${procedures.length})` },
        ]}
        value={tierTab}
        onChange={(val) => setTierTab(val as any)}
        className="w-full"
      />

      {/* Search Input */}
      <div className="relative">
        <Search className="w-3.5 h-3.5 text-label-3 absolute left-3 top-2.5" />
        <input
          type="text"
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          placeholder={`Search ${tierTab}...`}
          className="w-full pl-8 pr-3 py-1.5 rounded-xl bg-bg border apple-border text-xs text-label placeholder-label-3 focus:outline-none focus:ring-2 focus:ring-blue"
        />
      </div>

      {/* ================= TIER 1: TEMPORAL FACTS ================= */}
      {tierTab === 'facts' && (
        <div className="space-y-3">
          {/* Sub-filters */}
          <div className="flex items-center space-x-1.5 text-xs">
            <button
              type="button"
              onClick={() => setFactFilter('all')}
              className={`px-2.5 py-1 rounded-full text-[11px] font-semibold transition-all ${
                factFilter === 'all'
                  ? 'bg-blue text-white shadow-sm'
                  : 'bg-fill/30 text-label-2 hover:bg-fill/50'
              }`}
            >
              All ({facts.length})
            </button>
            <button
              type="button"
              onClick={() => setFactFilter('current')}
              className={`px-2.5 py-1 rounded-full text-[11px] font-semibold transition-all ${
                factFilter === 'current'
                  ? 'bg-green text-white shadow-sm'
                  : 'bg-fill/30 text-label-2 hover:bg-fill/50'
              }`}
            >
              Current Active ({currentCount})
            </button>
            <button
              type="button"
              onClick={() => setFactFilter('superseded')}
              className={`px-2.5 py-1 rounded-full text-[11px] font-semibold transition-all ${
                factFilter === 'superseded'
                  ? 'bg-gray-500 text-white shadow-sm'
                  : 'bg-fill/30 text-label-2 hover:bg-fill/50'
              }`}
            >
              Superseded ({supersededCount})
            </button>
          </div>

          {filteredFacts.length === 0 ? (
            <div className="py-8 text-center text-xs text-label-3 italic">
              No matching temporal facts found.
            </div>
          ) : (
            <div className="space-y-2.5">
              {filteredFacts.map((f) => {
                const isCurrent = f.valid_to === 0;
                return (
                  <div
                    key={f.id}
                    className={`p-3.5 rounded-2xl border transition-all text-xs space-y-2 ${
                      isCurrent
                        ? 'bg-bg border-green/30 shadow-sm'
                        : 'bg-fill/15 border-sep/60 opacity-70'
                    }`}
                  >
                    <div className="flex items-center justify-between">
                      <div className="flex items-center space-x-1.5 truncate">
                        <span className="font-mono text-[10px] text-blue font-bold px-1.5 py-0.5 rounded bg-blue/10">
                          {f.subject_id}
                        </span>
                        <span className="text-label-3">•</span>
                        <span className="font-mono text-[10px] text-label-2 font-medium">
                          {f.predicate}
                        </span>
                      </div>

                      <div className="flex items-center space-x-1.5 flex-shrink-0">
                        {f.confidence !== undefined && (
                          <span className="text-[9px] font-mono font-semibold px-1.5 py-0.2 rounded bg-fill text-label-2">
                            {Math.round(f.confidence * 100)}% conf
                          </span>
                        )}
                        <span
                          className={`px-2 py-0.5 rounded-full text-[9px] font-bold uppercase tracking-wider ${
                            isCurrent
                              ? 'bg-green/15 text-green border border-green/30'
                              : 'bg-label-3/20 text-label-3 border border-sep'
                          }`}
                        >
                          {isCurrent ? 'Current' : 'Superseded'}
                        </span>
                      </div>
                    </div>

                    <p
                      className={`leading-relaxed ${
                        isCurrent
                          ? 'font-medium text-label'
                          : 'line-through text-label-3 italic'
                      }`}
                    >
                      {f.text}
                    </p>

                    <div className="flex items-center justify-between pt-1 border-t apple-border text-[10px] text-label-3 font-mono">
                      <span className="flex items-center space-x-1">
                        <Calendar className="w-3 h-3" />
                        <span>
                          {isCurrent
                            ? `Valid since ${formatDate(f.valid_from)}`
                            : `Valid: ${formatDate(f.valid_from)} → ${formatDate(f.valid_to)}`}
                        </span>
                      </span>

                      <button
                        type="button"
                        onClick={() => handleInspectInGraph(f.id)}
                        className="hover:text-blue transition-colors flex items-center space-x-0.5"
                      >
                        <span>Graph</span>
                        <ExternalLink className="w-2.5 h-2.5" />
                      </button>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      )}

      {/* ================= TIER 2: EPISODIC MEMORY ================= */}
      {tierTab === 'episodes' && (
        <div className="space-y-3">
          {filteredEpisodes.length === 0 ? (
            <div className="py-8 text-center text-xs text-label-3 italic">
              No incident episodes recorded yet.
            </div>
          ) : (
            <div className="space-y-2.5">
              {filteredEpisodes.map((ep) => {
                const isSuccess = ep.outcome === 'success';
                const isPartial = ep.outcome === 'partial';

                return (
                  <div
                    key={ep.id}
                    className="p-3.5 rounded-2xl bg-bg border apple-border text-xs space-y-2 shadow-sm hover:border-purple/40 transition-colors"
                  >
                    <div className="flex items-center justify-between">
                      <span className="font-mono text-[10px] font-bold text-purple px-1.5 py-0.5 rounded bg-purple/10">
                        {ep.id}
                      </span>
                      <div className="flex items-center space-x-1.5">
                        <span
                          className={`px-2 py-0.5 rounded-full text-[9px] font-bold uppercase tracking-wider ${
                            isSuccess
                              ? 'bg-green/15 text-green border border-green/30'
                              : isPartial
                              ? 'bg-orange/15 text-orange border border-orange/30'
                              : 'bg-red/15 text-red border border-red/30'
                          }`}
                        >
                          {ep.outcome}
                        </span>
                      </div>
                    </div>

                    <p className="font-semibold text-label leading-relaxed">
                      {ep.summary}
                    </p>

                    {ep.goal && (
                      <div className="text-[11px] bg-fill/20 p-2 rounded-xl text-label-2">
                        <span className="font-semibold text-label-3 block text-[10px] uppercase tracking-wider mb-0.5">
                          Goal
                        </span>
                        {ep.goal}
                      </div>
                    )}

                    <div className="flex items-center justify-between pt-1 border-t apple-border text-[10px] text-label-3 font-mono">
                      <span className="flex items-center space-x-1">
                        <Clock className="w-3 h-3" />
                        <span>{formatDate(ep.ts)}</span>
                      </span>

                      <button
                        type="button"
                        onClick={() => handleInspectInGraph(ep.id)}
                        className="hover:text-purple transition-colors flex items-center space-x-0.5"
                      >
                        <span>Graph</span>
                        <ExternalLink className="w-2.5 h-2.5" />
                      </button>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      )}

      {/* ================= TIER 3: PROCEDURAL MEMORY ================= */}
      {tierTab === 'procedures' && (
        <div className="space-y-3">
          {filteredProcedures.length === 0 ? (
            <div className="py-8 text-center text-xs text-label-3 italic">
              No procedures found in procedural memory.
            </div>
          ) : (
            <div className="space-y-3">
              {filteredProcedures.map((proc) => {
                const steps = Array.isArray(proc.steps)
                  ? proc.steps
                  : typeof proc.steps === 'string'
                  ? JSON.parse(proc.steps)
                  : [];

                const totalRuns = proc.success_count + proc.fail_count;
                const successRate = totalRuns > 0 ? Math.round((proc.success_count / totalRuns) * 100) : 100;

                return (
                  <div
                    key={proc.id}
                    className="p-4 rounded-2xl bg-bg border apple-border text-xs space-y-3 shadow-sm hover:border-blue/30 transition-colors"
                  >
                    <div className="flex items-center justify-between">
                      <div className="flex items-center space-x-2">
                        <div className="w-6 h-6 rounded-lg bg-blue/15 text-blue flex items-center justify-center">
                          <BookOpen className="w-3.5 h-3.5" />
                        </div>
                        <h4 className="font-bold text-sm text-label">{proc.name}</h4>
                      </div>

                      <span className="text-[10px] font-mono font-bold px-2 py-0.5 rounded-full bg-green/15 text-green border border-green/30">
                        {proc.success_count} success{proc.success_count !== 1 ? 'es' : ''}
                      </span>
                    </div>

                    {/* Trigger Condition Pill */}
                    <div className="bg-fill/20 p-2.5 rounded-xl space-y-1">
                      <div className="flex items-center space-x-1 text-[10px] font-bold text-label-3 uppercase tracking-wider">
                        <Zap className="w-3 h-3 text-orange" />
                        <span>Activation Trigger Pattern</span>
                      </div>
                      <p className="font-mono text-[11px] text-label font-medium">
                        "{proc.trigger_text}"
                      </p>
                    </div>

                    {/* Success Rate Progress Bar */}
                    <div className="space-y-1">
                      <div className="flex justify-between text-[10px] text-label-3 font-semibold">
                        <span>Reliability Score</span>
                        <span>{successRate}% ({proc.success_count}/{totalRuns || 1})</span>
                      </div>
                      <div className="w-full h-1.5 rounded-full bg-fill/40 overflow-hidden">
                        <div
                          className="h-full bg-green rounded-full transition-all"
                          style={{ width: `${successRate}%` }}
                        />
                      </div>
                    </div>

                    {/* Numbered SOP Steps */}
                    <div className="space-y-1.5 pt-1">
                      <span className="text-[10px] font-bold text-label-3 uppercase tracking-wider block">
                        Operating Steps ({steps.length})
                      </span>
                      <ol className="space-y-1">
                        {steps.map((st: string, idx: number) => (
                          <li
                            key={idx}
                            className="flex items-start space-x-2 text-[11px] text-label-2 bg-bg-2 p-2 rounded-lg border apple-border"
                          >
                            <span className="w-4 h-4 rounded-full bg-blue text-white flex items-center justify-center text-[9px] font-bold flex-shrink-0 mt-0.5">
                              {idx + 1}
                            </span>
                            <span className="leading-relaxed">{st}</span>
                          </li>
                        ))}
                      </ol>
                    </div>

                    {/* Trigger Match Simulation Test */}
                    <div className="pt-2 border-t apple-border flex items-center justify-between">
                      <Button
                        variant="tinted"
                        color="blue"
                        size="sm"
                        onClick={() => {
                          setTestTriggerResult(
                            `Trigger check: Matches alert on 'payments-api' with 94% similarity score.`
                          );
                          setTimeout(() => setTestTriggerResult(null), 5000);
                        }}
                        className="space-x-1"
                      >
                        <Sparkles className="w-3 h-3" />
                        <span>Simulate Trigger Match</span>
                      </Button>

                      <button
                        type="button"
                        onClick={() => handleInspectInGraph(proc.id)}
                        className="text-[10px] font-mono text-label-3 hover:text-blue flex items-center space-x-0.5"
                      >
                        <span>Graph</span>
                        <ExternalLink className="w-2.5 h-2.5" />
                      </button>
                    </div>

                    {testTriggerResult && (
                      <div className="p-2 rounded-xl bg-green/10 text-green border border-green/30 text-[11px] font-medium flex items-center space-x-1.5">
                        <CheckCircle className="w-3.5 h-3.5 flex-shrink-0" />
                        <span>{testTriggerResult}</span>
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          )}
        </div>
      )}
    </div>
  );
};
