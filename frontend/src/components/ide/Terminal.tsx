import React, { useEffect, useRef } from 'react';

export default function Terminal({ logs }: { logs: string }) {
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [logs]);

  const colorize = (text: string) => {
    return text.split('\n').map((line, i) => {
      let className = "text-terminal-green";
      if (line.includes("[System]")) className = "text-terminal-white font-semibold";
      if (line.includes("Error") || line.includes("Exception") || line.includes("❌")) className = "text-red-400";
      if (line.includes("[Node]")) className = "text-blue-400";
      if (line.includes("✅")) className = "text-emerald-400";
      
      return (
        <div key={i} className={className}>
          {line}
        </div>
      );
    });
  };

  return (
    <div className="flex flex-col h-full bg-terminal-bg relative">
      <div className="sticky top-0 z-10 px-3 py-1.5 bg-[#1a1a1a] border-b border-[#333] text-[10px] font-semibold tracking-wider text-text-dim uppercase flex justify-between items-center shrink-0">
        <span>Terminal Output</span>
        <div className="flex gap-1.5">
          <div className="w-2.5 h-2.5 rounded-full bg-red-500/80"></div>
          <div className="w-2.5 h-2.5 rounded-full bg-yellow-500/80"></div>
          <div className="w-2.5 h-2.5 rounded-full bg-green-500/80"></div>
        </div>
      </div>
      <div 
        ref={scrollRef}
        className="flex-1 overflow-y-auto p-3 font-mono text-xs leading-relaxed shadow-inner pb-8"
      >
        {colorize(logs)}
      </div>
    </div>
  );
}
