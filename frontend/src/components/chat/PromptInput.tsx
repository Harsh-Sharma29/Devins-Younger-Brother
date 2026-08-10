import React, { useState } from 'react';
import { Send, Loader2 } from 'lucide-react';

interface PromptInputProps {
  onSubmit: (prompt: string) => void;
  isExecuting: boolean;
}

export default function PromptInput({ onSubmit, isExecuting }: PromptInputProps) {
  const [prompt, setPrompt] = useState('');

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (prompt.trim() && !isExecuting) {
      onSubmit(prompt);
      setPrompt('');
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit(e);
    }
  };

  return (
    <form onSubmit={handleSubmit} className="relative flex items-end gap-2 w-full">
      <textarea
        value={prompt}
        onChange={(e) => setPrompt(e.target.value)}
        onKeyDown={handleKeyDown}
        placeholder="Describe the software you want to build..."
        className="w-full bg-bg-elevated border border-border-subtle focus:border-accent-cyan focus:ring-1 focus:ring-accent-cyan rounded-xl px-4 py-3 min-h-[60px] max-h-[200px] resize-y text-sm font-mono text-text-primary placeholder:text-text-dim outline-none transition-all shadow-inner"
        disabled={isExecuting}
      />
      <button
        type="submit"
        disabled={!prompt.trim() || isExecuting}
        className="shrink-0 h-[60px] px-6 rounded-xl font-semibold flex items-center justify-center gap-2 border border-accent-cyan bg-gradient-to-br from-sky-800 via-blue-700 to-indigo-900 text-white shadow-[0_0_15px_rgba(0,180,216,0.3)] hover:shadow-[0_0_25px_rgba(0,180,216,0.5)] transition-all hover:-translate-y-0.5 disabled:opacity-50 disabled:cursor-not-allowed disabled:hover:translate-y-0 disabled:hover:shadow-none"
      >
        {isExecuting ? (
          <>
            <Loader2 className="w-5 h-5 animate-spin" />
            <span>Executing</span>
          </>
        ) : (
          <>
            <Send className="w-5 h-5" />
            <span>Launch</span>
          </>
        )}
      </button>
    </form>
  );
}
