import React, { useState, useEffect } from 'react';
import { Bell, Ticket, Radio, CheckCircle, XCircle, CheckCheck } from 'lucide-react';
import { useAppStore } from '../store';
import { api } from '../api/client';
import { Button, Sheet, Toggle } from '../ui';
import { ActionItem } from '../api/types';

export const ApprovalSheet: React.FC = () => {
  const {
    tenant,
    isApprovalSheetOpen,
    setApprovalSheetOpen,
    proposedActions,
  } = useAppStore();

  const [toggles, setToggles] = useState<Record<string, boolean>>({});
  const [isSubmitting, setIsSubmitting] = useState(false);

  const getActionIcon = (kind: string) => {
    switch (kind) {
      case 'page_person':
        return <Bell className="w-4 h-4 text-orange" />;
      case 'create_ticket':
        return <Ticket className="w-4 h-4 text-blue" />;
      case 'post_status_update':
        return <Radio className="w-4 h-4 text-purple" />;
      default:
        return <CheckCircle className="w-4 h-4 text-green" />;
    }
  };

  const isEnabled = (actId: string) => {
    return toggles[actId] !== undefined ? toggles[actId] : true;
  };

  const handleToggle = (actId: string) => {
    setToggles((prev) => ({
      ...prev,
      [actId]: !isEnabled(actId),
    }));
  };

  const handleSelectAll = () => {
    const next: Record<string, boolean> = {};
    proposedActions.forEach((a) => {
      next[a.id] = true;
    });
    setToggles(next);
  };

  const handleDeselectAll = () => {
    const next: Record<string, boolean> = {};
    proposedActions.forEach((a) => {
      next[a.id] = false;
    });
    setToggles(next);
  };

  const pendingActions = proposedActions.filter((a) => a.status === 'proposed');
  const enabledCount = pendingActions.filter((a) => isEnabled(a.id)).length;

  const handleApprove = async () => {
    if (enabledCount === 0 || isSubmitting) return;
    setIsSubmitting(true);
    try {
      for (const act of proposedActions) {
        if (act.status !== 'proposed') continue;
        const decision = isEnabled(act.id) ? 'approve' : 'reject';
        await api.postActionDecision(tenant, act.id, decision);
        act.status = decision === 'approve' ? 'executed' : 'rejected';
      }
      setApprovalSheetOpen(false);
    } catch (e) {
      console.error('Failed to submit action decisions', e);
    } finally {
      setIsSubmitting(false);
    }
  };

  // Keyboard shortcut: Cmd+Enter to approve
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === 'Enter' && isApprovalSheetOpen) {
        e.preventDefault();
        handleApprove();
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isApprovalSheetOpen, enabledCount, isSubmitting]);

  return (
    <Sheet
      isOpen={isApprovalSheetOpen}
      onClose={() => setApprovalSheetOpen(false)}
      title="Proposed Remediation Actions"
    >
      <div className="space-y-3.5">
        {/* Quick Batch Controls */}
        {pendingActions.length > 1 && (
          <div className="flex items-center justify-end space-x-2 text-xs pt-1">
            <button
              type="button"
              onClick={handleSelectAll}
              className="text-blue hover:underline font-semibold text-[11px]"
            >
              Select All
            </button>
            <span className="text-label-2">•</span>
            <button
              type="button"
              onClick={handleDeselectAll}
              className="text-label-2 hover:text-label font-semibold text-[11px]"
            >
              Clear
            </button>
          </div>
        )}

        <div className="space-y-2.5 max-h-[52vh] overflow-y-auto p-0.5">
          {proposedActions.map((act: ActionItem) => {
            const checked = isEnabled(act.id);
            const isExecuted = act.status === 'executed';
            const isRejected = act.status === 'rejected';

            return (
              <div
                key={act.id}
                className={`p-3.5 rounded-2xl border transition-all ${
                  isExecuted
                    ? 'bg-green/10 border-green/30'
                    : isRejected
                    ? 'bg-fill/20 border-sep opacity-50'
                    : checked
                    ? 'bg-bg border-blue/40 shadow-xs'
                    : 'bg-fill/10 border-sep'
                }`}
              >
                <div className="flex items-start justify-between">
                  <div className="flex items-start space-x-3">
                    <div className="p-2 rounded-xl bg-fill/50 mt-0.5">
                      {getActionIcon(act.kind)}
                    </div>
                    <div>
                      <div className="flex items-center space-x-2">
                        <span className="text-xs font-bold text-label">
                          {act.payload.title || act.payload.person_name || 'Status Update'}
                        </span>
                        <span className="text-[10px] font-mono text-label-2 uppercase font-bold">
                          ({act.kind.replace('_', ' ')})
                        </span>
                      </div>
                      <p className="text-xs text-label-2 mt-1 leading-relaxed font-medium">
                        {act.payload.message || act.payload.body || act.payload.text}
                      </p>
                      {act.payload.reason && (
                        <div className="text-[11px] text-label-2 mt-1.5 flex items-center flex-wrap gap-1">
                          <span className="font-semibold text-label">Rationale:</span>
                          <span>{act.payload.reason}</span>
                        </div>
                      )}
                    </div>
                  </div>

                  {!isExecuted && !isRejected && (
                    <Toggle
                      checked={checked}
                      onChange={() => handleToggle(act.id)}
                    />
                  )}

                  {isExecuted && (
                    <span className="inline-flex items-center space-x-1 text-xs text-green font-bold">
                      <CheckCircle className="w-4 h-4" />
                      <span>Simulated</span>
                    </span>
                  )}
                  {isRejected && (
                    <span className="inline-flex items-center space-x-1 text-xs text-label-2 font-medium">
                      <XCircle className="w-4 h-4" />
                      <span>Skipped</span>
                    </span>
                  )}
                </div>
              </div>
            );
          })}
        </div>

        {/* Buttons */}
        <div className="pt-2 space-y-2">
          <button
            type="button"
            disabled={enabledCount === 0 || isSubmitting}
            onClick={handleApprove}
            className="w-full h-[46px] rounded-xl bg-blue text-white font-semibold text-sm hover:opacity-90 active:scale-98 disabled:opacity-40 transition-all flex items-center justify-center space-x-1.5 shadow-xs focus:outline-none focus:ring-2 focus:ring-blue"
          >
            <CheckCheck className="w-4 h-4" />
            <span>
              {isSubmitting
                ? 'Processing...'
                : `Approve ${enabledCount} Action${enabledCount !== 1 ? 's' : ''}`}
            </span>
          </button>

          <Button
            variant="plain"
            color="gray"
            size="sm"
            onClick={() => setApprovalSheetOpen(false)}
            className="w-full justify-center text-label-2 font-medium"
          >
            Cancel
          </Button>
        </div>
      </div>
    </Sheet>
  );
};
