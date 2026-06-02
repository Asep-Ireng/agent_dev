import React, { useState } from "react";
import ReactMarkdown from "react-markdown";
import { motion, AnimatePresence } from "framer-motion";
import { Sparkles, Box, Loader2, Paperclip, Send, Brain, ChevronDown, ChevronUp } from "lucide-react";
import ModelPicker from "./ModelPicker";

interface DesignChatProps {
  chatHistory: { role: "user" | "agent"; content: string }[];
  currentMessage: string;
  setCurrentMessage: (msg: string) => void;
  attachedFiles: File[];
  setAttachedFiles: React.Dispatch<React.SetStateAction<File[]>>;
  designerLoading: boolean;
  handleChatSubmit: () => void;
  thinkingText?: string;
  model: string;
  provider: string;
  updateBackendSettings: (provider?: string, model?: string, thinkingLevel?: string) => void;
}

export default function DesignChat({
  chatHistory,
  currentMessage,
  setCurrentMessage,
  attachedFiles,
  setAttachedFiles,
  designerLoading,
  handleChatSubmit,
  thinkingText = "",
  model,
  provider,
  updateBackendSettings,
}: DesignChatProps) {
  const [showThinking, setShowThinking] = useState(false);
  const hasThinking = thinkingText.length > 0;
  return (
    <div className="flex flex-col bg-black/20 border border-[#F4F4F6]/5 rounded-2xl shadow-xl overflow-hidden h-full">
      <div className="p-4 bg-gradient-to-r from-[#E51937]/15 to-[#E51937]/5 border-b border-[#F4F4F6]/5 relative">
        <div className="absolute right-4 top-4 font-mono text-[9px] text-[#E51937]/60 tracking-wider hidden sm:block">
          SYS // LEAD_DESIGNER
        </div>
        <span className="text-[9px] font-mono text-[#E51937] tracking-widest uppercase block mb-0.5">
          PHASE 01 // ARCHITECTURE_PLANNING
        </span>
        <h3 className="text-lg font-bold text-[#F4F4F6] flex items-center gap-2 tracking-tight">
          <Sparkles className="w-4 h-4 text-[#E51937]" /> Chat with Lead Designer
        </h3>
        <p className="text-xs text-[#F4F4F6]/50 mt-1">
          Start by describing your app. Attach PDFs or Images.
        </p>
      </div>

      <div className="flex-1 overflow-y-auto p-4 space-y-4 custom-scrollbar">
        {chatHistory.length === 0 && (
          <div className="h-full flex flex-col items-center justify-center text-[#F4F4F6]/30 space-y-3">
            <Box className="w-8 h-8 opacity-50" />
            <p className="text-sm">No messages yet. Tell me what to build!</p>
          </div>
        )}
        {chatHistory.map((msg, idx) => (
          <div
            key={idx}
            className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}
          >
            <div
              className={`max-w-[80%] rounded-2xl px-4 py-2 text-sm ${msg.role === "user"
                  ? "bg-[#E51937] text-[#0F0F11] font-medium selection:bg-white selection:text-[#0F0F11]"
                  : "bg-white/5 border border-white/10 text-[#F4F4F6]/90"
                }`}
            >
              {msg.role === "agent" ? (
                <div className="prose prose-sm prose-invert max-w-none">
                  <ReactMarkdown>{msg.content}</ReactMarkdown>
                </div>
              ) : (
                msg.content
              )}
            </div>
          </div>
        ))}
        {designerLoading && (
          <div className="flex flex-col gap-2">
            <div className="flex justify-start items-center gap-2">
              <div className="max-w-[80%] rounded-2xl px-4 py-2 text-sm bg-white/5 border border-white/10 text-[#F4F4F6]/60 flex items-center gap-2">
                <Loader2 className="w-4 h-4 animate-spin" /> Rethinking
                architecture...
              </div>
              {/* Thinking button — always visible during loading */}
              <button
                onClick={() => setShowThinking((v) => !v)}
                title={showThinking ? "Hide thinking" : "Show model thinking"}
                className={`relative flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg border text-[11px] font-semibold transition-all duration-200 shrink-0
                  ${showThinking
                    ? "bg-purple-500/20 border-purple-500/40 text-purple-300"
                    : "bg-white/5 border-white/10 text-[#F4F4F6]/30 hover:text-purple-300 hover:border-purple-500/30 hover:bg-purple-500/10"
                  }`}
              >
                <Brain className="w-3 h-3" />
                {showThinking ? <ChevronUp className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />}
                {hasThinking && (
                  <span className="absolute -top-1 -right-1 flex h-2 w-2">
                    <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-purple-400 opacity-75" />
                    <span className="relative inline-flex rounded-full h-2 w-2 bg-purple-400" />
                  </span>
                )}
              </button>
            </div>

            {/* Inline thinking panel */}
            <AnimatePresence>
              {showThinking && hasThinking && (
                <motion.div
                  initial={{ opacity: 0, height: 0 }}
                  animate={{ opacity: 1, height: "auto" }}
                  exit={{ opacity: 0, height: 0 }}
                  transition={{ duration: 0.2 }}
                  className="overflow-hidden ml-2"
                >
                  <div className="border border-purple-500/20 bg-purple-900/10 rounded-xl p-3 max-h-48 overflow-y-auto custom-scrollbar">
                    <div className="flex items-center gap-1.5 mb-2">
                      <Brain className="w-3 h-3 text-purple-400" />
                      <span className="text-[9px] font-mono text-purple-400/60 uppercase tracking-widest">Model Internal Thinking</span>
                    </div>
                    <p className="text-[11px] font-mono text-purple-200/60 whitespace-pre-wrap leading-relaxed">
                      {thinkingText}
                      <span className="inline-block w-1.5 h-3 bg-purple-400/60 ml-0.5 animate-pulse rounded-sm align-middle" />
                    </p>
                  </div>
                </motion.div>
              )}
            </AnimatePresence>
          </div>
        )}
      </div>

      <div className="p-4 bg-[#0A0A0B]/50 border-t border-[#F4F4F6]/5 space-y-3">
        {/* File Previews */}
        {attachedFiles.length > 0 && (
          <div className="flex gap-2 mx-2 overflow-x-auto custom-scrollbar pb-2">
            {attachedFiles.map((f, i) => (
              <div
                key={i}
                className="flex items-center gap-2 shrink-0 bg-[#E51937]/30 border border-[#E51937]/50 text-[#F4F4F6] text-xs px-2 py-1 rounded-md"
              >
                <span className="truncate max-w-[100px]">{f.name}</span>
                <button
                  onClick={() =>
                    setAttachedFiles((prev) =>
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

        <div className="flex items-end gap-2">
          <div className="relative flex-1 group">
            <textarea
              className="w-full bg-[#1A1A1D] border border-[#F4F4F6]/10 rounded-xl pl-4 pr-10 py-3 text-sm text-[#F4F4F6] focus:outline-none focus:ring-2 focus:ring-[#E51937]/50 transition-all resize-none shadow-inner"
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
                      const named = new File(
                        [file],
                        `clipboard-${Date.now()}.png`,
                        { type: file.type }
                      );
                      setAttachedFiles((prev) => [...prev, named]);
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
                  setAttachedFiles((prev) => [
                    ...prev,
                    ...Array.from(e.target.files!),
                  ]);
                }
              }}
            />
            <label
              htmlFor="file-upload"
              className="absolute right-3 top-3 text-[#F4F4F6]/40 hover:text-[#E51937] cursor-pointer transition-colors"
              title="Attach PDFs or Images"
            >
              <Paperclip className="w-5 h-5" />
            </label>
          </div>

          <ModelPicker
            model={model}
            provider={provider}
            updateBackendSettings={updateBackendSettings}
            className="h-11"
          />

          <button
            onClick={handleChatSubmit}
            disabled={designerLoading}
            className="p-3 bg-gradient-to-r from-[#E51937] to-[#FF4D6A] text-[#F4F4F6] rounded-xl hover:brightness-110 transition-all active:scale-95 disabled:opacity-50 shadow-lg shadow-[#E51937]/30 shrink-0"
          >
            <Send className="w-5 h-5" />
          </button>
        </div>
      </div>
    </div>
  );
}
