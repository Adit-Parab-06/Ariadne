import React, { useRef, useEffect, useState } from 'react';
import {
  ArrowUp,
  CheckCircle,
  ArrowRight,
  ShieldAlert,
  PanelLeft,
  PanelRight,
  Square,
  RotateCcw,
  Copy,
  Check,
  Compass,
  Zap,
  Activity,
  Layers,
} from 'lucide-react';
import { useAppStore } from '../store';
import { api } from '../api/client';
import { AgentAvatar, Button, Card, Chip, SegmentedControl, ToolRow } from '../ui';
import { MissionMode } from '../api/types';

export const MainFeed: React.FC = () => {
  const {
    tenant,
    activeRunId,
    missionText,
    missionMode,
    runStatus,
    lanes,
    handoffs,
    proposedActions,
    answer,
    metrics,
    error,
    recalledCount,
    isMockMode,
    isSidebarOpen,
    isInspectorOpen,
    setIsMockMode,
    toggleSidebar,
    toggleInspector,
    setApprovalSheetOpen,
    setResolveSheetOpen,
    setInspectorTab,
    setActiveNodeId,
    initMissionRun,
    applyEvent,
    resetRunState,
  } = useAppStore();

  const [inputVal, setInputVal] = useState('');
  const [selectedMode, setSelectedMode] = useState<MissionMode>('respond');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [reportCopied, setReportCopied] = useState(false);

  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const feedEndRef = useRef<HTMLDivElement>(null);
  const activeUnsubRef = useRef<(() => void) | null>(null);

  // Command-K keyboard shortcut to focus composer
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
        e.preventDefault();
        textareaRef.current?.focus();
      }
      if (e.key === 'Escape' && document.activeElement === textareaRef.current) {
        textareaRef.current?.blur();
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, []);

  // Auto-scroll feed on new events
  useEffect(() => {
    feedEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [lanes, answer, handoffs, proposedActions]);

  // Cleanup active event listener on unmount
  useEffect(() => {
    return () => {
      if (activeUnsubRef.current) {
        activeUnsubRef.current();
        activeUnsubRef.current = null;
      }
    };
  }, []);

  const handleSend = async () => {
    const text = inputVal.trim();
    if (!text || isSubmitting) return;

    setIsSubmitting(true);
    setInputVal('');

    try {
      const { run_id } = await api.startMission(tenant, text, selectedMode);
      initMissionRun(run_id, text, selectedMode);

      const unsub = api.subscribeRunEvents(tenant, run_id, (ev) => {
        applyEvent(ev);
      });
      activeUnsubRef.current = unsub;
    } catch (err: any) {
      console.error('Failed to start mission', err);
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleStopRun = () => {
    if (activeUnsubRef.current) {
      activeUnsubRef.current();
      activeUnsubRef.current = null;
    }
    useAppStore.setState({ runStatus: 'completed' });
  };

  const handleCopyReport = () => {
    if (!answer) return;
    navigator.clipboard.writeText(answer);
    setReportCopied(true);
    setTimeout(() => setReportCopied(false), 2000);
  };

  const renderFormattedAnswer = (rawText: string) => {
    const parts = [];
    const pattern = /\[\[([a-zA-Z0-9_\-]+)\]\]/g;
    let lastIndex = 0;
    let match;

    while ((match = pattern.exec(rawText)) !== null) {
      if (match.index > lastIndex) {
        parts.push(rawText.substring(lastIndex, match.index));
      }
      const nodeId = match[1];
      parts.push(
        <Chip
          key={`${nodeId}-${match.index}`}
          label={nodeId}
          onClick={() => {
            setActiveNodeId(nodeId);
            setInspectorTab('thread');
          }}
          className="mx-0.5 cursor-pointer"
        />
      );
      lastIndex = pattern.lastIndex;
    }
    if (lastIndex < rawText.length) {
      parts.push(rawText.substring(lastIndex));
    }

    return (
      <div className="text-sm leading-relaxed text-label space-y-3 whitespace-pre-wrap font-sans">
        {parts}
      </div>
    );
  };

  return (
    <main className="flex-1 h-full flex flex-col bg-bg overflow-hidden relative">
      {/* ================= UNIFIED TOOLBAR ================= */}
      <header className="h-12 border-b apple-border flex items-center justify-between px-4 bg-bg/85 backdrop-blur-md z-10 select-none">
        {/* Left: Sidebar Toggle & Tenant Context */}
        <div className="flex items-center space-x-2.5">
          <button
            type="button"
            onClick={toggleSidebar}
            title={isSidebarOpen ? 'Hide Sidebar (⌘[)' : 'Show Sidebar (⌘[)'}
            className={`p-1.5 rounded-lg border transition-all ${
              isSidebarOpen
                ? 'bg-fill/40 border-apple text-label hover:bg-fill/70'
                : 'bg-transparent border-transparent text-label-2 hover:bg-fill/30 hover:text-label'
            }`}
          >
            <PanelLeft className="w-4 h-4" />
          </button>

          <div className="h-4 w-px bg-sep/40" />

          <div className="flex items-center space-x-2">
            <span className="w-2 h-2 rounded-full bg-blue" />
            <span className="text-xs font-semibold text-label">
              {tenant === 'northwind' ? 'Northwind FinTech' : 'Acme Logistics'}
            </span>
            {activeRunId && (
              <span className="text-[11px] font-mono text-label-2 font-semibold px-1.5 py-0.2 rounded bg-fill/50">
                {activeRunId}
              </span>
            )}
          </div>
        </div>

        {/* Right: Actions, Controls, and Inspector Toggle */}
        <div className="flex items-center space-x-2">
          {runStatus === 'running' && (
            <Button
              variant="tinted"
              color="red"
              size="sm"
              onClick={handleStopRun}
              className="space-x-1.5 animate-pulse"
              title="Stop investigation"
            >
              <Square className="w-3.5 h-3.5 fill-current" />
              <span>Stop</span>
            </Button>
          )}

          {runStatus === 'completed' && (
            <Button
              variant="tinted"
              color="green"
              size="sm"
              onClick={() => setResolveSheetOpen(true)}
              className="space-x-1"
            >
              <CheckCircle className="w-3.5 h-3.5" />
              <span>Resolve</span>
            </Button>
          )}

          {(missionText || activeRunId) && (
            <Button
              variant="plain"
              color="gray"
              size="sm"
              onClick={() => resetRunState()}
              className="space-x-1 text-label-2 hover:text-label"
              title="Start a new mission"
            >
              <RotateCcw className="w-3.5 h-3.5" />
              <span className="hidden sm:inline">New</span>
            </Button>
          )}

          <div className="h-4 w-px bg-sep/40 mx-1" />

          {/* Mode Switcher Pill */}
          <button
            type="button"
            onClick={() => setIsMockMode(!isMockMode)}
            className={`flex items-center space-x-1.5 text-[11px] font-medium px-2.5 py-1 rounded-full border transition-all ${
              isMockMode
                ? 'bg-orange/15 text-orange border-orange/30 hover:bg-orange/20'
                : 'bg-green/15 text-green border-green/30 hover:bg-green/20'
            }`}
            title="Toggle between Live Backend and Mock Mode"
          >
            <span
              className={`w-1.5 h-1.5 rounded-full ${
                isMockMode ? 'bg-orange' : 'bg-green animate-pulse'
              }`}
            />
            <span className="font-semibold">{isMockMode ? 'Mock' : 'Live'}</span>
          </button>

          {/* Inspector Toggle */}
          <button
            type="button"
            onClick={toggleInspector}
            title={isInspectorOpen ? 'Hide Inspector (⌘])' : 'Show Inspector (⌘])'}
            className={`p-1.5 rounded-lg border transition-all ${
              isInspectorOpen
                ? 'bg-fill/40 border-apple text-label hover:bg-fill/70'
                : 'bg-transparent border-transparent text-label-2 hover:bg-fill/30 hover:text-label'
            }`}
          >
            <PanelRight className="w-4 h-4" />
          </button>
        </div>
      </header>

      {/* ================= MAIN FEED SCROLL AREA ================= */}
      <div className="flex-1 overflow-y-auto p-6 space-y-6 max-w-4xl mx-auto w-full">
        {/* Welcome Launchpad without unnecessary captions */}
        {!missionText && (
          <div className="py-10 space-y-5">
            <div className="text-center space-y-1.5 max-w-md mx-auto">
              <div className="w-12 h-12 rounded-2xl bg-blue/10 text-blue mx-auto flex items-center justify-center border border-blue/20 shadow-xs mb-3">
                <Compass className="w-6 h-6" />
              </div>
              <h2 className="text-xl font-bold tracking-tight text-label">
                Ariadne Brain
              </h2>
              <p className="text-xs text-label-2 font-medium">
                Incident Response & Institutional Memory
              </p>
            </div>

            {/* Quick Explore Scenarios */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-3 pt-2">
              {/* Scenario 1: Northwind */}
              <button
                type="button"
                onClick={() => {
                  useAppStore.setState({ tenant: 'northwind' });
                  setInputVal('payments-api p99 latency is 4.2s and 5xx errors are at 8%');
                  setSelectedMode('respond');
                }}
                className="p-3.5 rounded-2xl bg-bg-2 border apple-border hover:border-blue/40 hover:shadow-xs text-left transition-all space-y-1.5 group"
              >
                <div className="flex items-center justify-between">
                  <span className="text-xs font-bold text-blue flex items-center space-x-1">
                    <Zap className="w-3.5 h-3.5" />
                    <span>Northwind</span>
                  </span>
                  <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-blue/10 text-blue font-bold">
                    Respond
                  </span>
                </div>
                <p className="text-xs font-semibold text-label group-hover:text-blue transition-colors">
                  payments-api latency spike & 5xx surge
                </p>
              </button>

              {/* Scenario 2: Acme */}
              <button
                type="button"
                onClick={() => {
                  useAppStore.setState({ tenant: 'acme' });
                  setInputVal('order-service timeout rate is 12% and warehouse-api is returning 504 Gateway Timeout');
                  setSelectedMode('respond');
                }}
                className="p-3.5 rounded-2xl bg-bg-2 border apple-border hover:border-blue/40 hover:shadow-xs text-left transition-all space-y-1.5 group"
              >
                <div className="flex items-center justify-between">
                  <span className="text-xs font-bold text-orange flex items-center space-x-1">
                    <Activity className="w-3.5 h-3.5" />
                    <span>Acme Corp</span>
                  </span>
                  <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-orange/10 text-orange font-bold">
                    Respond
                  </span>
                </div>
                <p className="text-xs font-semibold text-label group-hover:text-blue transition-colors">
                  warehouse-api 504 Gateway Timeout
                </p>
              </button>

              {/* Scenario 3: Knowledge Graph Query */}
              <button
                type="button"
                onClick={() => {
                  setInputVal('What services, customers, and procedures are affected if ledger-db goes offline?');
                  setSelectedMode('ask');
                }}
                className="p-3.5 rounded-2xl bg-bg-2 border apple-border hover:border-blue/40 hover:shadow-xs text-left transition-all space-y-1.5 group"
              >
                <div className="flex items-center justify-between">
                  <span className="text-xs font-bold text-purple flex items-center space-x-1">
                    <Layers className="w-3.5 h-3.5" />
                    <span>Analysis</span>
                  </span>
                  <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-purple/10 text-purple font-bold">
                    Ask Mode
                  </span>
                </div>
                <p className="text-xs font-semibold text-label group-hover:text-blue transition-colors">
                  ledger-db blast radius analysis
                </p>
              </button>
            </div>
          </div>
        )}

        {/* User Alert Message */}
        {missionText && (
          <div className="flex justify-end animate-in fade-in slide-in-from-bottom-2 duration-150">
            <div className="bg-blue text-white px-4 py-3 rounded-2xl max-w-xl shadow-xs text-sm leading-relaxed">
              <div className="text-[10px] font-bold uppercase tracking-wider opacity-90 mb-1">
                {missionMode === 'respond' ? 'Incident Alert' : 'Inquiry'}
              </div>
              <p>{missionText}</p>
            </div>
          </div>
        )}

        {/* Error State */}
        {error && (
          <Card className="border-red/30 bg-red/10 text-red flex items-start space-x-3 p-4">
            <ShieldAlert className="w-5 h-5 flex-shrink-0 mt-0.5" />
            <div>
              <h4 className="text-sm font-semibold">Mission Failed</h4>
              <p className="text-xs text-red mt-0.5">{error}</p>
            </div>
          </Card>
        )}

        {/* Parallel Agent Lanes */}
        {missionText && (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {/* Scout Lane */}
            <Card
              className={`space-y-3 transition-all ${
                lanes.scout.isWorking ? 'ring-1 ring-blue/40 shadow-xs' : ''
              }`}
            >
              <div className="flex items-center space-x-3">
                <AgentAvatar role="scout" isWorking={lanes.scout.isWorking} />
                <div className="flex-1 min-w-0">
                  <h3 className="text-sm font-semibold text-label">Scout</h3>
                  <p className="text-xs text-label-2 font-medium truncate">{lanes.scout.status}</p>
                </div>
              </div>

              {lanes.scout.tools.length > 0 && (
                <div className="space-y-1.5 pt-1">
                  {lanes.scout.tools.map((tc, idx) => (
                    <ToolRow key={idx} toolCall={tc} />
                  ))}
                </div>
              )}

              {lanes.scout.findings && (
                <div className="text-xs bg-bg/60 p-2.5 rounded-xl border apple-border text-label-2 whitespace-pre-wrap leading-relaxed font-normal">
                  {lanes.scout.findings}
                </div>
              )}
            </Card>

            {/* Archivist Lane */}
            <Card
              className={`space-y-3 transition-all ${
                lanes.archivist.isWorking ? 'ring-1 ring-purple/40 shadow-xs' : ''
              }`}
            >
              <div className="flex items-center space-x-3">
                <AgentAvatar role="archivist" isWorking={lanes.archivist.isWorking} />
                <div className="flex-1 min-w-0">
                  <h3 className="text-sm font-semibold text-label">Archivist</h3>
                  <p className="text-xs text-label-2 font-medium truncate">{lanes.archivist.status}</p>
                </div>
                {recalledCount > 0 && (
                  <span className="text-[10px] bg-purple/15 text-purple font-mono font-bold px-2 py-0.5 rounded-full border border-purple/30">
                    {recalledCount} recalled
                  </span>
                )}
              </div>

              {lanes.archivist.tools.length > 0 && (
                <div className="space-y-1.5 pt-1">
                  {lanes.archivist.tools.map((tc, idx) => (
                    <ToolRow key={idx} toolCall={tc} />
                  ))}
                </div>
              )}

              {lanes.archivist.findings && (
                <div className="text-xs bg-bg/60 p-2.5 rounded-xl border apple-border text-label-2 whitespace-pre-wrap leading-relaxed font-normal">
                  {lanes.archivist.findings}
                </div>
              )}
            </Card>
          </div>
        )}

        {/* Handoff Banners */}
        {handoffs.map((h, idx) => (
          <div
            key={idx}
            className="flex items-center justify-center space-x-2 py-1 text-xs text-label-2 font-medium animate-in fade-in duration-150"
          >
            <span className="capitalize font-semibold text-label">{h.from}</span>
            <ArrowRight className="w-3.5 h-3.5 text-blue" />
            <span className="capitalize font-semibold text-label">{h.to}</span>
            <span className="text-[11px] text-label-2">({h.note})</span>
          </div>
        ))}

        {/* Responder Lane */}
        {missionMode === 'respond' &&
          (lanes.responder.tools.length > 0 || lanes.responder.isWorking || proposedActions.length > 0) && (
            <Card className="space-y-3 border-orange/30 bg-orange/5">
              <div className="flex items-center space-x-3">
                <AgentAvatar role="responder" isWorking={lanes.responder.isWorking} />
                <div className="flex-1 min-w-0">
                  <h3 className="text-sm font-semibold text-label">Responder</h3>
                  <p className="text-xs text-label-2 font-medium truncate">{lanes.responder.status}</p>
                </div>
              </div>

              {lanes.responder.tools.length > 0 && (
                <div className="space-y-1.5 pt-1">
                  {lanes.responder.tools.map((tc, idx) => (
                    <ToolRow key={idx} toolCall={tc} />
                  ))}
                </div>
              )}
            </Card>
          )}

        {/* Proposed Actions Card */}
        {proposedActions.length > 0 && (
          <Card className="bg-bg-2 border-blue/30 space-y-3 shadow-xs">
            <div className="flex items-center justify-between">
              <h3 className="text-sm font-bold text-label flex items-center">
                <span>Proposed Actions</span>
                <span className="ml-2 px-2 py-0.5 text-[10px] rounded-full bg-blue text-white font-mono font-bold">
                  {proposedActions.length}
                </span>
              </h3>
              <Button
                variant="filled"
                color="blue"
                size="sm"
                onClick={() => setApprovalSheetOpen(true)}
              >
                Review & Approve
              </Button>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-3 gap-2.5">
              {proposedActions.map((act) => (
                <div
                  key={act.id}
                  className="p-3 rounded-xl bg-bg border apple-border text-xs space-y-1 shadow-xs"
                >
                  <div className="flex items-center justify-between">
                    <span className="font-mono font-bold text-blue capitalize">
                      {act.kind.replace('_', ' ')}
                    </span>
                    <span
                      className={`text-[9px] px-1.5 py-0.2 rounded font-bold uppercase ${
                        act.status === 'executed'
                          ? 'bg-green/15 text-green'
                          : 'bg-orange/15 text-orange'
                      }`}
                    >
                      {act.status}
                    </span>
                  </div>
                  <p className="text-label font-semibold truncate">
                    {act.payload.title || act.payload.person_name || act.payload.audience}
                  </p>
                </div>
              ))}
            </div>
          </Card>
        )}

        {/* Final Synthesized Answer */}
        {answer && (
          <Card className="space-y-4 border-blue/25 shadow-xs animate-in fade-in duration-200">
            <div className="flex items-center justify-between border-b apple-border pb-3">
              <div className="flex items-center space-x-2.5">
                <AgentAvatar role="synthesizer" size="sm" />
                <h3 className="text-sm font-bold text-label">Synthesized Investigation</h3>
              </div>
              <div className="flex items-center space-x-1.5">
                <Button
                  variant="plain"
                  color="gray"
                  size="sm"
                  onClick={handleCopyReport}
                  className="space-x-1 text-label-2 hover:text-label"
                  title="Copy investigation report"
                >
                  {reportCopied ? (
                    <>
                      <Check className="w-3.5 h-3.5 text-green" />
                      <span className="text-green font-medium">Copied</span>
                    </>
                  ) : (
                    <>
                      <Copy className="w-3.5 h-3.5" />
                      <span>Copy</span>
                    </>
                  )}
                </Button>
                <Button
                  variant="plain"
                  color="blue"
                  size="sm"
                  onClick={() => setInspectorTab('thread')}
                >
                  Inspect Evidence
                </Button>
              </div>
            </div>

            {renderFormattedAnswer(answer)}

            {metrics && (
              <div className="flex items-center space-x-3 pt-3 border-t apple-border text-xs text-label-2 font-mono font-medium">
                <span>{metrics.tool_calls} tool calls</span>
                <span>•</span>
                <span>{(metrics.duration_ms / 1000).toFixed(1)}s elapsed</span>
              </div>
            )}
          </Card>
        )}

        <div ref={feedEndRef} />
      </div>

      {/* ================= COMPOSER ================= */}
      <footer className="p-4 border-t apple-border bg-bg/85 backdrop-blur-md">
        <div className="max-w-4xl mx-auto bg-bg-2 border apple-border rounded-2xl p-2.5 shadow-xs focus-within:ring-2 focus-within:ring-blue focus-within:border-transparent transition-all">
          <textarea
            ref={textareaRef}
            rows={2}
            value={inputVal}
            onChange={(e) => setInputVal(e.target.value)}
            onKeyDown={(e) => {
              if ((e.metaKey || e.ctrlKey) && e.key === 'Enter') {
                e.preventDefault();
                handleSend();
              }
            }}
            placeholder="Ask a question or paste an alert..."
            className="w-full bg-transparent resize-none border-none text-sm text-label placeholder-label-3 focus:outline-none px-2 py-1 leading-relaxed"
          />

          <div className="flex items-center justify-between pt-2 border-t apple-border px-1">
            <SegmentedControl
              name="mode-selector"
              options={[
                { value: 'respond', label: 'Respond' },
                { value: 'ask', label: 'Ask' },
              ]}
              value={selectedMode}
              onChange={(m) => setSelectedMode(m)}
            />

            <button
              type="button"
              disabled={!inputVal.trim() || isSubmitting}
              onClick={handleSend}
              className="w-8 h-8 rounded-full bg-blue text-white flex items-center justify-center hover:opacity-90 active:scale-95 disabled:opacity-30 disabled:pointer-events-none transition-all focus:outline-none focus:ring-2 focus:ring-blue focus:ring-offset-2"
              title="Execute Mission"
            >
              <ArrowUp className="w-4 h-4" />
            </button>
          </div>
        </div>
      </footer>
    </main>
  );
};
