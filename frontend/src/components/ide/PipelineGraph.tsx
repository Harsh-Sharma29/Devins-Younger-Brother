import React from 'react';
import { motion } from 'framer-motion';
import { ArrowRight, Compass, ClipboardList, Code2, ShieldCheck, Box, Bug } from 'lucide-react';
import { clsx, type ClassValue } from 'clsx';
import { twMerge } from 'tailwind-merge';

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

const NODES = [
  { id: 'Router', icon: Compass, label: 'Router' },
  { id: 'Planner', icon: ClipboardList, label: 'Planner' },
  { id: 'Coder', icon: Code2, label: 'Coder' },
  { id: 'Validator', icon: ShieldCheck, label: 'Validator' },
  { id: 'Sandbox', icon: Box, label: 'Sandbox' },
  { id: 'Debugger', icon: Bug, label: 'Debugger' },
];

export default function PipelineGraph({ activeNode }: { activeNode: string | null }) {
  return (
    <div className="flex items-center justify-between bg-bg-panel border border-border-subtle rounded-xl p-3 shadow-lg shrink-0 overflow-x-auto">
      {NODES.map((node, i) => {
        const isActive = activeNode === node.id;
        const Icon = node.icon;
        return (
          <React.Fragment key={node.id}>
            <div className="relative flex-1 min-w-[100px]">
              <motion.div
                animate={isActive ? { scale: 1.05 } : { scale: 1 }}
                className={cn(
                  "flex items-center justify-center gap-2 py-2 px-1 rounded-lg border font-mono text-xs font-medium transition-colors z-10 relative",
                  isActive 
                    ? "bg-gradient-to-br from-sky-600 to-blue-800 border-accent-cyan text-white shadow-[0_0_15px_rgba(0,180,216,0.5)]" 
                    : "bg-bg-elevated border-border-subtle text-text-muted opacity-60"
                )}
              >
                <Icon className={cn("w-4 h-4 shrink-0", isActive && "text-cyan-200")} />
                <span className="hidden sm:inline">{node.label}</span>
              </motion.div>
            </div>
            {i < NODES.length - 1 && (
              <div className="px-2 text-text-dim shrink-0">
                <ArrowRight className="w-4 h-4" />
              </div>
            )}
          </React.Fragment>
        );
      })}
    </div>
  );
}
