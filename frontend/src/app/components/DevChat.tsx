import React, { useRef, useEffect, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Code2, Send, Paperclip, Loader2, ChevronDown, ChevronRight, Eye } from "lucide-react";
import ReactMarkdown from "react-markdown";
import dynamic from "next/dynamic";
import ModelPicker from "./ModelPicker";

const PatchDiff = dynamic(
  () => import("@pierre/diffs/react").then((mod) => mod.PatchDiff),
  { ssr: false }
);

interface DevChatProps {
  devChatMessages: { role: string; content: string }[];
  devChatInput: string;
  setDevChatInput: (s: string) => void;
  devChatLoading: boolean;
  devChatFiles: File[];
  setDevChatFiles: React.Dispatch<React.SetStateAction<File[]>>;
  devChatMode: "ask" | "apply";
  setDevChatMode: (m: "ask" | "apply") => void;
  pendingApplyTask: string | null;
  setPendingApplyTask: (t: string | null) => void;
  agentResult: string;
  developerLoading: boolean;
  handleDevChat: () => void;
  handleApplyProceed: () => void;
  setDevChatMessages: React.Dispatch<
    React.SetStateAction<{ role: string; content: string }[]>
  >;
  workspaceDiff: string;
  fetchWorkspaceDiff: () => void;
  totalTokens: { prompt: number; completion: number; total: number };
  model: string;
  provider: string;
  updateBackendSettings: (provider?: string, model?: string, thinkingLevel?: string) => void;
}

