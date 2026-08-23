"use client";

import React, { useState, useEffect } from "react";
import Sidebar from "@/components/layout/Sidebar";
import PipelineGraph from "@/components/ide/PipelineGraph";
import CodeEditor from "@/components/ide/CodeEditor";
import Terminal from "@/components/ide/Terminal";
import PromptInput from "@/components/chat/PromptInput";

// Use environment variable if available, fallback to relative path for Nginx
const API_URL = process.env.NEXT_PUBLIC_API_URL || "";

export default function Home() {
  const [activeFile, setActiveFile] = useState("main.py");
  const [workspaceFiles, setWorkspaceFiles] = useState<Record<string, string>>({});
  const [consoleLogs, setConsoleLogs] = useState("[System] AutoForge Initialized.\nWaiting for your instructions...");
  const [isExecuting, setIsExecuting] = useState(false);
  const [telemetry, setTelemetry] = useState({ cpu: 0, ram: 0, tokens: 0, latency: 0 });
  const [activeNode, setActiveNode] = useState<string | null>(null);
  const [threadId, setThreadId] = useState("");

  useEffect(() => {
    // 1. Create a session to get a thread_id
    fetch(`${API_URL}/api/v1/session/new`, { method: 'POST' })
      .then(res => res.json())
      .then(data => {
        if(data.thread_id) setThreadId(data.thread_id);
      })
      .catch(err => {
        setConsoleLogs(prev => prev + `\n[System Warning] Could not connect to API backend at ${API_URL}`);
      });

    // 2. Poll telemetry
    const interval = setInterval(() => {
      fetch(`${API_URL}/api/v1/health`)
        .then(res => res.json())
        .then(data => {
          if (data.telemetry) {
            setTelemetry({
              cpu: data.telemetry.cpu_pct || 0,
              ram: data.telemetry.ram_pct || 0,
              tokens: data.telemetry.total_tokens || 0,
              latency: data.telemetry.latency_ms || 0
            });
          }
        })
        .catch(() => {});
    }, 5000);
    
    return () => clearInterval(interval);
  }, []);

  // WebSocket for Live Terminal Output
  useEffect(() => {
    if (!threadId) return;
    
    let ws: WebSocket;
    try {
      const wsUrl = `${API_URL.replace('http', 'ws')}/api/v1/ws/terminal/${threadId}`;
      ws = new WebSocket(wsUrl);
      
      ws.onmessage = (event) => {
        setConsoleLogs(prev => prev + event.data);
      };
    } catch (err) {
      console.warn("WebSocket connection failed", err);
    }
    
    return () => {
      if (ws) ws.close();
    };
  }, [threadId]);

  const executePrompt = async (prompt: string) => {
    if (!prompt.trim() || isExecuting) return;
    setIsExecuting(true);
    setConsoleLogs(prev => prev + `\n\n[User] ${prompt}\n[System] Starting LangGraph pipeline...`);
    setActiveNode("Router");

    try {
      const response = await fetch(`${API_URL}/api/v1/execute`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          prompt,
          thread_id: threadId || crypto.randomUUID(),
          recursion_limit: 50
        })
      });

      if (!response.body) throw new Error("No response body");
      
      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      
      let pendingEvent = "";
      let buffer = "";
      
      while (true) {
        const { value, done } = await reader.read();
        if (done) break;
        
        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        
        // Keep the last incomplete line in the buffer
        buffer = lines.pop() || "";
        
        for (const line of lines) {
          if (line.trim() === '') continue; // skip empty lines

          if (line.startsWith('event: ')) {
            pendingEvent = line.substring(7).trim();
          } else if (line.startsWith('data: ')) {
            const dataStr = line.substring(6).trim();
            if (!dataStr) continue;
            
            try {
              const payload = JSON.parse(dataStr);
              
              if (pendingEvent === 'node_update') {
                if (payload.new_logs && payload.new_logs.length > 0) {
                  setConsoleLogs(prev => prev + '\n' + payload.new_logs.join('\n'));
                }
                // WebSocket now handles live terminal output, skipping terminal_output_delta to prevent duplicates
                if (payload.node_name) {
                  const nodeMap: Record<string, string> = {
                    "router_node": "Router",
                    "planner_agent": "Planner",
                    "coder_model": "Coder",
                    "coder_tools": "Coder",
                    "coder_agent": "Coder",
                    "validator_node": "Validator",
                    "terminal_agent": "Sandbox",
                    "debugger_agent": "Debugger"
                  };
                  setActiveNode(nodeMap[payload.node_name] || null);
                }
                if (payload.workspace_files) {
                  setWorkspaceFiles(payload.workspace_files);
                  if (payload.active_file) {
                    setActiveFile(payload.active_file);
                  }
                }
              } else if (pendingEvent === 'complete') {
                setIsExecuting(false);
                setActiveNode(null);
                setConsoleLogs(prev => prev + '\n[System] Pipeline finished successfully.');
              } else if (pendingEvent === 'error') {
                setIsExecuting(false);
                setActiveNode(null);
                setConsoleLogs(prev => prev + '\n[System Error] ' + (payload.error || 'Unknown error'));
              }
            } catch (e) {
              console.warn("Error parsing SSE data", dataStr);
            }
          }
        }
      }
    } catch (err) {
      setConsoleLogs(prev => prev + `\n[System Error] ${err}`);
      setIsExecuting(false);
      setActiveNode(null);
    }
  };

  return (
    <div className="flex h-screen w-full bg-bg-deep text-text-primary overflow-hidden font-sans selection:bg-accent-cyan/30">
      <Sidebar 
        telemetry={telemetry} 
        files={Object.keys(workspaceFiles)}
        activeFile={activeFile}
        onSelectFile={setActiveFile}
      />
      
      <main className="flex-1 flex flex-col min-w-0 h-full p-4 gap-4">
        <header className="flex items-center gap-3 pb-3 border-b border-border-subtle shrink-0">
          <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-accent-cyan to-blue-600 flex items-center justify-center shadow-lg shadow-accent-cyan/20">
            <svg width="20" height="20" viewBox="0 0 32 32" xmlns="http://www.w3.org/2000/svg">
              <path d="M10 12l6-4 6 4v8l-6 4-6-4z" fill="#ffffff"/>
              <circle cx="16" cy="16" r="3" fill="#00b4d8"/>
            </svg>
          </div>
          <h1 className="text-2xl font-bold bg-gradient-to-r from-accent-cyan via-accent-blue to-purple-500 bg-clip-text text-transparent m-0 tracking-tight">
            AutoForge
          </h1>
          <div className="flex items-center gap-2 px-3 py-1 rounded-full bg-emerald-500/10 border border-emerald-500/30 text-emerald-400 text-[10px] font-bold tracking-widest uppercase">
            <div className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse shadow-[0_0_8px_rgba(16,185,129,0.8)]" />
            Pro IDE
          </div>
        </header>

        <PipelineGraph activeNode={activeNode} />

        <div className="flex-1 flex flex-col min-h-0 gap-4">
          <div className="flex-1 min-h-0 rounded-xl overflow-hidden border border-border-subtle bg-bg-panel shadow-2xl flex flex-col">
            <CodeEditor 
              code={workspaceFiles[activeFile] || ""} 
              activeFile={activeFile}
              files={Object.keys(workspaceFiles)}
              onSelectFile={setActiveFile}
              onChange={(newCode) => {
                if (newCode !== undefined) {
                  setWorkspaceFiles(prev => ({...prev, [activeFile]: newCode}));
                }
              }}
            />
          </div>
          
          <div className="h-[30vh] shrink-0 rounded-xl overflow-hidden border border-border-subtle shadow-inner flex flex-col relative group">
            <Terminal logs={consoleLogs} />
          </div>
        </div>

        <div className="shrink-0">
          <PromptInput isExecuting={isExecuting} onSubmit={executePrompt} />
        </div>
      </main>
    </div>
  );
}
