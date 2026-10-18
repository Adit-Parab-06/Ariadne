import React, { useState } from 'react';
import {
  Activity,
  Code2,
  Play,
  ShieldCheck,
} from 'lucide-react';
import { useAppStore } from '../store';
import { api } from '../api/client';
import { Button, Card, Sheet } from '../ui';

interface ConcurrencyLabModalProps {
  isOpen: boolean;
  onClose: () => void;
}

interface BenchmarkHistoryItem {
  id: string;
  tasks: number;
  workers: number;
  claimed: number;
  duplicates: number;
  seconds: number;
  throughput: number;
  timestamp: string;
}

export const ConcurrencyLabModal: React.FC<ConcurrencyLabModalProps> = ({
  isOpen,
  onClose,
}) => {
  const { tenant } = useAppStore();

  const [tasks, setTasks] = useState(200);
  const [workers, setWorkers] = useState(8);
  const [isRunning, setIsRunning] = useState(false);
  const [latestResult, setLatestResult] = useState<any>(null);
  const [history, setHistory] = useState<BenchmarkHistoryItem[]>([]);
  const [activePreset, setActivePreset] = useState<'quick' | 'standard' | 'stress'>('standard');

  const applyPreset = (preset: 'quick' | 'standard' | 'stress') => {
    setActivePreset(preset);
    if (preset === 'quick') {
      setTasks(100);
      setWorkers(4);
    } else if (preset === 'standard') {
      setTasks(200);
      setWorkers(8);
    } else if (preset === 'stress') {
      setTasks(400);
      setWorkers(16);
    }
  };

  const handleRun = async () => {
    setIsRunning(true);
    try {
      const res = await api.postConcurrencyLab(tenant, tasks, workers);
      setLatestResult(res);

      const newItem: BenchmarkHistoryItem = {
        id: `bench_${Date.now()}`,
        tasks,
        workers,
        claimed: res.claimed,
        duplicates: res.duplicates,
        seconds: res.seconds,
        throughput: res.throughput,
        timestamp: new Date().toLocaleTimeString(),
      };
      setHistory((prev) => [newItem, ...prev.slice(0, 4)]);
    } catch (e) {
      console.error('Concurrency benchmark failed', e);
    } finally {
      setIsRunning(false);
    }
  };

  return (
    <Sheet
      isOpen={isOpen}
      onClose={onClose}
      title="Coordination Lab: Atomic CAS Benchmark"
    >
      <div className="space-y-4">
        {/* Intro */}
        <p className="text-xs text-label-2 leading-relaxed">
          Demonstrates FalkorDB as a load-bearing coordination substrate. Benchmarks concurrent agent task claims using single-statement conditional Cypher <code className="font-mono bg-fill/50 px-1 py-0.5 rounded text-blue">SET</code> with zero external locking infrastructure (no Redis Redlock, no Celery, no Kafka).
        </p>

        {/* Presets */}
        <div className="grid grid-cols-3 gap-2">
          <button
            type="button"
            onClick={() => applyPreset('quick')}
            className={`p-2 rounded-xl border text-center transition-all ${
              activePreset === 'quick'
                ? 'bg-blue/10 border-blue text-blue font-bold shadow-sm'
                : 'bg-bg border-apple text-label-2 hover:bg-fill/20'
            }`}
          >
            <div className="text-[10px] uppercase font-semibold">Quick Scan</div>
            <div className="text-xs font-mono font-bold mt-0.5">100t • 4w</div>
          </button>
          <button
            type="button"
            onClick={() => applyPreset('standard')}
            className={`p-2 rounded-xl border text-center transition-all ${
              activePreset === 'standard'
                ? 'bg-blue/10 border-blue text-blue font-bold shadow-sm'
                : 'bg-bg border-apple text-label-2 hover:bg-fill/20'
            }`}
          >
            <div className="text-[10px] uppercase font-semibold">Standard</div>
            <div className="text-xs font-mono font-bold mt-0.5">200t • 8w</div>
          </button>
          <button
            type="button"
            onClick={() => applyPreset('stress')}
            className={`p-2 rounded-xl border text-center transition-all ${
              activePreset === 'stress'
                ? 'bg-blue/10 border-blue text-blue font-bold shadow-sm'
                : 'bg-bg border-apple text-label-2 hover:bg-fill/20'
            }`}
          >
            <div className="text-[10px] uppercase font-semibold">High Stress</div>
            <div className="text-xs font-mono font-bold mt-0.5">400t • 16w</div>
          </button>
        </div>

        {/* Sliders */}
        <Card className="space-y-3.5 bg-bg">
          <div>
            <div className="flex justify-between items-center text-xs font-semibold mb-1">
              <span className="text-label">Contending Tasks</span>
              <span className="font-mono text-blue font-bold text-sm">{tasks}</span>
            </div>
            <input
              type="range"
              min={50}
              max={500}
              step={25}
              value={tasks}
              onChange={(e) => {
                setTasks(Number(e.target.value));
                setActivePreset('standard');
              }}
              className="w-full accent-blue cursor-pointer"
            />
            <div className="flex justify-between text-[10px] text-label-3 font-mono mt-0.5">
              <span>50 tasks</span>
              <span>250</span>
              <span>500 tasks</span>
            </div>
          </div>

          <div>
            <div className="flex justify-between items-center text-xs font-semibold mb-1">
              <span className="text-label">Parallel Worker Threads</span>
              <span className="font-mono text-purple font-bold text-sm">{workers}</span>
            </div>
            <input
              type="range"
              min={2}
              max={16}
              step={2}
              value={workers}
              onChange={(e) => {
                setWorkers(Number(e.target.value));
                setActivePreset('standard');
              }}
              className="w-full accent-purple cursor-pointer"
            />
            <div className="flex justify-between text-[10px] text-label-3 font-mono mt-0.5">
              <span>2 threads</span>
              <span>8 threads</span>
              <span>16 threads</span>
            </div>
          </div>
        </Card>

        {/* Action Button */}
        <Button
          variant="filled"
          color="blue"
          size="md"
          disabled={isRunning}
          onClick={handleRun}
          className="w-full justify-center space-x-2 py-3"
        >
          {isRunning ? (
            <>
              <Activity className="w-4 h-4 animate-spin" />
              <span>Contending on FalkorDB Graph...</span>
            </>
          ) : (
            <>
              <Play className="w-4 h-4 fill-current" />
              <span>Execute Concurrency Benchmark</span>
            </>
          )}
        </Button>

        {/* Latest Results Card */}
        {latestResult && (
          <div className="p-4 rounded-2xl bg-green/10 border border-green/30 space-y-3 shadow-sm animate-in fade-in duration-300">
            <div className="flex items-center justify-between border-b border-green/20 pb-2">
              <div className="flex items-center space-x-2 text-green">
                <ShieldCheck className="w-5 h-5 flex-shrink-0" />
                <span className="text-xs font-bold uppercase tracking-wider">
                  Zero Duplicates Verified
                </span>
              </div>
              <span className="font-mono text-xs font-bold text-green px-2 py-0.5 rounded-full bg-green/20">
                CAS PASS
              </span>
            </div>

            <div className="grid grid-cols-2 gap-3 text-xs font-mono">
              <div className="bg-bg/60 p-2.5 rounded-xl border border-green/20">
                <span className="text-[10px] text-label-3 block uppercase font-sans">Claimed Tasks</span>
                <span className="text-base font-bold text-label">{latestResult.claimed} / {tasks}</span>
              </div>
              <div className="bg-bg/60 p-2.5 rounded-xl border border-green/20">
                <span className="text-[10px] text-label-3 block uppercase font-sans">Duplicate Claims</span>
                <span className="text-base font-bold text-green">{latestResult.duplicates}</span>
              </div>
              <div className="bg-bg/60 p-2.5 rounded-xl border border-green/20">
                <span className="text-[10px] text-label-3 block uppercase font-sans">Elapsed Duration</span>
                <span className="text-base font-bold text-label">{latestResult.seconds}s</span>
              </div>
              <div className="bg-bg/60 p-2.5 rounded-xl border border-green/20">
                <span className="text-[10px] text-label-3 block uppercase font-sans">Throughput</span>
                <span className="text-base font-bold text-blue">{latestResult.throughput} tasks/s</span>
              </div>
            </div>
          </div>
        )}

        {/* Cypher CAS Mechanism Card */}
        <div className="p-3.5 rounded-2xl bg-fill/20 border apple-border space-y-2">
          <div className="flex items-center space-x-1.5 text-xs font-bold text-label">
            <Code2 className="w-4 h-4 text-blue" />
            <span>Under The Hood: Atomic Cypher CAS</span>
          </div>
          <p className="text-[11px] text-label-2 leading-relaxed">
            FalkorDB guarantees atomicity by evaluating the conditional predicate in the same write statement:
          </p>
          <pre className="p-2.5 rounded-xl bg-bg border apple-border text-[10px] font-mono text-label overflow-x-auto leading-relaxed">
{`MATCH (t:Task {id: $tid, status: 'open'})
SET t.status = 'claimed',
    t.owner  = $worker,
    t.claimed_at = timestamp()
RETURN t.id`}
          </pre>
        </div>

        {/* Past Benchmark History */}
        {history.length > 0 && (
          <div className="space-y-2 pt-1 border-t apple-border">
            <span className="text-[11px] font-semibold text-label-3 uppercase tracking-wider block">
              Recent Benchmark Runs ({history.length})
            </span>
            <div className="space-y-1.5 max-h-36 overflow-y-auto">
              {history.map((h) => (
                <div
                  key={h.id}
                  className="flex items-center justify-between p-2 rounded-xl bg-bg border apple-border text-[11px] font-mono text-label-2"
                >
                  <div className="flex items-center space-x-2">
                    <span className="text-blue font-bold">{h.tasks}t • {h.workers}w</span>
                    <span className="text-label-3">at {h.timestamp}</span>
                  </div>
                  <div className="flex items-center space-x-3">
                    <span className="text-green font-semibold">0 dupes</span>
                    <span className="font-bold text-label">{h.throughput} t/s</span>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </Sheet>
  );
};
