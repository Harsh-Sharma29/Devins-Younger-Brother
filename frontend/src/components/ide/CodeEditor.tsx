import React from 'react';
import Editor from '@monaco-editor/react';

interface CodeEditorProps {
  code: string;
  activeFile: string;
  files: string[];
  onSelectFile: (file: string) => void;
  onChange: (value: string | undefined) => void;
  readOnly?: boolean;
}

export default function CodeEditor({ code, activeFile, files, onSelectFile, onChange, readOnly = false }: CodeEditorProps) {
  return (
    <div className="flex flex-col h-full w-full bg-[#1e1e1e]">
      <div className="flex items-center overflow-x-auto bg-bg-panel border-b border-border-subtle shrink-0">
        {files.length === 0 && (
          <div className="px-4 py-2 text-xs font-mono text-text-dim">No open files</div>
        )}
        {files.map(file => (
          <button
            key={file}
            onClick={() => onSelectFile(file)}
            className={`px-4 py-2 text-xs font-mono border-b-2 transition-colors whitespace-nowrap ${
              activeFile === file 
                ? 'border-accent-cyan text-accent-cyan bg-bg-elevated' 
                : 'border-transparent text-text-muted hover:text-text-primary hover:bg-bg-elevated'
            }`}
          >
            {file}
          </button>
        ))}
      </div>
      
      <div className="flex-1 min-h-0 w-full relative">
        {files.length > 0 ? (
          <Editor
            height="100%"
            width="100%"
            language="python"
            theme="vs-dark"
            value={code}
            path={activeFile}
            onChange={onChange}
            options={{
              minimap: { enabled: false },
              fontSize: 13,
              fontFamily: 'var(--font-jetbrains-mono), monospace',
              readOnly: readOnly,
              wordWrap: 'on',
              padding: { top: 16 },
              scrollBeyondLastLine: false,
              automaticLayout: true,
            }}
            loading={<div className="flex h-full items-center justify-center text-text-dim text-sm font-mono">Loading Monaco Editor...</div>}
          />
        ) : (
          <div className="flex h-full items-center justify-center border border-dashed border-border-subtle m-4 rounded-lg bg-bg-elevated text-text-dim text-sm font-mono">
            // Awaiting generated code from Coder agent...
          </div>
        )}
      </div>
    </div>
  );
}
