import React from 'react';
import { Activity, FileCode2, Cpu, HardDrive, Timer, Hash } from 'lucide-react';

interface SidebarProps {
  telemetry: { cpu: number; ram: number; tokens: number; latency: number };
  files: string[];
  activeFile: string;
  onSelectFile: (file: string) => void;
}

export default function Sidebar({ telemetry, files, activeFile, onSelectFile }: SidebarProps) {
  return (
    <aside className="w-64 bg-gradient-to-b from-[#0d0d14] to-bg-deep border-r border-border-subtle flex flex-col h-full shrink-0">
      <div className="p-4 border-b border-border-subtle flex items-center gap-2">
        <Activity className="w-5 h-5 text-accent-cyan" />
        <span className="text-sm font-semibold tracking-wider text-text-muted uppercase">System Status</span>
      </div>
      
      <div className="p-3 flex flex-col gap-2 border-b border-border-subtle">
        <TelemetryCard icon={<Hash className="w-4 h-4" />} label="Tokens Generated" value={telemetry.tokens.toLocaleString()} />
        <TelemetryCard icon={<Timer className="w-4 h-4" />} label="Latency Delta" value={`${telemetry.latency} ms`} />
        <TelemetryCard icon={<Cpu className="w-4 h-4" />} label="CPU Usage" value={`${telemetry.cpu.toFixed(1)}%`} />
        <TelemetryCard icon={<HardDrive className="w-4 h-4" />} label="RAM Usage" value={`${telemetry.ram.toFixed(1)}%`} />
      </div>

      <div className="p-4 border-b border-border-subtle flex items-center gap-2">
        <FileCode2 className="w-5 h-5 text-accent-cyan" />
        <span className="text-sm font-semibold tracking-wider text-text-muted uppercase">Workspace</span>
      </div>

      <div className="flex-1 overflow-y-auto p-2">
        {files.length === 0 ? (
          <div className="text-xs text-text-dim text-center py-4 font-mono">// No files yet</div>
        ) : (
          files.map(file => (
            <button
              key={file}
              onClick={() => onSelectFile(file)}
              className={`w-full text-left px-3 py-2 rounded-md text-sm font-mono transition-colors ${
                activeFile === file 
                  ? 'bg-bg-elevated text-accent-cyan font-medium' 
                  : 'text-text-muted hover:bg-bg-panel hover:text-text-primary'
              }`}
            >
              {file}
            </button>
          ))
        )}
      </div>
    </aside>
  );
}

function TelemetryCard({ icon, label, value }: { icon: React.ReactNode, label: string, value: string }) {
  return (
    <div className="bg-bg-elevated border border-border-subtle rounded-md p-2 flex items-center justify-between shadow-sm">
      <div className="flex flex-col">
        <span className="text-[10px] uppercase tracking-wider text-text-dim mb-0.5 font-semibold">{label}</span>
        <span className="text-xs font-mono font-semibold text-accent-cyan">{value}</span>
      </div>
      <div className="text-text-dim/50">{icon}</div>
    </div>
  );
}
