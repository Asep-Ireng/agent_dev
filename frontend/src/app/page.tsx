"use client";

import React, { useState, useEffect, useRef } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Sparkles, Code2, Settings2, Box, Loader2, Paperclip, Send, TerminalSquare, AlertTriangle, XCircle, CheckCircle, ChevronDown, ChevronRight, ChevronUp, FileCode2, Brain, Terminal } from "lucide-react";
import ReactMarkdown from "react-markdown";

type LogEntry =
  | { type: "thought"; text: string }
  | { type: "tool_call"; tool: string; input: string }
  | { type: "tool_input"; input: string }
  | { type: "tool_result"; tool: string; cwd: string; cmd: string; stdout: string; stderr: string; exit_code: number | null; success: boolean; raw: string }
  | { type: "final_answer"; text: string }
  | { type: "system"; text: string; level: "info" | "warn" | "error" }
  | { type: "log"; text: string }
  | { type: "cmd_start"; cwd: string; cmd: string }
  | { type: "cmd_output"; stream: "stdout" | "stderr"; line: string }
  | { type: "cmd_end"; exit_code: number; success: boolean };

export default function Home() {
  const [provider, setProvider] = useState(process.env.NEXT_PUBLIC_DEFAULT_PROVIDER || "Google (Gemini)");
  
  const defaultGoogleKey = process.env.NEXT_PUBLIC_GOOGLE_API_KEY || "";
  const defaultOpenAIKey = process.env.NEXT_PUBLIC_OPENAI_API_KEY || "";
  const [apiKey, setApiKey] = useState(provider === "OpenAI" ? defaultOpenAIKey : defaultGoogleKey);
  
  const defaultGoogleModel = process.env.NEXT_PUBLIC_GOOGLE_MODEL || "gemini-1.5-pro";
  const defaultOpenAIModel = process.env.NEXT_PUBLIC_OPENAI_MODEL || "gpt-4o";
  const [model, setModel] = useState(provider === "OpenAI" ? defaultOpenAIModel : defaultGoogleModel);
  
  const [workspacePath, setWorkspacePath] = useState(process.env.NEXT_PUBLIC_WORKSPACE_PATH || "./workspace");
  
  const [chatHistory, setChatHistory] = useState<{role: "user" | "agent", content: string}[]>([]);
  const [currentMessage, setCurrentMessage] = useState("");
  const [attachedFiles, setAttachedFiles] = useState<File[]>([]);
  
  const [spec, setSpec] = useState("");
  const [code, setCode] = useState("");
  const [specTab, setSpecTab] = useState<"preview" | "edit">("preview");
  
  const [designerLoading, setDesignerLoading] = useState(false);
  const [developerLoading, setDeveloperLoading] = useState(false);
  
  const [actionLogs, setActionLogs] = useState<LogEntry[]>([]);
  const [requireApproval, setRequireApproval] = useState(true);
  const [pendingCommand, setPendingCommand] = useState<string | null>(null);
  const [rejectReason, setRejectReason] = useState("");
  const [expandedThoughts, setExpandedThoughts] = useState<Set<number>>(new Set());
  const [agentResult, setAgentResult] = useState<string>("");
  const [devChatMessages, setDevChatMessages] = useState<{role: string; content: string}[]>([]);
  const [devChatInput, setDevChatInput] = useState("");
  const [devChatLoading, setDevChatLoading] = useState(false);
  const [devChatFiles, setDevChatFiles] = useState<File[]>([]);
  const [devChatMode, setDevChatMode] = useState<"ask" | "apply">("ask");
  const [pendingApplyTask, setPendingApplyTask] = useState<string | null>(null);
  const logsEndRef = useRef<HTMLDivElement>(null);
  const devChatEndRef = useRef<HTMLDivElement>(null);

  // Auto-scroll terminal to bottom when new logs arrive
  useEffect(() => {
    logsEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [actionLogs]);

  // Auto-scroll dev chat
  useEffect(() => {
    devChatEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [devChatMessages]);

  const handleChatSubmit = async () => {
    if (!apiKey) {
      alert("Please provide an API key in the sidebar.");
      return;
    }
    if (!currentMessage.trim() && attachedFiles.length === 0) return;

    const userText = currentMessage;
    setChatHistory(prev => [...prev, { role: "user", content: userText }]);
    setCurrentMessage("");
    setDesignerLoading(true);
    
    try {
      const formData = new FormData();
      formData.append("idea", userText);
      formData.append("spec", spec); // send current spec context
      formData.append("provider", provider);
      formData.append("model", model);
      formData.append("api_key", apiKey);
      attachedFiles.forEach(file => formData.append("files", file));

      const res = await fetch("http://localhost:8000/api/design/chat", {
        method: "POST",
        body: formData,
      });
      
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "API failed");
      
      setSpec(data.spec);
      setChatHistory(prev => [...prev, { role: "agent", content: data.summary || "Specification updated." }]);
      setAttachedFiles([]);
      setSpecTab("preview");
      
    } catch (err: unknown) {
      console.error("Design API Error:", err);
      if (err instanceof Error) {
        alert("Error: " + err.message);
      } else {
        alert("An unknown error occurred.");
      }
    } finally {
      setDesignerLoading(false);
    }
  };

  const addLog = (entry: LogEntry) => {
    setActionLogs(prev => [...prev, entry]);
  };

  const handleDevelop = () => {
    if (!apiKey) {
      alert("Please provide an API key in the sidebar.");
      return;
    }
    
    setDeveloperLoading(true);
    setActionLogs([]);
    setExpandedThoughts(new Set());
    setAgentResult("");
    setDevChatMessages([]);
    setDevChatInput("");
    
    const queryParams = new URLSearchParams({
      spec: spec,
      provider: provider,
      model: model,
      api_key: apiKey,
      workspace_path: workspacePath,
      require_approval: requireApproval.toString()
    }).toString();

    const eventSource = new EventSource(`http://localhost:8000/api/develop?${queryParams}`);

    // --- Typed event listeners ---
    
    const handleTypedEvent = (eventType: string) => (event: MessageEvent) => {
      try {
        const data = JSON.parse(event.data);
        switch (eventType) {
          case "thought":
            addLog({ type: "thought", text: data.text });
            break;
          case "tool_call":
            addLog({ type: "tool_call", tool: data.tool, input: data.input || "" });
            break;
          case "tool_input":
            addLog({ type: "tool_input", input: data.input });
            break;
          case "tool_result":
            addLog({ type: "tool_result", ...data });
            break;
          case "final_answer":
            addLog({ type: "final_answer", text: data.text });
            break;
          case "system":
            addLog({ type: "system", text: data.text, level: data.level || "info" });
            break;
          case "log":
            addLog({ type: "log", text: data.text });
            break;
          case "cmd_start":
            addLog({ type: "cmd_start", cwd: data.cwd, cmd: data.cmd });
            break;
          case "cmd_output":
            addLog({ type: "cmd_output", stream: data.stream, line: data.line });
            break;
          case "cmd_end":
            addLog({ type: "cmd_end", exit_code: data.exit_code, success: data.success });
            break;
        }
      } catch (e) {
        console.error(`Failed to parse ${eventType} event:`, e);
      }
    };

    eventSource.addEventListener("thought", handleTypedEvent("thought"));
    eventSource.addEventListener("tool_call", handleTypedEvent("tool_call"));
    eventSource.addEventListener("tool_input", handleTypedEvent("tool_input"));
    eventSource.addEventListener("tool_result", handleTypedEvent("tool_result"));
    eventSource.addEventListener("final_answer", handleTypedEvent("final_answer"));
    eventSource.addEventListener("system", handleTypedEvent("system"));
    eventSource.addEventListener("log", handleTypedEvent("log"));
    eventSource.addEventListener("cmd_start", handleTypedEvent("cmd_start"));
    eventSource.addEventListener("cmd_output", handleTypedEvent("cmd_output"));
    eventSource.addEventListener("cmd_end", handleTypedEvent("cmd_end"));

    eventSource.addEventListener("result", (event) => {
      try {
        const data = JSON.parse(event.data);
        if (data.text) setAgentResult(data.text);
      } catch (e) {
        console.error("Failed to parse result event:", e);
      }
    });

    eventSource.addEventListener("action_required", (event) => {
      try {
        const data = JSON.parse(event.data);
        setPendingCommand(data.command);
      } catch (e) {
        console.error("Failed to parse action_required data:", e);
      }
    });

    eventSource.onerror = (err) => {
      console.error("EventSource failed:", err);
      addLog({ type: "system", text: "Connection closed or errored.", level: "error" });
      setPendingCommand(null);
      eventSource.close();
      setDeveloperLoading(false);
    };

    eventSource.addEventListener("done", (event) => {
      try {
        const data = JSON.parse(event.data);
        const status = data.status || (data.killed ? "killed" : data.error ? "failed" : "success");
        const summary = data.status_summary ? ` — ${data.status_summary}` : "";
        
        switch (status) {
          case "killed":
            addLog({ type: "system", text: "Agent stopped by user.", level: "warn" });
            break;
          case "failed":
            addLog({ type: "system", text: `Development failed.${summary}`, level: "error" });
            break;
          case "partial":
            addLog({ type: "system", text: `Development partially completed — some issues occurred.${summary}`, level: "warn" });
            break;
          case "success":
          default:
            addLog({ type: "system", text: `Development completed successfully!${summary}`, level: "info" });
            break;
        }
      } catch {
        addLog({ type: "system", text: "Development process finished.", level: "info" });
      }
      setPendingCommand(null);
      eventSource.close();
      setDeveloperLoading(false);
    });
  };

  const handleStopDevelop = async () => {
    try {
      addLog({ type: "system", text: "Sending kill signal...", level: "warn" });
      await fetch("http://localhost:8000/api/develop/stop", { method: "POST" });
    } catch (err) {
      console.error("Failed to send stop signal:", err);
    }
  };

  const handleDevChat = async () => {
    if (!devChatInput.trim() || devChatLoading) return;
    
    const userMessage = devChatInput.trim();
    const filesToSend = [...devChatFiles];
    setDevChatInput("");
    setDevChatFiles([]);
    
    const modeLabel = devChatMode === "apply" ? "🔧" : "💬";
    const displayText = filesToSend.length > 0 
      ? `${modeLabel} ${userMessage} [📎 ${filesToSend.length} file${filesToSend.length > 1 ? 's' : ''}]`
      : `${modeLabel} ${userMessage}`;
    setDevChatMessages(prev => [...prev, { role: "user", content: displayText }]);
    setDevChatLoading(true);
    
    if (devChatMode === "apply") {
      // Apply mode — Step 1: Get a plan from litellm first
      try {
        const formData = new FormData();
        formData.append("message", `The user wants you to make the following change:\n\n"${userMessage}"\n\nCreate a brief, specific plan of what you will do. List the files you will read, modify, or create, and describe the changes concisely. Do NOT execute anything yet — just describe the plan.`);
        formData.append("spec", spec);
        formData.append("workspace_path", workspacePath);
        formData.append("history", JSON.stringify(devChatMessages));
        formData.append("provider", provider);
        formData.append("model", model);
        formData.append("api_key", apiKey);
        filesToSend.forEach(file => formData.append("files", file));
        
        const response = await fetch("http://localhost:8000/api/dev-chat", {
          method: "POST",
          body: formData
        });
        
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        
        const data = await response.json();
        // Store the plan and the original task, show with a Proceed button
        setPendingApplyTask(userMessage);
        setDevChatMessages(prev => [...prev, { role: "assistant", content: `**📋 Proposed Plan:**\n\n${data.reply}\n\n---\n_Click **Proceed** below to execute this plan, or type a follow-up to refine it._` }]);
      } catch (err) {
        console.error("Dev chat plan error:", err);
        setDevChatMessages(prev => [...prev, { role: "assistant", content: "Failed to generate a plan. Check the backend." }]);
        setPendingApplyTask(null);
      } finally {
        setDevChatLoading(false);
      }
    } else {
      // Ask mode — normal chat
      try {
        const formData = new FormData();
        formData.append("message", userMessage);
        formData.append("spec", spec);
        formData.append("workspace_path", workspacePath);
        formData.append("history", JSON.stringify(devChatMessages));
        formData.append("provider", provider);
        formData.append("model", model);
        formData.append("api_key", apiKey);
        filesToSend.forEach(file => formData.append("files", file));
        
        const response = await fetch("http://localhost:8000/api/dev-chat", {
          method: "POST",
          body: formData
        });
        
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        
        const data = await response.json();
        setDevChatMessages(prev => [...prev, { role: "assistant", content: data.reply }]);
      } catch (err) {
        console.error("Dev chat error:", err);
        setDevChatMessages(prev => [...prev, { role: "assistant", content: "Sorry, something went wrong. Check that the backend is running." }]);
      } finally {
        setDevChatLoading(false);
      }
    }
  };

  const handleApplyProceed = () => {
    if (!pendingApplyTask) return;
    
    const taskToExecute = pendingApplyTask;
    setPendingApplyTask(null);
    setDevChatMessages(prev => [...prev, { role: "user", content: "▶ Proceeding with the plan..." }]);
    setDeveloperLoading(true);
    setActionLogs([]);
    
    // Build chat context so the iterate agent knows what was discussed
    const chatContext = devChatMessages
      .slice(-10) // last 10 messages for context
      .map(m => `${m.role === "user" ? "User" : "Dev"}: ${m.content}`)
      .join("\n");
    const fullTask = chatContext
      ? `${taskToExecute}\n\n--- Chat Context ---\n${chatContext}`
      : taskToExecute;
    
    const queryParams = new URLSearchParams({
      task: fullTask,
      spec: spec,
      dev_context: agentResult || "",
      workspace_path: workspacePath,
      provider: provider,
      model: model,
      api_key: apiKey,
      require_approval: requireApproval ? "true" : "false"
    });
    
    const eventSource = new EventSource(`http://localhost:8000/api/dev-iterate?${queryParams.toString()}`);
    
    const addLog = (entry: LogEntry) => setActionLogs(prev => [...prev, entry]);
    
    const handleTypedEvent = (eventType: string) => (event: MessageEvent) => {
      try {
        const data = JSON.parse(event.data);
        switch (eventType) {
          case "thought": addLog({ type: "thought", text: data.text }); break;
          case "tool_call": addLog({ type: "tool_call", tool: data.tool, input: data.input }); break;
          case "tool_input": addLog({ type: "tool_input", input: data.input }); break;
          case "tool_result": addLog({ type: "tool_result", ...data }); break;
          case "final_answer": addLog({ type: "final_answer", text: data.text }); break;
          case "system": addLog({ type: "system", text: data.text, level: data.level }); break;
          case "log": addLog({ type: "log", text: data.text }); break;
          case "cmd_start": addLog({ type: "cmd_start", cwd: data.cwd, cmd: data.cmd }); break;
          case "cmd_output": addLog({ type: "cmd_output", stream: data.stream, line: data.line }); break;
          case "cmd_end": addLog({ type: "cmd_end", exit_code: data.exit_code, success: data.success }); break;
        }
      } catch (e) {
        console.error(`Failed to parse ${eventType} event:`, e);
      }
    };
    
    ["thought", "tool_call", "tool_input", "tool_result", "final_answer", "system", "log", "cmd_start", "cmd_output", "cmd_end"].forEach(evt => {
      eventSource.addEventListener(evt, handleTypedEvent(evt));
    });
    
    eventSource.addEventListener("action_required", (event) => {
      try {
        const data = JSON.parse(event.data);
        setPendingCommand(data.command);
      } catch (e) { console.error(e); }
    });
    
    eventSource.addEventListener("result", (event) => {
      try {
        const data = JSON.parse(event.data);
        if (data.text) {
          setDevChatMessages(prev => [...prev, { role: "assistant", content: `✅ **Changes Applied:**\n\n${data.text}` }]);
        }
      } catch (e) { console.error(e); }
    });
    
    eventSource.addEventListener("done", () => {
      eventSource.close();
      setDeveloperLoading(false);
    });
    
    eventSource.onerror = () => {
      addLog({ type: "system", text: "Iteration connection closed or errored.", level: "error" });
      eventSource.close();
      setDeveloperLoading(false);
    };
  };

  const handleCommandApproval = async (approved: boolean) => {
    try {
      setPendingCommand(null);
      await fetch("http://localhost:8000/api/develop/approve", { 
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ 
          approved, 
          feedback: approved ? undefined : rejectReason 
        })
      });
      setRejectReason("");
    } catch (err) {
      console.error("Failed to send approval:", err);
    }
  };

  return (
    <div className="flex h-screen bg-[#25343F] text-[#EAEFEF]/80 font-sans selection:bg-[#FF9B51]/30 overflow-hidden">
      
      {/* SIDEBAR */}
      <motion.aside 
        initial={{ x: -300, opacity: 0 }}
        animate={{ x: 0, opacity: 1 }}
        transition={{ duration: 0.5, ease: "easeOut" }}
        className="w-80 bg-black/20 backdrop-blur-md border-r border-[#EAEFEF]/5 p-6 flex flex-col shadow-2xl z-10"
      >
        <div className="flex items-center gap-3 mb-10">
          <div className="p-2 bg-gradient-to-br from-[#FF9B51] to-[#FF9B51] rounded-xl shadow-lg shadow-[#FF9B51]/30">
            <Sparkles className="w-5 h-5 text-[#EAEFEF]" />
          </div>
          <h1 className="text-xl font-bold bg-clip-text text-transparent bg-gradient-to-r from-[#EAEFEF] to-[#BFC9D1]">
            Agentic Dev Studio
          </h1>
        </div>

        <div className="space-y-6">
          <div className="space-y-2">
            <label className="text-xs font-semibold text-slate-500 uppercase tracking-wider flex items-center gap-2">
              <Settings2 className="w-3 h-3" /> Provider
            </label>
            <div className="grid grid-cols-2 gap-2">
              {["OpenAI", "Google (Gemini)"].map((p) => (
                <button
                  key={p}
                  onClick={() => {
                    setProvider(p);
                    setApiKey(p === "OpenAI" ? defaultOpenAIKey : defaultGoogleKey);
                    setModel(p === "OpenAI" ? defaultOpenAIModel : defaultGoogleModel);
                  }}
                  className={`px-3 py-2 rounded-lg text-sm font-medium transition-all duration-200 border 
                    ${provider === p 
                      ? "bg-[#FF9B51]/30 border-[#FF9B51]/50 text-[#EAEFEF] shadow-inner" 
                      : "bg-black/20 border-[#EAEFEF]/5 hover:bg-[#EAEFEF]/5 text-[#EAEFEF]/60"
                    }`}
                >
                  {p.split(" ")[0]}
                </button>
              ))}
            </div>
          </div>

          <div className="space-y-2">
            <label className="text-xs font-semibold text-slate-500 uppercase tracking-wider">Model</label>
            <input
              type="text"
              value={model}
              onChange={(e) => setModel(e.target.value)}
              className="w-full bg-black/20 border border-[#EAEFEF]/5 rounded-lg px-4 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-[#FF9B51]/50 transition-all placeholder:text-[#EAEFEF]/40"
            />
          </div>

          <div className="space-y-2">
            <label className="text-xs font-semibold text-slate-500 uppercase tracking-wider">API Key</label>
            <input
              type="password"
              placeholder={provider === "OpenAI" ? "sk-..." : "AIza..."}
              value={apiKey}
              onChange={(e) => setApiKey(e.target.value)}
              className="w-full bg-black/20 border border-[#EAEFEF]/5 rounded-lg px-4 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-[#FF9B51]/50 transition-all font-mono placeholder:font-sans"
            />
          </div>

          <div className="space-y-2">
            <label className="text-xs font-semibold text-slate-500 uppercase tracking-wider">Workspace Path</label>
            <input
              type="text"
              placeholder="./workspace"
              value={workspacePath}
              onChange={(e) => setWorkspacePath(e.target.value)}
              className="w-full bg-black/20 border border-[#EAEFEF]/5 rounded-lg px-4 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-[#FF9B51]/50 transition-all font-mono placeholder:text-[#EAEFEF]/40"
            />
            <p className="text-[10px] text-[#BFC9D1]/50 mt-1">Directory where the agent writes code.</p>
          </div>

          <div className="space-y-2 pt-2 border-t border-[#EAEFEF]/5">
            <label className="text-xs font-semibold text-slate-500 uppercase tracking-wider flex items-center justify-between">
              <span>HITL Verification</span>
              <button 
                onClick={() => {
                  const newVal = !requireApproval;
                  setRequireApproval(newVal);
                  // If dev agent is running, live-update the approval setting
                  if (developerLoading) {
                    fetch(`http://localhost:8000/api/develop/toggle-approval?require=${newVal}`, { method: "POST" }).catch(() => {});
                  }
                }}
                className={`relative inline-flex h-5 w-9 shrink-0 cursor-pointer rounded-full transition-colors duration-200 ease-in-out ${requireApproval ? 'bg-[#FF9B51]' : 'bg-[#EAEFEF]/20'}`}
              >
                <span className={`inline-block h-4 w-4 transform rounded-full bg-white shadow transition duration-200 ease-in-out mt-0.5 ${requireApproval ? 'translate-x-4' : 'translate-x-0.5'}`} />
              </button>
            </label>
            <p className="text-[10px] text-[#EAEFEF]/40 mt-1">Require explicit approval before executing any Terminal commands.</p>
          </div>
        </div>
      </motion.aside>

      {/* MAIN CONTENT */}
      <main className="flex-1 overflow-y-auto p-10 relative">
        <div className="max-w-4xl mx-auto space-y-12 pb-32">
          
          {/* HEADER AREA */}
          <motion.div 
            initial={{ y: 20, opacity: 0 }} 
            animate={{ y: 0, opacity: 1 }} 
            transition={{ delay: 0.1 }}
            className="space-y-2"
          >
            <h2 className="text-3xl font-light text-[#EAEFEF] tracking-tight">What are we building?</h2>
            <p className="text-[#EAEFEF]/60 text-sm">Enter a high level idea and watch the agents build the software.</p>
          </motion.div>

          {/* MAIN INTERFACE: Split view for Chat & Spec */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-8 h-[600px]">
            
            {/* LEFT COLUMN: CHAT */}
            <div className="flex flex-col bg-black/20 border border-[#EAEFEF]/5 rounded-2xl shadow-xl overflow-hidden h-full">
              <div className="p-4 bg-gradient-to-r from-[#FF9B51]/40 to-[#FF9B51]/20 border-b border-[#EAEFEF]/5">
                <h3 className="text-lg font-medium text-[#EAEFEF] flex items-center gap-2">
                  <Sparkles className="w-4 h-4 text-[#FF9B51]" /> Chat with Lead Designer
                </h3>
                <p className="text-xs text-[#EAEFEF]/60 mt-1">Start by describing your app. Attach PDFs or Images.</p>
              </div>
              
              <div className="flex-1 overflow-y-auto p-4 space-y-4 custom-scrollbar">
                {chatHistory.length === 0 && (
                  <div className="h-full flex flex-col items-center justify-center text-[#EAEFEF]/30 space-y-3">
                    <Box className="w-8 h-8 opacity-50" />
                    <p className="text-sm">No messages yet. Tell me what to build!</p>
                  </div>
                )}
                {chatHistory.map((msg, idx) => (
                  <div key={idx} className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}>
                    <div className={`max-w-[80%] rounded-2xl px-4 py-2 text-sm ${
                      msg.role === "user" 
                        ? "bg-[#FF9B51] text-[#25343F] font-medium" 
                        : "bg-white/5 border border-white/10 text-[#EAEFEF]/90"
                    }`}>
                      {msg.content}
                    </div>
                  </div>
                ))}
                {designerLoading && (
                  <div className="flex justify-start">
                    <div className="max-w-[80%] rounded-2xl px-4 py-2 text-sm bg-white/5 border border-white/10 text-[#EAEFEF]/60 flex items-center gap-2">
                      <Loader2 className="w-4 h-4 animate-spin" /> Rethinking architecture...
                    </div>
                  </div>
                )}
              </div>

              <div className="p-4 bg-[#0A0A0B]/50 border-t border-[#EAEFEF]/5 space-y-3">
                {/* File Previews */}
                {attachedFiles.length > 0 && (
                  <div className="flex gap-2 mx-2 overflow-x-auto custom-scrollbar pb-2">
                    {attachedFiles.map((f, i) => (
                      <div key={i} className="flex items-center gap-2 shrink-0 bg-[#FF9B51]/30 border border-[#FF9B51]/50 text-[#EAEFEF] text-xs px-2 py-1 rounded-md">
                        <span className="truncate max-w-[100px]">{f.name}</span>
                        <button onClick={() => setAttachedFiles(prev => prev.filter((_, idx) => idx !== i))} className="text-[#EAEFEF]/60 hover:text-white">&times;</button>
                      </div>
                    ))}
                  </div>
                )}
                
                <div className="flex items-end gap-2">
                  <div className="relative flex-1 group">
                    <textarea
                      className="w-full bg-[#1A1A1D] border border-[#EAEFEF]/10 rounded-xl pl-4 pr-10 py-3 text-sm text-[#EAEFEF] focus:outline-none focus:ring-2 focus:ring-[#FF9B51]/50 transition-all resize-none shadow-inner"
                      placeholder="e.g. Build a capybara tracking app using Next.js & Supabase..."
                      rows={2}
                      value={currentMessage}
                      onChange={(e) => setCurrentMessage(e.target.value)}
                      onKeyDown={(e) => {
                        if (e.key === "Enter" && !e.shiftKey) {
                          e.preventDefault();
                          handleChatSubmit();
                        }
                      }}
                      onPaste={(e) => {
                        const items = e.clipboardData?.items;
                        if (!items) return;
                        for (const item of Array.from(items)) {
                          if (item.type.startsWith("image/")) {
                            const file = item.getAsFile();
                            if (file) {
                              const named = new File([file], `clipboard-${Date.now()}.png`, { type: file.type });
                              setAttachedFiles(prev => [...prev, named]);
                            }
                          }
                        }
                      }}
                    />
                    {/* Hidden File Input */}
                    <input 
                      type="file" 
                      multiple 
                      id="file-upload" 
                      className="hidden" 
                      accept=".pdf,image/*"
                      onChange={(e) => {
                        if (e.target.files) {
                          setAttachedFiles(prev => [...prev, ...Array.from(e.target.files!)]);
                        }
                      }}
                    />
                    <label 
                      htmlFor="file-upload"
                      className="absolute right-3 top-3 text-[#EAEFEF]/40 hover:text-[#FF9B51] cursor-pointer transition-colors"
                      title="Attach PDFs or Images"
                    >
                      <Paperclip className="w-5 h-5" />
                    </label>
                  </div>
                  
                  <button
                    onClick={handleChatSubmit}
                    disabled={designerLoading}
                    className="p-3 bg-gradient-to-r from-[#FF9B51] to-[#FF9B51] text-[#EAEFEF] rounded-xl hover:brightness-110 transition-all active:scale-95 disabled:opacity-50 shadow-lg shadow-[#FF9B51]/30 shrink-0"
                  >
                    <Send className="w-5 h-5" />
                  </button>
                </div>
              </div>
            </div>

            {/* RIGHT COLUMN: SPEC VIEWER */}
            <div className="flex flex-col bg-black/20 border border-[#EAEFEF]/5 rounded-2xl shadow-xl overflow-hidden h-full">
              {/* Tabs */}
              <div className="flex justify-between items-center bg-black/40 border-b border-[#EAEFEF]/5 p-2">
                <div className="flex gap-2">
                  <button 
                    onClick={() => setSpecTab("preview")}
                    className={`px-4 py-1.5 rounded-lg text-sm font-medium transition-all ${specTab === "preview" ? "bg-[#FF9B51]/40 text-[#EAEFEF]" : "text-[#EAEFEF]/50 hover:text-[#EAEFEF]/80 hover:bg-[#EAEFEF]/5"}`}
                  >
                    Preview
                  </button>
                  <button 
                    onClick={() => setSpecTab("edit")}
                    className={`px-4 py-1.5 rounded-lg text-sm font-medium transition-all ${specTab === "edit" ? "bg-[#FF9B51]/40 text-[#EAEFEF]" : "text-[#EAEFEF]/50 hover:text-[#EAEFEF]/80 hover:bg-[#EAEFEF]/5"}`}
                  >
                    Raw Edit
                  </button>
                </div>
                {spec && (
                  <div className="flex gap-2">
                    {developerLoading && (
                       <button
                         onClick={handleStopDevelop}
                         className="px-4 py-1.5 bg-red-500/20 text-red-500 hover:bg-red-500/30 border border-red-500/50 text-sm font-semibold rounded-lg flex items-center gap-1.5 transition-all active:scale-95 shadow-md"
                       >
                         <XCircle className="w-4 h-4" /> Stop Agent
                       </button>
                    )}
                    <button
                      onClick={handleDevelop}
                      disabled={developerLoading || designerLoading}
                      className="px-4 py-1.5 bg-white text-[#25343F] text-sm font-semibold rounded-lg flex items-center gap-1.5 hover:bg-gray-200 transition-all active:scale-95 shadow-md disabled:opacity-50"
                    >
                      {developerLoading ? <Loader2 className="w-3 h-3 animate-spin" /> : "Approve & Dev →"}
                    </button>
                  </div>
                )}
              </div>

              {/* Content */}
              <div className="flex-1 relative">
                 {specTab === "edit" ? (
                  <textarea
                    className="w-full h-full absolute inset-0 bg-transparent p-6 text-[#EAEFEF]/90 focus:outline-none font-mono text-sm leading-relaxed resize-none custom-scrollbar"
                    value={spec}
                    onChange={(e) => setSpec(e.target.value)}
                    placeholder="Specification will appear here after your first chat message..."
                    disabled={designerLoading}
                  />
                ) : (
                  <div className="w-full h-full absolute inset-0 bg-transparent p-6 text-[#EAEFEF]/90 overflow-y-auto custom-scrollbar prose prose-invert prose-slate max-w-none prose-p:text-[#EAEFEF]/80 prose-headings:text-[#EAEFEF]">
                    <ReactMarkdown>{spec || "_Awaiting initial instructions..._"}</ReactMarkdown>
                  </div>
                )}
              </div>
            </div>
            
          </div>

          {/* STEP 3: ACTION AGENT TERMINAL */}
          <AnimatePresence>
            {(actionLogs.length > 0 || developerLoading) && (
              <motion.div
                initial={{ y: 30, opacity: 0, scale: 0.95 }}
                animate={{ y: 0, opacity: 1, scale: 1 }}
                className="space-y-4 pt-8 border-t border-white/5"
              >
                <div className="flex justify-between items-center">
                  <div className="flex items-center gap-3">
                    <div className="w-8 h-8 rounded-full bg-[#FF9B51]/20 flex items-center justify-center border border-[#FF9B51]/40">
                      <TerminalSquare className="w-4 h-4 text-[#FF9B51]" />
                    </div>
                    <h3 className="text-xl font-medium text-[#EAEFEF]">Live Terminal Stream</h3>
                  </div>
                  {developerLoading && (
                    <div className="flex items-center gap-2 text-sm text-[#FF9B51] font-medium animate-pulse">
                      <Loader2 className="w-4 h-4 animate-spin" /> Autonomous Agent Active
                    </div>
                  )}
                </div>
                
                {/* Terminal Window Block */}
                <div className="bg-[#0A0A0B] border border-[#EAEFEF]/10 rounded-2xl shadow-2xl overflow-hidden font-mono text-sm leading-relaxed h-[400px] flex flex-col">
                  {/* Mac style OS header */}
                  <div className="flex gap-2 p-3 bg-white/5 border-b border-white/5 items-center">
                    <div className="w-3 h-3 rounded-full bg-red-500/80"></div>
                    <div className="w-3 h-3 rounded-full bg-yellow-500/80"></div>
                    <div className="w-3 h-3 rounded-full bg-green-500/80"></div>
                    <div className="mx-auto text-[10px] text-white/30 tracking-widest uppercase truncate max-w-[50%]">BASH ~ {workspacePath}</div>
                  </div>
                  
                  {/* Streaming Logs */}
                  <div className="flex-1 overflow-y-auto p-4 space-y-2 custom-scrollbar text-[#EAEFEF]/80 relative">
                    {actionLogs.map((log, idx) => {
                      switch (log.type) {
                        case "thought":
                          const isExpanded = expandedThoughts.has(idx);
                          return (
                            <div key={idx} className="group">
                              <button
                                onClick={() => setExpandedThoughts(prev => {
                                  const next = new Set(prev);
                                  next.has(idx) ? next.delete(idx) : next.add(idx);
                                  return next;
                                })}
                                className="flex items-center gap-2 text-[#EAEFEF]/40 hover:text-[#EAEFEF]/70 transition-colors text-xs w-full text-left"
                              >
                                <Brain className="w-3 h-3 shrink-0" />
                                {isExpanded ? <ChevronDown className="w-3 h-3 shrink-0" /> : <ChevronRight className="w-3 h-3 shrink-0" />}
                                <span className="font-medium">Agent Thinking</span>
                                {!isExpanded && <span className="truncate opacity-60 ml-1">{log.text.slice(0, 80)}...</span>}
                              </button>
                              {isExpanded && (
                                <div className="ml-5 mt-1 pl-3 border-l border-[#EAEFEF]/10 text-[#EAEFEF]/50 text-xs whitespace-pre-wrap leading-relaxed">
                                  {log.text}
                                </div>
                              )}
                            </div>
                          );

                        case "tool_call":
                          return (
                            <div key={idx} className="mt-3 flex items-center gap-2">
                              <Terminal className="w-3.5 h-3.5 text-green-400 shrink-0" />
                              <span className="text-green-400 text-xs font-semibold uppercase tracking-wider">Using Tool:</span>
                              <span className="text-green-300 text-sm font-medium">{log.tool}</span>
                            </div>
                          );

                        case "tool_input":
                          return (
                            <div key={idx} className="ml-5 bg-white/5 border border-white/10 rounded-lg p-2 font-mono text-xs text-[#EAEFEF]/70 whitespace-pre-wrap break-all max-h-32 overflow-y-auto custom-scrollbar">
                              {log.input}
                            </div>
                          );

                        case "tool_result":
                          return (
                            <div key={idx} className={`ml-5 mb-2 rounded-lg border overflow-hidden ${log.success ? 'border-green-500/30' : 'border-red-500/40'}`}>
                              {/* Result header */}
                              <div className={`flex items-center gap-2 px-3 py-1.5 text-xs ${log.success ? 'bg-green-500/10 text-green-400' : 'bg-red-500/10 text-red-400'}`}>
                                {log.success ? <CheckCircle className="w-3 h-3" /> : <XCircle className="w-3 h-3" />}
                                <span className="font-semibold">{log.success ? "SUCCESS" : "FAILED"}</span>
                                {log.tool === "terminal" && log.exit_code !== null && (
                                  <span className="opacity-60">Exit code {log.exit_code}</span>
                                )}
                                {log.cwd && (
                                  <span className="ml-auto bg-black/30 px-2 py-0.5 rounded text-[10px] text-[#EAEFEF]/50 font-mono">{log.cwd}</span>
                                )}
                              </div>
                              {/* Command */}
                              {log.cmd && (
                                <div className="px-3 py-1.5 bg-black/30 border-b border-white/5 font-mono text-xs text-green-400">
                                  $ {log.cmd}
                                </div>
                              )}
                              {/* Stdout */}
                              {log.stdout && (
                                <div className="px-3 py-2 font-mono text-[11px] text-[#EAEFEF]/70 whitespace-pre-wrap max-h-48 overflow-y-auto custom-scrollbar bg-black/20">
                                  {log.stdout}
                                </div>
                              )}
                              {/* Stderr */}
                              {log.stderr && (
                                <div className="px-3 py-2 font-mono text-[11px] text-red-400/80 whitespace-pre-wrap max-h-32 overflow-y-auto custom-scrollbar bg-red-500/5 border-t border-red-500/20">
                                  {log.stderr}
                                </div>
                              )}
                            </div>
                          );

                        case "final_answer":
                          return (
                            <div key={idx} className="mt-3 bg-[#FF9B51]/20 border border-[#FF9B51]/40 rounded-lg p-3">
                              <div className="flex items-center gap-2 text-xs text-[#FF9B51] font-semibold mb-1">
                                <Sparkles className="w-3 h-3" /> Agent Summary
                              </div>
                              <div className="text-sm text-[#EAEFEF]/90 whitespace-pre-wrap">{log.text}</div>
                            </div>
                          );

                        case "system":
                          const colorMap = {
                            info: "text-blue-400",
                            warn: "text-yellow-400",
                            error: "text-red-400"
                          };
                          const bgMap = {
                            info: "bg-blue-500/5",
                            warn: "bg-yellow-500/5",
                            error: "bg-red-500/10"
                          };
                          return (
                            <div key={idx} className={`flex items-center gap-2 px-2 py-1 rounded text-xs font-medium ${colorMap[log.level]} ${bgMap[log.level]} mt-1`}>
                              {log.level === "error" ? <XCircle className="w-3 h-3" /> : log.level === "warn" ? <AlertTriangle className="w-3 h-3" /> : <TerminalSquare className="w-3 h-3" />}
                              {log.text}
                            </div>
                          );

                        case "log":
                          return (
                            <div key={idx} className="text-xs text-[#EAEFEF]/50 whitespace-pre-wrap pl-2">{log.text}</div>
                          );

                        case "cmd_start":
                          return (
                            <div key={idx} className="mt-3 bg-black/30 border border-white/10 rounded-lg overflow-hidden">
                              <div className="flex items-center gap-2 px-3 py-1.5">
                                <Terminal className="w-3 h-3 text-green-400" />
                                <span className="text-green-400 font-mono text-xs font-medium">$ {log.cmd}</span>
                                <span className="ml-auto bg-black/30 px-2 py-0.5 rounded text-[10px] text-[#EAEFEF]/40 font-mono">{log.cwd}</span>
                              </div>
                            </div>
                          );

                        case "cmd_output":
                          return (
                            <div key={idx} className={`pl-5 font-mono text-[11px] whitespace-pre-wrap ${log.stream === "stderr" ? "text-red-400/70" : "text-[#EAEFEF]/60"}`}>
                              {log.line}
                            </div>
                          );

                        case "cmd_end":
                          return (
                            <div key={idx} className={`pl-5 flex items-center gap-1.5 text-[10px] font-medium mt-0.5 mb-1 ${log.success ? "text-green-500/70" : "text-red-400"}`}>
                              {log.success ? <CheckCircle className="w-2.5 h-2.5" /> : <XCircle className="w-2.5 h-2.5" />}
                              {log.success ? "Done" : `Failed (exit ${log.exit_code})`}
                            </div>
                          );

                        default:
                          return null;
                      }
                    })}
                    
                    {/* Auto-scroll anchor */}
                    <div ref={logsEndRef} />
                    
                    {/* HITL Action Block */}
                    {pendingCommand && (
                      <motion.div 
                        initial={{ opacity: 0, y: 10 }}
                        animate={{ opacity: 1, y: 0 }}
                        className="sticky bottom-4 mx-4 bg-[#FF9B51]/20 border border-[#FF9B51]/50 backdrop-blur-md rounded-xl p-4 shadow-2xl z-10"
                      >
                        <div className="flex items-start gap-3">
                          <AlertTriangle className="w-5 h-5 text-yellow-500 shrink-0 mt-0.5" />
                          <div className="flex-1">
                            <h4 className="text-sm font-semibold text-[#EAEFEF]">Action Required</h4>
                            <p className="text-xs text-[#EAEFEF]/70 mt-1 mb-3">The agent wants to execute the following operation:</p>
                            <div className="bg-black/50 p-2 rounded border border-[#EAEFEF]/10 font-mono text-[10px] text-green-400 break-all mb-4 whitespace-pre-wrap max-h-40 overflow-y-auto custom-scrollbar">
                              {pendingCommand}
                            </div>
                            <input
                              type="text"
                              placeholder="Optional reason for rejection (e.g. 'Use npm instead of yarn')"
                              value={rejectReason}
                              onChange={(e) => setRejectReason(e.target.value)}
                              className="w-full bg-black/40 border border-white/10 rounded px-3 py-1.5 text-xs text-white mb-4 focus:outline-none focus:ring-1 focus:ring-red-500/50 placeholder:text-white/30"
                            />
                            <div className="flex gap-2">
                              <button 
                                onClick={() => handleCommandApproval(true)}
                                className="flex-1 py-1.5 bg-green-500/20 text-green-400 hover:bg-green-500/30 border border-green-500/50 rounded flex items-center justify-center gap-1 text-xs font-semibold transition-colors"
                              >
                                <CheckCircle className="w-3.5 h-3.5" /> Approve Action
                              </button>
                              <button 
                                onClick={() => handleCommandApproval(false)}
                                className="flex-1 py-1.5 bg-red-500/20 text-red-400 hover:bg-red-500/30 border border-red-500/50 rounded flex items-center justify-center gap-1 text-xs font-semibold transition-colors"
                              >
                                <XCircle className="w-3.5 h-3.5" /> Reject & Rethink
                              </button>
                            </div>
                          </div>
                        </div>
                      </motion.div>
                    )}
                  </div>
                </div>
              </motion.div>
            )}
          </AnimatePresence>

          {/* AGENT RESULT PANEL */}
          <AnimatePresence>
            {agentResult && !developerLoading && (
              <motion.div
                initial={{ y: 30, opacity: 0, scale: 0.95 }}
                animate={{ y: 0, opacity: 1, scale: 1 }}
                exit={{ opacity: 0, scale: 0.95 }}
                transition={{ duration: 0.4, ease: "easeOut" }}
                className="space-y-4 pt-8 border-t border-white/5"
              >
                <div className="flex items-center gap-3">
                  <div className="w-8 h-8 rounded-full bg-gradient-to-br from-[#FF9B51] to-[#FF9B51] flex items-center justify-center shadow-lg shadow-[#FF9B51]/30">
                    <Sparkles className="w-4 h-4 text-white" />
                  </div>
                  <h3 className="text-xl font-medium text-[#EAEFEF]">Agent Result</h3>
                </div>

                <div className="bg-black/20 border border-[#FF9B51]/30 rounded-2xl shadow-xl overflow-hidden">
                  <div className="flex items-center justify-between px-4 py-2 bg-[#FF9B51]/20 border-b border-[#FF9B51]/20">
                    <span className="text-xs text-[#EAEFEF]/60 font-medium uppercase tracking-wider">Development Summary</span>
                    <button
                      onClick={() => navigator.clipboard.writeText(agentResult)}
                      className="text-xs text-[#EAEFEF]/40 hover:text-[#EAEFEF]/80 transition-colors px-2 py-1 rounded hover:bg-white/5"
                    >
                      Copy
                    </button>
                  </div>
                  <div className="p-6 overflow-y-auto max-h-[500px] custom-scrollbar prose prose-invert prose-slate max-w-none prose-p:text-[#EAEFEF]/80 prose-headings:text-[#EAEFEF] prose-code:text-[#FF9B51] prose-pre:bg-black/40 prose-pre:border prose-pre:border-white/10 text-sm">
                    <ReactMarkdown>{agentResult}</ReactMarkdown>
                  </div>
                </div>
              </motion.div>
            )}
          </AnimatePresence>

          {/* DEV AGENT CHAT */}
          <AnimatePresence>
            {agentResult && !developerLoading && (
              <motion.div
                initial={{ y: 30, opacity: 0, scale: 0.95 }}
                animate={{ y: 0, opacity: 1, scale: 1 }}
                exit={{ opacity: 0, scale: 0.95 }}
                transition={{ duration: 0.4, ease: "easeOut", delay: 0.15 }}
                className="space-y-4 pt-8 border-t border-white/5"
              >
                <div className="flex items-center gap-3">
                  <div className="w-8 h-8 rounded-full bg-gradient-to-br from-[#2D4961] to-[#395370] flex items-center justify-center shadow-lg shadow-[#2D4961]/30">
                    <Code2 className="w-4 h-4 text-white" />
                  </div>
                  <h3 className="text-xl font-medium text-[#EAEFEF]">Chat with Developer</h3>
                  <div className="ml-auto flex gap-1 bg-black/30 rounded-lg p-0.5">
                    <button
                      onClick={() => setDevChatMode("ask")}
                      className={`px-3 py-1 rounded-md text-xs font-medium transition-all ${
                        devChatMode === "ask"
                          ? "bg-[#395370]/60 text-[#EAEFEF] shadow-sm"
                          : "text-[#EAEFEF]/40 hover:text-[#EAEFEF]/70"
                      }`}
                    >
                      💬 Ask
                    </button>
                    <button
                      onClick={() => setDevChatMode("apply")}
                      className={`px-3 py-1 rounded-md text-xs font-medium transition-all ${
                        devChatMode === "apply"
                          ? "bg-[#FF9B51]/40 text-[#EAEFEF] shadow-sm"
                          : "text-[#EAEFEF]/40 hover:text-[#EAEFEF]/70"
                      }`}
                    >
                      🔧 Apply
                    </button>
                  </div>
                </div>

                <div className="bg-black/20 border border-white/10 rounded-2xl shadow-xl overflow-hidden flex flex-col max-h-[500px]">
                  {/* Chat messages */}
                  <div className="flex-1 overflow-y-auto p-4 space-y-3 custom-scrollbar min-h-[120px]">
                    {devChatMessages.length === 0 && (
                      <div className="text-center text-[#EAEFEF]/30 text-sm py-8">
                        {devChatMode === "apply"
                          ? "Describe a change and the agent will apply it to the codebase."
                          : "Ask the developer anything about the project they just built."}
                      </div>
                    )}
                    {devChatMessages.map((msg, idx) => (
                      <div key={idx} className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}>
                        <div className={`max-w-[85%] rounded-xl px-4 py-2.5 text-sm ${
                          msg.role === "user"
                            ? "bg-[#395370]/40 text-[#EAEFEF] border border-[#395370]/50"
                            : "bg-white/5 text-[#EAEFEF]/90 border border-white/10"
                        }`}>
                          {msg.role === "assistant" ? (
                            <div className="prose prose-invert prose-sm max-w-none prose-p:text-[#EAEFEF]/80 prose-code:text-[#6B9FC4] prose-pre:bg-black/40 prose-pre:border prose-pre:border-white/10">
                              <ReactMarkdown>{msg.content}</ReactMarkdown>
                            </div>
                          ) : (
                            <span>{msg.content}</span>
                          )}
                        </div>
                      </div>
                    ))}
                    {/* Proceed / Cancel bar for pending apply plans */}
                    {pendingApplyTask && !devChatLoading && (
                      <div className="flex gap-2 justify-center py-2">
                        <button
                          onClick={handleApplyProceed}
                          className="px-4 py-2 bg-[#FF9B51]/80 hover:bg-[#FF9B51] text-[#25343F] text-sm font-semibold rounded-lg transition-all active:scale-95 flex items-center gap-1.5 shadow-md"
                        >
                          ▶ Proceed
                        </button>
                        <button
                          onClick={() => { setPendingApplyTask(null); setDevChatMessages(prev => [...prev, { role: "user", content: "✕ Cancelled." }]); }}
                          className="px-4 py-2 bg-white/10 hover:bg-white/20 text-[#EAEFEF]/70 text-sm font-medium rounded-lg transition-all"
                        >
                          Cancel
                        </button>
                      </div>
                    )}
                    {devChatLoading && (
                      <div className="flex justify-start">
                        <div className="bg-white/5 border border-white/10 rounded-xl px-4 py-2.5 text-sm text-[#EAEFEF]/50 flex items-center gap-2">
                          <Loader2 className="w-3 h-3 animate-spin" /> Thinking...
                        </div>
                      </div>
                    )}
                    <div ref={devChatEndRef} />
                  </div>

                  {/* Chat input */}
                  <div className="border-t border-white/5 p-3 space-y-2">
                    {/* File previews */}
                    {devChatFiles.length > 0 && (
                      <div className="flex gap-2 overflow-x-auto custom-scrollbar pb-1">
                        {devChatFiles.map((f, i) => (
                          <div key={i} className="flex items-center gap-2 shrink-0 bg-[#2D4961]/30 border border-[#395370]/50 text-[#EAEFEF] text-xs px-2 py-1 rounded-md">
                            <span className="truncate max-w-[100px]">{f.name}</span>
                            <button onClick={() => setDevChatFiles(prev => prev.filter((_, idx) => idx !== i))} className="text-[#EAEFEF]/60 hover:text-white">&times;</button>
                          </div>
                        ))}
                      </div>
                    )}
                    <div className="flex gap-2">
                      <div className="relative flex-1">
                        <input
                          type="text"
                          value={devChatInput}
                          onChange={(e) => setDevChatInput(e.target.value)}
                          onKeyDown={(e) => {
                            if (e.key === "Enter" && !e.shiftKey && devChatInput.trim() && !devChatLoading) {
                              e.preventDefault();
                              handleDevChat();
                            }
                          }}
                          onPaste={(e) => {
                            const items = e.clipboardData?.items;
                            if (!items) return;
                            for (const item of Array.from(items)) {
                              if (item.type.startsWith("image/")) {
                                const file = item.getAsFile();
                                if (file) {
                                  const named = new File([file], `clipboard-${Date.now()}.png`, { type: file.type });
                                  setDevChatFiles(prev => [...prev, named]);
                                }
                              }
                            }
                          }}
                          placeholder="Ask about the code, design decisions, or improvements..."
                          className="w-full bg-white/5 border border-white/10 rounded-lg pl-3 pr-9 py-2 text-sm text-[#EAEFEF] focus:outline-none focus:ring-1 focus:ring-[#395370]/50 placeholder:text-[#EAEFEF]/30"
                          disabled={devChatLoading}
                        />
                        <input
                          type="file"
                          multiple
                          id="dev-chat-upload"
                          className="hidden"
                          accept="image/*"
                          onChange={(e) => {
                            if (e.target.files) {
                              setDevChatFiles(prev => [...prev, ...Array.from(e.target.files!)]);
                            }
                          }}
                        />
                        <label
                          htmlFor="dev-chat-upload"
                          className="absolute right-2 top-2 text-[#EAEFEF]/40 hover:text-[#395370] cursor-pointer transition-colors"
                          title="Attach screenshots"
                        >
                          <Paperclip className="w-4 h-4" />
                        </label>
                      </div>
                      <button
                        onClick={handleDevChat}
                        disabled={!devChatInput.trim() || devChatLoading}
                        className="px-4 py-2 bg-[#395370]/40 text-[#EAEFEF] hover:bg-[#395370]/60 border border-[#395370]/50 rounded-lg text-sm font-medium transition-colors disabled:opacity-40 flex items-center gap-1.5"
                      >
                        <Send className="w-3.5 h-3.5" />
                      </button>
                    </div>
                  </div>
                </div>
              </motion.div>
            )}
          </AnimatePresence>

        </div>
      </main>
      
      {/* Floating scroll-to-top button */}
      <button
        onClick={() => window.scrollTo({ top: 0, behavior: "smooth" })}
        className="fixed bottom-6 right-6 z-50 w-10 h-10 bg-[#395370]/80 hover:bg-[#395370] text-[#EAEFEF] rounded-full shadow-lg shadow-black/30 flex items-center justify-center transition-all hover:scale-110 active:scale-95 backdrop-blur-sm border border-white/10"
        title="Scroll to top"
      >
        <ChevronUp className="w-5 h-5" />
      </button>

      {/* Global generic custom scrollbar style embedded */}
      <style dangerouslySetInnerHTML={{__html: `
        .custom-scrollbar::-webkit-scrollbar { width: 8px; }
        .custom-scrollbar::-webkit-scrollbar-track { background: transparent; }
        .custom-scrollbar::-webkit-scrollbar-thumb { background: rgba(255,255,255,0.1); border-radius: 4px; }
        .custom-scrollbar::-webkit-scrollbar-thumb:hover { background: rgba(255,255,255,0.2); }
      `}} />
    </div>
  );
}
