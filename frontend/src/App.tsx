import React, { useEffect } from 'react';
import { Sidebar } from './components/Sidebar';
import { MainFeed } from './components/MainFeed';
import { Inspector } from './components/Inspector';
import { ApprovalSheet } from './components/ApprovalSheet';
import { ResolveSheet } from './components/ResolveSheet';
import { useAppStore } from './store';
import { api } from './api/client';

export const App: React.FC = () => {
  const {
    tenant,
    activeRunId,
    setRuns,
    isSidebarOpen,
    isInspectorOpen,
    toggleSidebar,
    toggleInspector,
  } = useAppStore();

  // Load runs on mount or tenant switch
  useEffect(() => {
    (async () => {
      try {
        const runList = await api.listRuns(tenant);
        setRuns(runList || []);
      } catch (e) {
        console.warn('Failed to fetch runs on mount', e);
      }
    })();
  }, [tenant, setRuns]);

  // Load clean baseline architecture topology when idle
  useEffect(() => {
    if (!activeRunId) {
      (async () => {
        try {
          const overview = await api.getGraphOverview(tenant);
          if (overview?.nodes?.length) {
            // Filter baseline view to core architecture so the canvas starts clean, readable, and structured
            const coreNodes = overview.nodes.filter(
              (n) => n.label === 'Service' || n.label === 'Incident' || n.label === 'Customer'
            );
            const coreIds = new Set(coreNodes.map((n) => n.id));
            const coreEdges = overview.edges.filter(
              (e) => coreIds.has(e.src) && coreIds.has(e.dst)
            );
            useAppStore.setState({
              evidence: {
                nodes: coreNodes.length > 0 ? coreNodes : overview.nodes.slice(0, 16),
                edges: coreEdges.length > 0 ? coreEdges : overview.edges.slice(0, 24),
              },
            });
          }
        } catch (e) {
          console.warn('Failed to load initial graph overview', e);
        }
      })();
    }
  }, [tenant, activeRunId]);

  // Global keyboard shortcuts for macOS-like window controls (Apple HIG Agency & Flexibility)
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      // Cmd+[ or Ctrl+[ -> Toggle Sidebar
      if ((e.metaKey || e.ctrlKey) && e.key === '[') {
        e.preventDefault();
        toggleSidebar();
      }
      // Cmd+] or Ctrl+] -> Toggle Inspector
      if ((e.metaKey || e.ctrlKey) && e.key === ']') {
        e.preventDefault();
        toggleInspector();
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [toggleSidebar, toggleInspector]);

  return (
    <div className="flex h-screen w-screen overflow-hidden bg-bg font-sans antialiased text-label">
      {/* Sidebar (260px) */}
      {isSidebarOpen && <Sidebar />}

      {/* Main Mission Feed */}
      <MainFeed />

      {/* Inspector Panel (420px) */}
      {isInspectorOpen && <Inspector />}

      {/* Action Approval Sheet */}
      <ApprovalSheet />

      {/* Incident Resolution & Memory Consolidation Sheet */}
      <ResolveSheet />
    </div>
  );
};

export default App;
