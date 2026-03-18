import React, { useRef, useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Code2, Send, Paperclip, Loader2 } from "lucide-react";
import ReactMarkdown from "react-markdown";

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
}: DevChatProps) {
  const devChatEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    devChatEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [devChatMessages]);

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
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-full bg-gradient-to-br from-[#2D4961] to-[#395370] flex items-center justify-center shadow-lg shadow-[#2D4961]/30">
            <Code2 className="w-4 h-4 text-white" />
          </div>
          <h3 className="text-xl font-medium text-[#EAEFEF]">
            Chat with Developer
          </h3>
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
              <div
                key={idx}
                className={`flex ${
                  msg.role === "user" ? "justify-end" : "justify-start"
                }`}
              >
                <div
                  className={`max-w-[85%] rounded-xl px-4 py-2.5 text-sm ${
                    msg.role === "user"
                      ? "bg-[#395370]/40 text-[#EAEFEF] border border-[#395370]/50"
                      : "bg-white/5 text-[#EAEFEF]/90 border border-white/10"
                  }`}
                >
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
                  onClick={() => {
                    setPendingApplyTask(null);
                    setDevChatMessages((prev) => [
                      ...prev,
                      { role: "user", content: "✕ Cancelled." },
                    ]);
                  }}
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
                  <div
                    key={i}
                    className="flex items-center gap-2 shrink-0 bg-[#2D4961]/30 border border-[#395370]/50 text-[#EAEFEF] text-xs px-2 py-1 rounded-md"
                  >
                    <span className="truncate max-w-[100px]">{f.name}</span>
                    <button
                      onClick={() =>
                        setDevChatFiles((prev) =>
                          prev.filter((_, idx) => idx !== i)
                        )
                      }
                      className="text-[#EAEFEF]/60 hover:text-white"
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
                      setDevChatFiles((prev) => [
                        ...prev,
                        ...Array.from(e.target.files!),
                      ]);
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
    </AnimatePresence>
  );
}
