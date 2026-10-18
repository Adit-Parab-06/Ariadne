import React, { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { ChevronDown, Code, Clock, Copy, Check } from 'lucide-react';
import { ToolCallItem } from '../api/types';
import { Chip } from './Chip';

export interface ToolRowProps {
  toolCall: ToolCallItem;
  className?: string;
}

export const ToolRow: React.FC<ToolRowProps> = ({ toolCall, className = '' }) => {
  const [isOpen, setIsOpen] = useState(false);
  const [copied, setCopied] = useState(false);

  const hasCypher = toolCall.cypher && toolCall.cypher.length > 0;
  const nodes = toolCall.evidence?.nodes || [];

  const handleCopyCypher = (e: React.MouseEvent) => {
    e.stopPropagation();
    if (!toolCall.cypher) return;
    navigator.clipboard.writeText(toolCall.cypher.join('\n\n'));
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className={`border apple-border rounded-xl bg-bg/50 overflow-hidden text-xs transition-colors hover:border-blue/20 ${className}`}>
      {/* Header bar */}
      <div className="flex items-center justify-between px-3 py-2.5">
        <div className="flex items-center space-x-2 overflow-hidden flex-1">
          <span className="font-mono font-semibold text-blue bg-blue/10 px-1.5 py-0.5 rounded">
            {toolCall.tool}
          </span>
          <span className="text-label-2 truncate">{toolCall.summary || 'Executing...'}</span>
        </div>

        <div className="flex items-center space-x-2 flex-shrink-0 ml-2">
          {toolCall.ms !== undefined && (
            <span className="inline-flex items-center text-[10px] text-label-3 font-mono">
              <Clock className="w-3 h-3 mr-0.5" />
              {toolCall.ms}ms
            </span>
          )}

          {hasCypher && (
            <button
              type="button"
              onClick={() => setIsOpen(!isOpen)}
              className="inline-flex items-center text-[11px] font-medium text-label-2 hover:text-blue transition-colors px-1.5 py-0.5 rounded hover:bg-fill focus:outline-none"
            >
              <Code className="w-3 h-3 mr-1" />
              <span>{isOpen ? 'Hide query' : 'Show query'}</span>
              <ChevronDown
                className={`w-3 h-3 ml-0.5 transform transition-transform ${
                  isOpen ? 'rotate-180' : ''
                }`}
              />
            </button>
          )}
        </div>
      </div>

      {/* Expandable Cypher & Evidence disclosure */}
      <AnimatePresence>
        {isOpen && hasCypher && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ type: 'spring', stiffness: 450, damping: 30 }}
            className="border-t apple-border bg-fill/20 px-3 py-2.5 space-y-2 overflow-hidden"
          >
            <div>
              <div className="flex items-center justify-between mb-1">
                <span className="text-[10px] font-semibold uppercase tracking-wider text-label-3">
                  Cypher Query
                </span>
                <button
                  type="button"
                  onClick={handleCopyCypher}
                  className="inline-flex items-center space-x-1 text-[10px] text-label-3 hover:text-blue transition-colors px-1.5 py-0.5 rounded hover:bg-fill/50"
                  title="Copy Cypher query to clipboard"
                >
                  {copied ? (
                    <>
                      <Check className="w-3 h-3 text-green" />
                      <span className="text-green font-medium">Copied</span>
                    </>
                  ) : (
                    <>
                      <Copy className="w-3 h-3" />
                      <span>Copy Cypher</span>
                    </>
                  )}
                </button>
              </div>
              {toolCall.cypher!.map((q, idx) => (
                <pre
                  key={idx}
                  className="font-mono text-[11px] text-label-2 bg-bg/80 p-2.5 rounded-lg border apple-border overflow-x-auto whitespace-pre-wrap select-text leading-relaxed"
                >
                  {q}
                </pre>
              ))}
            </div>

            {nodes.length > 0 && (
              <div>
                <span className="text-[10px] font-semibold uppercase tracking-wider text-label-3 block mb-1">
                  Discovered Evidence ({nodes.length})
                </span>
                <div className="flex flex-wrap gap-1.5">
                  {nodes.map((n) => (
                    <Chip key={n.id} label={n.id} type={n.label} />
                  ))}
                </div>
              </div>
            )}
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
};
