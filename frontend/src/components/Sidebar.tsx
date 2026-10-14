import React from 'react';
import {
  LayoutDashboard,
  GitBranch,
  PlayCircle,
  Ticket,
  FileDiff,
  CheckCircle2,
  History,
  Cpu,
  Activity,
  Settings
} from 'lucide-react';

export type TabType =
  | 'overview'
  | 'repositories'
  | 'runs'
  | 'tickets'
  | 'changes'
  | 'evaluation'
  | 'failures'
  | 'models'
  | 'observability'
  | 'settings';

interface SidebarProps {
  currentTab: TabType;
  setCurrentTab: (tab: TabType) => void;
  pendingApprovalsCount: number;
}

export const Sidebar: React.FC<SidebarProps> = ({
  currentTab,
  setCurrentTab,
  pendingApprovalsCount,
}) => {
  const navItems: Array<{ id: TabType; label: string; icon: React.ReactNode; badge?: number }> = [
    { id: 'overview', label: 'Overview', icon: <LayoutDashboard className="w-4 h-4" /> },
    { id: 'repositories', label: 'Repositories', icon: <GitBranch className="w-4 h-4" /> },
    { id: 'runs', label: 'Agent Runs', icon: <PlayCircle className="w-4 h-4" /> },
    { id: 'tickets', label: 'Tickets', icon: <Ticket className="w-4 h-4" /> },
    {
      id: 'changes',
      label: 'Code Changes',
      icon: <FileDiff className="w-4 h-4" />,
      badge: pendingApprovalsCount > 0 ? pendingApprovalsCount : undefined,
    },
    { id: 'evaluation', label: 'Evaluation Lab', icon: <CheckCircle2 className="w-4 h-4" /> },
    { id: 'failures', label: 'Failure Memory', icon: <History className="w-4 h-4" /> },
    { id: 'models', label: 'Models & Inference', icon: <Cpu className="w-4 h-4" /> },
    { id: 'observability', label: 'Observability', icon: <Activity className="w-4 h-4" /> },
    { id: 'settings', label: 'Settings', icon: <Settings className="w-4 h-4" /> },
  ];

  return (
    <aside className="w-60 border-r border-zinc-800 bg-zinc-950 flex flex-col justify-between shrink-0 select-none">
      <div className="p-3 space-y-1">
        <div className="px-3 py-2 text-[10px] font-mono font-bold tracking-wider text-zinc-500 uppercase">
          Navigation
        </div>
        {navItems.map((item) => {
          const isActive = currentTab === item.id;
          return (
            <button
              key={item.id}
              onClick={() => setCurrentTab(item.id)}
              className={`w-full flex items-center justify-between px-3 py-2 rounded text-xs font-medium transition ${
                isActive
                  ? 'bg-zinc-800/90 text-zinc-100 border border-zinc-700 shadow-sm'
                  : 'text-zinc-400 hover:text-zinc-200 hover:bg-zinc-900 border border-transparent'
              }`}
            >
              <div className="flex items-center gap-2.5">
                <span className={isActive ? 'text-zinc-100' : 'text-zinc-400'}>{item.icon}</span>
                <span>{item.label}</span>
              </div>
              {item.badge !== undefined && (
                <span className="px-1.5 py-0.5 text-[10px] font-mono rounded-full bg-amber-500/20 text-amber-400 border border-amber-500/30">
                  {item.badge}
                </span>
              )}
            </button>
          );
        })}
      </div>

      <div className="p-4 border-t border-zinc-800 text-xs font-mono text-zinc-500">
        <div className="flex justify-between items-center mb-1 text-[11px]">
          <span>RAM LIMIT</span>
          <span className="text-zinc-400 font-bold">8.0 GB</span>
        </div>
        <div className="w-full h-1 bg-zinc-800 rounded-full overflow-hidden">
          <div className="h-full bg-zinc-400" style={{ width: '80%' }}></div>
        </div>
        <p className="text-[10px] text-zinc-600 mt-2">Single Local Model Lock Active</p>
      </div>
    </aside>
  );
};
