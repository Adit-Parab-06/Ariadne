import React, { useState } from 'react';
import { useAppStore } from '../store';
import { api } from '../api/client';
import { Button, Chip, Sheet, Toast } from '../ui';
import { CheckCircle2, Sparkles } from 'lucide-react';

export const ResolveSheet: React.FC = () => {
  const {
    tenant,
    activeRunId,
    isResolveSheetOpen,
    setResolveSheetOpen,
    incrementMemoryVersion,
  } = useAppStore();

  const [note, setNote] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [writtenNodes, setWrittenNodes] = useState<Array<{ id: string; label: string; name: string }>>([]);
  const [showToast, setShowToast] = useState(false);

  const handleResolve = async () => {
    if (!activeRunId || !note.trim() || isSubmitting) return;

    setIsSubmitting(true);
    try {
      const res = await api.resolveRun(tenant, activeRunId, note);
      setWrittenNodes(res.memory_written || []);
      incrementMemoryVersion();
      setShowToast(true);
      setTimeout(() => setShowToast(false), 4000);
    } catch (e) {
      console.error('Failed to resolve run', e);
    } finally {
      setIsSubmitting(false);
    }
  };

  // Keyboard shortcut: Cmd+Enter to save to memory
  React.useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === 'Enter' && isResolveSheetOpen) {
        e.preventDefault();
        handleResolve();
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isResolveSheetOpen, activeRunId, note, isSubmitting]);

  return (
    <>
      <Sheet
        isOpen={isResolveSheetOpen}
        onClose={() => setResolveSheetOpen(false)}
        title="Resolve Incident & Update Memory"
      >
        <div className="space-y-4">
          <div>
            <label className="text-xs font-semibold text-label block mb-1">
              Resolution Note
            </label>
            <textarea
              rows={3}
              value={note}
              onChange={(e) => setNote(e.target.value)}
              placeholder="e.g. Root cause was ledger-db connection pool exhaustion. Raised max_client_conn to 400 and verified latency returned to baseline."
              className="w-full rounded-xl bg-bg border apple-border p-3 text-xs text-label focus:outline-none focus:ring-2 focus:ring-blue resize-none"
            />
          </div>

          <Button
            variant="filled"
            color="green"
            size="md"
            disabled={!note.trim() || isSubmitting || writtenNodes.length > 0}
            onClick={handleResolve}
            className="w-full justify-center space-x-1.5"
          >
            <Sparkles className="w-4 h-4" />
            <span>{isSubmitting ? 'Consolidating Memory...' : 'Save to Memory'}</span>
          </Button>

          {writtenNodes.length > 0 && (
            <div className="p-4 rounded-xl bg-green/10 border border-green/30 space-y-2 mt-4">
              <div className="flex items-center space-x-1.5 text-green text-xs font-bold">
                <CheckCircle2 className="w-4 h-4" />
                <span>Memory Successfully Consolidated</span>
              </div>
              <div className="flex flex-wrap gap-1.5">
                {writtenNodes.map((n) => (
                  <div key={n.id} className="flex items-center space-x-1">
                    <Chip label={n.id} type={n.label} />
                    <span className="text-[10px] bg-green text-white font-bold px-1.5 py-0.2 rounded-full uppercase">
                      Learned
                    </span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      </Sheet>

      <Toast
        message="Memory updated with new episode and facts"
        type="success"
        isVisible={showToast}
      />
    </>
  );
};
