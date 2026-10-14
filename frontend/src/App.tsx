import React, { useState, useEffect } from 'react';
import { Navbar } from './components/Navbar';
import { Sidebar, TabType } from './components/Sidebar';
import { OverviewPage } from './pages/OverviewPage';
import { RepositoriesPage } from './pages/RepositoriesPage';
import { AgentRunsPage } from './pages/AgentRunsPage';
import { TicketsPage } from './pages/TicketsPage';
import { CodeChangesPage } from './pages/CodeChangesPage';
import { EvaluationLabPage } from './pages/EvaluationLabPage';
import { FailureTrajectoriesPage } from './pages/FailureTrajectoriesPage';
import { ModelsPage } from './pages/ModelsPage';
import { ObservabilityPage } from './pages/ObservabilityPage';
import { SettingsPage } from './pages/SettingsPage';
import { api } from './services/api';

export const App: React.FC = () => {
  const [currentTab, setCurrentTab] = useState<TabType>('overview');
  const [selectedRunId, setSelectedRunId] = useState<string | null>(null);
  const [autonomyMode, setAutonomyMode] = useState('SUPERVISED');
  const [isDark, setIsDark] = useState(true);

  // System Status
  const [freeRamMb, setFreeRamMb] = useState(1380);
  const [ramWarning, setRamWarning] = useState(false);
  const [ollamaConnected, setOllamaConnected] = useState(false);
  const [groqConnected, setGroqConnected] = useState(false);
  const [pendingApprovalsCount, setPendingApprovalsCount] = useState(0);

  useEffect(() => {
    fetchSystemStatus();
    const interval = setInterval(fetchSystemStatus, 6000);
    return () => clearInterval(interval);
  }, []);

  const fetchSystemStatus = async () => {
    try {
      const status = await api.getSystemStatus();
      if (status.system) {
        setFreeRamMb(status.system.free_ram_mb);
        setRamWarning(status.system.ram_warning);
      }
      setOllamaConnected(status.ollama?.available ?? false);
      setGroqConnected(status.groq?.available ?? false);

      // Check pending runs awaiting approval
      const runs = await api.getRuns();
      const awaiting = runs.filter((r) => r.state === 'AWAITING_APPROVAL').length;
      setPendingApprovalsCount(awaiting);
    } catch (e) {
      // Backend starting or offline
    }
  };

  return (
    <div className={`min-h-screen flex flex-col ${isDark ? 'bg-zinc-950 text-zinc-100' : 'bg-zinc-100 text-zinc-900'}`}>
      {/* Top Navigation */}
      <Navbar
        freeRamMb={freeRamMb}
        ramWarning={ramWarning}
        autonomyMode={autonomyMode}
        setAutonomyMode={setAutonomyMode}
        ollamaConnected={ollamaConnected}
        groqConnected={groqConnected}
        isDark={isDark}
        setIsDark={setIsDark}
      />

      {/* Main Content Area */}
      <div className="flex-1 flex overflow-hidden">
        {/* Sidebar */}
        <Sidebar
          currentTab={currentTab}
          setCurrentTab={setCurrentTab}
          pendingApprovalsCount={pendingApprovalsCount}
        />

        {/* Tab Body */}
        <main className="flex-1 overflow-auto bg-zinc-900/20">
          {currentTab === 'overview' && (
            <OverviewPage
              setCurrentTab={setCurrentTab}
              onSelectRun={(id) => {
                setSelectedRunId(id);
                setCurrentTab('runs');
              }}
            />
          )}
          {currentTab === 'repositories' && <RepositoriesPage />}
          {currentTab === 'runs' && (
            <AgentRunsPage
              selectedRunId={selectedRunId}
              onSelectRun={setSelectedRunId}
              setCurrentTab={setCurrentTab}
            />
          )}
          {currentTab === 'tickets' && (
            <TicketsPage
              onSelectRun={(id) => {
                setSelectedRunId(id);
                setCurrentTab('runs');
              }}
              setCurrentTab={setCurrentTab}
            />
          )}
          {currentTab === 'changes' && <CodeChangesPage selectedRunId={selectedRunId} />}
          {currentTab === 'evaluation' && <EvaluationLabPage selectedRunId={selectedRunId} />}
          {currentTab === 'failures' && <FailureTrajectoriesPage />}
          {currentTab === 'models' && <ModelsPage />}
          {currentTab === 'observability' && <ObservabilityPage />}
          {currentTab === 'settings' && <SettingsPage />}
        </main>
      </div>
    </div>
  );
};

export default App;