export default function DevChat({
  devChatMessages,
  devChatInput,
  setDevChatInput,
  devChatLoading,
  devChatFiles,
  setDevChatFiles,
  devChatMode,
  setDevChatMode,
  pendingApplyTask,
  setPendingApplyTask,
  agentResult,
  developerLoading,
  handleDevChat,
  handleApplyProceed,
  setDevChatMessages,
  workspaceDiff,
  fetchWorkspaceDiff,
  totalTokens,
  model,
  provider,
  updateBackendSettings,
}: DevChatProps) {
  const devChatEndRef = useRef<HTMLDivElement>(null);
  const [isDiffExpanded, setIsDiffExpanded] = useState(false);

  useEffect(() => {
    devChatEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [devChatMessages]);

  useEffect(() => {
    fetchWorkspaceDiff();
  }, []);

  if (!agentResult || developerLoading) return null;

  return (
    <AnimatePresence>
      <motion.div
        initial={{ y: 30, opacity: 0, scale: 0.95 }}
        animate={{ y: 0, opacity: 1, scale: 1 }}
        exit={{ opacity: 0, scale: 0.95 }}
        transition={{ duration: 0.4, ease: "easeOut", delay: 0.15 }}
        className="space-y-4 pt-8 border-t border-white/5"
      >
        <div className="flex justify-between items-end">
          <div className="flex flex-col">
            <span className="text-[9px] font-mono text-[#E51937] tracking-widest uppercase block mb-1">
              SYS // COMPILER_TUNING {totalTokens.total > 0 && `// TOKENS: ${totalTokens.total.toLocaleString()} (P: ${totalTokens.prompt.toLocaleString()} | C: ${totalTokens.completion.toLocaleString()})`}
            </span>
            <div className="flex items-center gap-3">
              <div className="w-8 h-8 rounded-full bg-[#E51937]/10 flex items-center justify-center border border-[#E51937]/20">
                <Code2 className="w-4 h-4 text-[#E51937]" />
              </div>
              <h3 className="text-xl font-bold text-[#F4F4F6] tracking-tight">
                Chat with Developer
              </h3>
            </div>
          </div>
          <div className="flex gap-1 bg-black/35 rounded-lg p-0.5 border border-white/5">
            <button
              onClick={() => setDevChatMode("ask")}
              className={`px-3 py-1 rounded-md text-xs font-medium transition-all ${
                devChatMode === "ask"
                  ? "bg-[#27272a]/60 text-[#F4F4F6] shadow-sm"
                  : "text-[#F4F4F6]/40 hover:text-[#F4F4F6]/70"
              }`}
            >
              💬 Ask
            </button>
            <button
              onClick={() => setDevChatMode("apply")}
              className={`px-3 py-1 rounded-md text-xs font-medium transition-all ${
                devChatMode === "apply"
                  ? "bg-[#E51937]/40 text-[#F4F4F6] shadow-sm"
                  : "text-[#F4F4F6]/40 hover:text-[#F4F4F6]/70"
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
              <div className="text-center text-[#F4F4F6]/30 text-sm py-8">
                {devChatMode === "apply"
                  ? "Describe a change and the agent will apply it to the codebase."
                  : "Ask the developer anything about the project they just built."}
              </div>
            )}
            {devChatMessages.map((msg, idx) => (
              <div
                key={idx}
                className={`flex ${
                  msg.role === "user" ? "justify-end" : "justify-start"
                }`}
              >
                <div
                  className={`max-w-[85%] rounded-xl px-4 py-2.5 text-sm ${
                    msg.role === "user"
                      ? "bg-[#27272a]/40 text-[#F4F4F6] border border-[#27272a]/50"
                      : "bg-white/5 text-[#F4F4F6]/90 border border-white/10"
                  }`}
                >
                  {msg.role === "assistant" ? (
                    <div className="prose prose-invert prose-sm max-w-none prose-p:text-[#F4F4F6]/80 prose-code:text-[#6B9FC4] prose-pre:bg-black/40 prose-pre:border prose-pre:border-white/10">
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
                  className="px-4 py-2 bg-[#E51937]/80 hover:bg-[#E51937] text-[#0F0F11] text-sm font-semibold rounded-lg transition-all active:scale-95 flex items-center gap-1.5 shadow-md"
                >
                  ▶ Proceed
                </button>
                <button
                  onClick={() => {
                    setPendingApplyTask(null);
                    setDevChatMessages((prev) => [
                      ...prev,
                      { role: "user", content: "✕ Cancelled." },
                    ]);
                  }}
                  className="px-4 py-2 bg-white/10 hover:bg-white/20 text-[#F4F4F6]/70 text-sm font-medium rounded-lg transition-all"
                >
                  Cancel
                </button>
              </div>
            )}
            {devChatLoading && (
              <div className="flex justify-start">
                <div className="bg-white/5 border border-white/10 rounded-xl px-4 py-2.5 text-sm text-[#F4F4F6]/50 flex items-center gap-2">
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
                  <div
                    key={i}
                    className="flex items-center gap-2 shrink-0 bg-[#1F1F23]/30 border border-[#27272a]/50 text-[#F4F4F6] text-xs px-2 py-1 rounded-md"
                  >
                    <span className="truncate max-w-[100px]">{f.name}</span>
                    <button
                      onClick={() =>
                        setDevChatFiles((prev) =>
                          prev.filter((_, idx) => idx !== i)
                        )
                      }
                      className="text-[#F4F4F6]/60 hover:text-white"
                    >
                      &times;
                    </button>
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
                    if (
                      e.key === "Enter" &&
                      !e.shiftKey &&
                      devChatInput.trim() &&
                      !devChatLoading
                    ) {
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
                          const named = new File(
                            [file],
                            `clipboard-${Date.now()}.png`,
                            { type: file.type }
                          );
                          setDevChatFiles((prev) => [...prev, named]);
                        }
                      }
                    }
                  }}
                  placeholder="Ask about the code, design decisions, or improvements..."
                  className="w-full bg-white/5 border border-white/10 rounded-lg pl-3 pr-9 py-2 text-sm text-[#F4F4F6] focus:outline-none focus:ring-1 focus:ring-[#27272a]/50 placeholder:text-[#F4F4F6]/30"
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
                      setDevChatFiles((prev) => [
                        ...prev,
                        ...Array.from(e.target.files!),
                      ]);
                    }
                  }}
                />
                <label
                  htmlFor="dev-chat-upload"
                  className="absolute right-2 top-2 text-[#F4F4F6]/40 hover:text-[#27272a] cursor-pointer transition-colors"
                  title="Attach screenshots"
                >
                  <Paperclip className="w-4 h-4" />
                </label>
              </div>
              <ModelPicker
                model={model}
                provider={provider}
                updateBackendSettings={updateBackendSettings}
                className="h-[38px]"
              />
              <button
                onClick={handleDevChat}
                disabled={!devChatInput.trim() || devChatLoading}
                className="px-4 py-2 bg-[#27272a]/40 text-[#F4F4F6] hover:bg-[#27272a]/60 border border-[#27272a]/50 rounded-lg text-sm font-medium transition-colors disabled:opacity-40 flex items-center gap-1.5"
              >
                <Send className="w-3.5 h-3.5" />
              </button>
            </div>
          </div>
        </div>

        {workspaceDiff && (
          <div className="bg-black/20 border border-white/10 rounded-2xl overflow-hidden flex flex-col mt-4">
            <button
              onClick={() => setIsDiffExpanded(!isDiffExpanded)}
              className="w-full flex items-center justify-between px-4 py-3 bg-white/5 hover:bg-white/[0.08] transition-colors text-left cursor-pointer"
            >
              <div className="flex items-center gap-2">
                <Eye className="w-4 h-4 text-[#E51937]" />
                <span className="font-mono text-xs font-bold text-[#F4F4F6] uppercase tracking-wider">
                  Code Diff Review
                </span>
                <span className="bg-[#E51937]/10 text-[#E51937] text-[10px] px-1.5 py-0.5 rounded font-mono border border-[#E51937]/20 font-semibold">
                  unstaged modifications
                </span>
              </div>
              <div className="flex items-center gap-1.5 text-xs text-[#F4F4F6]/50">
                {isDiffExpanded ? (
                  <>
                    <span>Hide Diff</span>
                    <ChevronDown className="w-4 h-4" />
                  </>
                ) : (
                  <>
                    <span>Show Diff</span>
                    <ChevronRight className="w-4 h-4" />
                  </>
                )}
              </div>
            </button>

            <AnimatePresence>
              {isDiffExpanded && (
                <motion.div
                  initial={{ height: 0, opacity: 0 }}
                  animate={{ height: "auto", opacity: 1 }}
                  exit={{ height: 0, opacity: 0 }}
                  className="border-t border-white/5 overflow-hidden"
                >
                  <div className="p-4 bg-black/40 max-h-[400px] overflow-y-auto custom-scrollbar font-mono text-xs">
                    <PatchDiff patch={workspaceDiff} />
                  </div>
                </motion.div>
              )}
            </AnimatePresence>
          </div>
        )}
      </motion.div>
    </AnimatePresence>
  );
}
