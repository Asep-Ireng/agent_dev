import React, { useRef, useEffect, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  TerminalSquare,
  Loader2,
  Brain,
  ChevronDown,
  ChevronRight,
  Terminal as TerminalIcon,
  CheckCircle,
  XCircle,
  AlertTriangle,
  Sparkles,
} from "lucide-react";
import { LogEntry } from "../types";

interface TerminalProps {
  actionLogs: LogEntry[];
  developerLoading: boolean;
  workspacePath: string;
  pendingCommand: string | null;
  rejectReason: string;
  setRejectReason: (r: string) => void;
  handleCommandApproval: (approved: boolean) => void;
  expandedThoughts: Set<number>;
  setExpandedThoughts: React.Dispatch<React.SetStateAction<Set<number>>>;
}

export default function Terminal({
  actionLogs,
  developerLoading,
  workspacePath,
  pendingCommand,
  rejectReason,
  setRejectReason,
  handleCommandApproval,
  expandedThoughts,
  setExpandedThoughts,
}: TerminalProps) {
  const logsEndRef = useRef<HTMLDivElement>(null);
  const [autoScroll, setAutoScroll] = useState(true);
  const [expandedResults, setExpandedResults] = useState<Set<number>>(new Set());

  // Auto-scroll terminal to bottom when new logs arrive (if autoScroll is active)
  useEffect(() => {
    if (autoScroll) {
      logsEndRef.current?.scrollIntoView({ behavior: "smooth" });
    }
  }, [actionLogs, pendingCommand, autoScroll]);

  const handleScroll = (e: React.UIEvent<HTMLDivElement>) => {
    const target = e.currentTarget;
    // Detect if user is scrolled to the bottom (within 20px buffer)
    const isAtBottom = target.scrollHeight - target.scrollTop - target.clientHeight < 20;
    if (isAtBottom && !autoScroll) {
      setAutoScroll(true);
    } else if (!isAtBottom && autoScroll) {
      setAutoScroll(false);
    }
  };

  if (actionLogs.length === 0 && !developerLoading) return null;

  return (
    <AnimatePresence>
      <motion.div
        initial={{ y: 30, opacity: 0, scale: 0.95 }}
        animate={{ y: 0, opacity: 1, scale: 1 }}
        className="space-y-4 pt-8 border-t border-white/5"
      >
        <div className="flex justify-between items-end">
          <div className="flex flex-col">
            <span className="text-[9px] font-mono text-[#E51937] tracking-widest uppercase block mb-1">
              TELEMETRY // AUTONOMOUS_EXECUTION
            </span>
            <div className="flex items-center gap-3">
              <div className="w-8 h-8 rounded-full bg-[#E51937]/10 flex items-center justify-center border border-[#E51937]/20">
                <TerminalSquare className="w-4 h-4 text-[#E51937]" />
              </div>
              <h3 className="text-xl font-bold text-[#F4F4F6] tracking-tight">
                Live Terminal Stream
              </h3>
            </div>
          </div>
          {developerLoading && (
            <div className="flex items-center gap-1.5 font-mono text-xs text-[#E51937] font-semibold tracking-wide animate-pulse">
              <Loader2 className="w-3.5 h-3.5 animate-spin" /> Autonomous Agent Active
            </div>
          )}
        </div>

        {/* Terminal Window Block */}
        <div className="bg-[#0A0A0B] border border-[#F4F4F6]/10 rounded-2xl shadow-2xl overflow-hidden font-mono text-sm leading-relaxed h-[400px] flex flex-col relative">
          {/* Mac style OS header */}
          <div className="flex gap-2 p-3 bg-white/5 border-b border-white/5 items-center">
            <div className="w-3 h-3 rounded-full bg-red-500/80"></div>
            <div className="w-3 h-3 rounded-full bg-yellow-500/80"></div>
            <div className="w-3 h-3 rounded-full bg-green-500/80"></div>
            <div className="mx-auto text-[10px] text-white/30 tracking-widest uppercase truncate max-w-[50%]">
              BASH ~ {workspacePath}
            </div>
          </div>

          {/* Streaming Logs */}
          <div 
            onScroll={handleScroll}
            className="flex-1 overflow-y-auto p-4 space-y-2 custom-scrollbar text-[#F4F4F6]/80"
          >
            {actionLogs.map((log, idx) => {
              switch (log.type) {
                case "thought":
                  const isExpanded = expandedThoughts.has(idx);
                  return (
                    <div key={idx} className="group">
                      <button
                        onClick={() =>
                          setExpandedThoughts((prev) => {
                            const next = new Set(prev);
                            next.has(idx) ? next.delete(idx) : next.add(idx);
                            return next;
                          })
                        }
                        className="flex items-center gap-2 text-[#F4F4F6]/40 hover:text-[#F4F4F6]/70 transition-colors text-xs w-full text-left"
                      >
                        <Brain className="w-3 h-3 shrink-0" />
                        {isExpanded ? (
                          <ChevronDown className="w-3 h-3 shrink-0" />
                        ) : (
                          <ChevronRight className="w-3 h-3 shrink-0" />
                        )}
                        <span className="font-medium">Agent Thinking</span>
                        {!isExpanded && (
                          <span className="truncate opacity-60 ml-1">
                            {log.text.slice(0, 80)}...
                          </span>
                        )}
                      </button>
                      {isExpanded && (
                        <div className="ml-5 mt-1 pl-3 border-l border-[#F4F4F6]/10 text-[#F4F4F6]/50 text-xs whitespace-pre-wrap leading-relaxed">
                          {log.text}
                        </div>
                      )}
                    </div>
                  );

                case "model_thinking":
                  const isThinkingExpanded = expandedThoughts.has(idx);
                  return (
                    <div key={idx} className="group">
                      <button
                        onClick={() =>
                          setExpandedThoughts((prev) => {
                            const next = new Set(prev);
                            next.has(idx) ? next.delete(idx) : next.add(idx);
                            return next;
                          })
                        }
                        className="flex items-center gap-2 text-purple-400/70 hover:text-purple-400 transition-colors text-xs w-full text-left"
                      >
                        <Brain className="w-3 h-3 shrink-0" />
                        {isThinkingExpanded ? (
                          <ChevronDown className="w-3 h-3 shrink-0" />
                        ) : (
                          <ChevronRight className="w-3 h-3 shrink-0" />
                        )}
                        <span className="font-medium">Model Internal Thinking</span>
                        {!isThinkingExpanded && (
                          <span className="truncate opacity-60 ml-1">
                            {log.text.slice(0, 80)}...
                          </span>
                        )}
                      </button>
                      {isThinkingExpanded && (
                        <div className="ml-5 mt-1 pl-3 border-l-2 border-purple-500/30 text-purple-400/80 text-xs whitespace-pre-wrap leading-relaxed overflow-x-auto">
                          {log.text}
                        </div>
                      )}
                    </div>
                  );

                case "tool_call":
                  return (
                    <div key={idx} className="mt-3 flex items-center gap-2">
                      <TerminalIcon className="w-3.5 h-3.5 text-green-400 shrink-0" />
                      <span className="text-green-400 text-xs font-semibold uppercase tracking-wider">
                        Using Tool:
                      </span>
                      <span className="text-green-300 text-sm font-medium">
                        {log.tool}
                      </span>
                    </div>
                  );

                case "tool_input":
                  return (
                    <div
                      key={idx}
                      className="ml-5 bg-white/5 border border-white/10 rounded-lg p-2 font-mono text-xs text-[#F4F4F6]/70 whitespace-pre-wrap break-all max-h-32 overflow-y-auto custom-scrollbar"
                    >
                      {log.input}
                    </div>
                  );

                case "tool_result":
                  const isResultExpanded = expandedResults.has(idx);
                  return (
                    <div
                      key={idx}
                      onClick={(e) => {
                        const selection = window.getSelection();
                        if (selection && selection.toString()) return;
                        
                        if (
                          (e.target as HTMLElement).closest(".stdout-container") ||
                          (e.target as HTMLElement).closest(".stderr-container")
                        ) {
                          return;
                        }
                        
                        setAutoScroll(false);
                        setExpandedResults((prev) => {
                          const next = new Set(prev);
                          next.has(idx) ? next.delete(idx) : next.add(idx);
                          return next;
                        });
                      }}
                      className={`ml-5 mb-2 rounded-lg border overflow-hidden transition-all duration-200 cursor-pointer hover:bg-white/[0.02] ${
                        log.success
                          ? "border-green-500/30"
                          : "border-red-500/40"
                      }`}
                    >
                      {/* Result header */}
                      <div
                        className={`flex items-center gap-2 px-3 py-1.5 text-xs select-none ${
                          log.success
                            ? "bg-green-500/10 text-green-400"
                            : "bg-red-500/10 text-red-400"
                        }`}
                      >
                        {log.success ? (
                          <CheckCircle className="w-3 h-3 shrink-0" />
                        ) : (
                          <XCircle className="w-3 h-3 shrink-0" />
                        )}
                        <span className="font-semibold">
                          {log.success ? "SUCCESS" : "FAILED"}
                        </span>
                        {log.tool === "terminal" && log.exit_code !== null && (
                          <span className="opacity-60 shrink-0">
                            Exit code {log.exit_code}
                          </span>
                        )}
                        
                        <span className="opacity-40 text-[9px] uppercase font-mono tracking-wider ml-2 shrink-0">
                          {isResultExpanded ? "[- Collapse]" : "[+ Expand details]"}
                        </span>

                        {log.cwd && (
                          <span className="ml-auto bg-black/30 px-2 py-0.5 rounded text-[10px] text-[#F4F4F6]/50 font-mono truncate max-w-[200px]">
                            {log.cwd}
                          </span>
                        )}
                      </div>
                      {/* Command */}
                      {log.cmd && (
                        <div className="px-3 py-1.5 bg-black/30 border-b border-white/5 font-mono text-xs text-green-400 select-none">
                          $ {log.cmd}
                        </div>
                      )}
                      
                      {/* Output containers (expanded only) */}
                      <AnimatePresence initial={false}>
                        {isResultExpanded && (
                          <motion.div
                            initial={{ height: 0, opacity: 0 }}
                            animate={{ height: "auto", opacity: 1 }}
                            exit={{ height: 0, opacity: 0 }}
                            transition={{ duration: 0.2 }}
                            className="overflow-hidden"
                          >
                            {/* Stdout */}
                            {log.stdout && (
                              <div className="stdout-container px-3 py-2 font-mono text-[11px] text-[#F4F4F6]/70 whitespace-pre-wrap max-h-48 overflow-y-auto custom-scrollbar bg-black/20">
                                {log.stdout}
                              </div>
                            )}
                            {/* Stderr */}
                            {log.stderr && (
                              <div className="stderr-container px-3 py-2 font-mono text-[11px] text-red-400/80 whitespace-pre-wrap max-h-32 overflow-y-auto custom-scrollbar bg-red-500/5 border-t border-red-500/20">
                                {log.stderr}
                              </div>
                            )}
                          </motion.div>
                        )}
                      </AnimatePresence>
                    </div>
                  );

                case "final_answer":
                  return (
                    <div
                      key={idx}
                      className="mt-3 bg-[#E51937]/20 border border-[#E51937]/40 rounded-lg p-3"
                    >
                      <div className="flex items-center gap-2 text-xs text-[#E51937] font-semibold mb-1">
                        <Sparkles className="w-3 h-3" /> Agent Summary
                      </div>
                      <div className="text-sm text-[#F4F4F6]/90 whitespace-pre-wrap">
                        {log.text}
                      </div>
                    </div>
                  );

                case "system":
                  const colorMap = {
                    info: "text-blue-400",
                    warn: "text-yellow-400",
                    error: "text-red-400",
                  };
                  const bgMap = {
                    info: "bg-blue-500/5",
                    warn: "bg-yellow-500/5",
                    error: "bg-red-500/10",
                  };
                  return (
                    <div
                      key={idx}
                      className={`flex items-center gap-2 px-2 py-1 rounded text-xs font-medium ${
                        colorMap[log.level]
                      } ${bgMap[log.level]} mt-1`}
                    >
                      {log.level === "error" ? (
                        <XCircle className="w-3 h-3" />
                      ) : log.level === "warn" ? (
                        <AlertTriangle className="w-3 h-3" />
                      ) : (
                        <TerminalSquare className="w-3 h-3" />
                      )}
                      {log.text}
                    </div>
                  );

                case "log":
                  return (
                    <div
                      key={idx}
                      className="text-xs text-[#F4F4F6]/50 whitespace-pre-wrap pl-2"
                    >
                      {log.text}
                    </div>
                  );

                case "cmd_start":
                  return (
                    <div
                      key={idx}
                      className="mt-3 bg-black/30 border border-white/10 rounded-lg overflow-hidden"
                    >
                      <div className="flex items-center gap-2 px-3 py-1.5">
                        <TerminalIcon className="w-3 h-3 text-green-400" />
                        <span className="text-green-400 font-mono text-xs font-medium">
                          $ {log.cmd}
                        </span>
                        <span className="ml-auto bg-black/30 px-2 py-0.5 rounded text-[10px] text-[#F4F4F6]/40 font-mono">
                          {log.cwd}
                        </span>
                      </div>
                    </div>
                  );

                case "cmd_output":
                  return (
                    <div
                      key={idx}
                      className={`pl-5 font-mono text-[11px] whitespace-pre-wrap ${
                        log.stream === "stderr"
                          ? "text-red-400/70"
                          : "text-[#F4F4F6]/60"
                      }`}
                    >
                      {log.line}
                    </div>
                  );

                case "cmd_end":
                  return (
                    <div
                      key={idx}
                      className={`pl-5 flex items-center gap-1.5 text-[10px] font-medium mt-0.5 mb-1 ${
                        log.success ? "text-green-500/70" : "text-red-400"
                      }`}
                    >
                      {log.success ? (
                        <CheckCircle className="w-2.5 h-2.5" />
                      ) : (
                        <XCircle className="w-2.5 h-2.5" />
                      )}
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
                className="sticky bottom-4 mx-4 bg-[#E51937]/20 border border-[#E51937]/50 backdrop-blur-md rounded-xl p-4 shadow-2xl z-10"
              >
                <div className="flex items-start gap-3">
                  <AlertTriangle className="w-5 h-5 text-yellow-500 shrink-0 mt-0.5" />
                  <div className="flex-1">
                    <h4 className="text-sm font-semibold text-[#F4F4F6]">
                      Action Required
                    </h4>
                    <p className="text-xs text-[#F4F4F6]/70 mt-1 mb-3">
                      The agent wants to execute the following operation:
                    </p>
                    <div className="bg-black/50 p-2 rounded border border-[#F4F4F6]/10 font-mono text-[10px] text-green-400 break-all mb-4 whitespace-pre-wrap max-h-40 overflow-y-auto custom-scrollbar">
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

          {/* Resume Auto-Scroll Button */}
          <AnimatePresence>
            {!autoScroll && (
              <div className="absolute bottom-4 right-4 z-20">
                <motion.button
                  initial={{ opacity: 0, y: 10, scale: 0.9 }}
                  animate={{ opacity: 1, y: 0, scale: 1 }}
                  exit={{ opacity: 0, y: 10, scale: 0.9 }}
                  onClick={(e) => {
                    e.stopPropagation();
                    setAutoScroll(true);
                    logsEndRef.current?.scrollIntoView({ behavior: "smooth" });
                  }}
                  className="flex items-center gap-1.5 px-3 py-1.5 bg-[#E51937] hover:bg-[#E51937]/90 text-[#0F0F11] font-semibold font-mono text-[11px] rounded-full shadow-lg shadow-black/60 transition-all active:scale-95 border border-[#E51937]/35 animate-none"
                >
                  <ChevronDown className="w-3.5 h-3.5" /> Resume Auto-Scroll
                </motion.button>
              </div>
            )}
          </AnimatePresence>
        </div>
      </motion.div>
    </AnimatePresence>
  );
}
