"use client";

import React, { useEffect, useRef } from "react";
import { motion } from "framer-motion";
import { Brain, Sparkles, Loader2, X } from "lucide-react";

interface ThinkingPanelProps {
  thinkingText: string;
  isActive: boolean;
  onClose: () => void;
}

export default function ThinkingPanel({
  thinkingText,
  isActive,
  onClose,
}: ThinkingPanelProps) {
  const bottomRef = useRef<HTMLDivElement>(null);

  // Auto-scroll to latest tokens
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [thinkingText]);

  return (
    <motion.div
      initial={{ opacity: 0, x: 24, flexGrow: 0, flexShrink: 1, flexBasis: "0%" }}
      animate={{ opacity: 1, x: 0, flexGrow: 2, flexShrink: 1, flexBasis: "0%" }}
      exit={{ opacity: 0, x: 24, flexGrow: 0, flexShrink: 1, flexBasis: "0%" }}
      transition={{ type: "spring", stiffness: 340, damping: 30 }}
      className="min-w-0 flex flex-col overflow-hidden"
    >
      {/* Panel mirror-header — visually aligns with terminal header below */}
      <div className="flex items-center gap-2.5 mb-4 h-[28px]">
        <div
          className={`w-8 h-8 rounded-full flex items-center justify-center border transition-all ${
            isActive
              ? "bg-purple-500/15 border-purple-500/30"
              : "bg-purple-500/5 border-purple-500/10"
          }`}
        >
          <Brain
            className={`w-4 h-4 transition-colors ${
              isActive ? "text-purple-400" : "text-purple-400/40"
            }`}
          />
        </div>
        <div className="flex flex-col">
          <span className="text-[9px] font-mono text-purple-500/60 tracking-widest uppercase block leading-none mb-0.5">
            EXTENDED THINKING
          </span>
          <h3 className="text-xl font-bold text-[#F4F4F6] tracking-tight leading-none">
            Model Reasoning
          </h3>
        </div>
        {isActive && (
          <div className="ml-auto flex items-center gap-1.5 font-mono text-xs text-purple-400/70 font-semibold tracking-wide">
            <Loader2 className="w-3 h-3 animate-spin" />
            <span className="animate-pulse text-[10px]">STREAMING</span>
          </div>
        )}
        {/* Close button */}
        <button
          onClick={onClose}
          title="Close thinking panel"
          className="ml-auto flex items-center justify-center w-7 h-7 rounded-lg bg-white/5 border border-white/10 text-[#F4F4F6]/30 hover:text-[#F4F4F6]/80 hover:bg-white/10 transition-all"
        >
          <X className="w-3.5 h-3.5" />
        </button>
      </div>

      {/* Panel window — matches terminal height exactly */}
      <div className="bg-[#0A0A0B] border border-purple-500/20 rounded-2xl shadow-2xl shadow-purple-900/10 overflow-hidden font-mono text-sm leading-relaxed h-[400px] flex flex-col relative">
        {/* Mac-style bar */}
        <div className="flex gap-2 p-3 bg-purple-900/10 border-b border-purple-500/10 items-center">
          <div className="w-3 h-3 rounded-full bg-purple-500/30" />
          <div className="w-3 h-3 rounded-full bg-purple-500/20" />
          <div className="w-3 h-3 rounded-full bg-purple-500/10" />
          <div className="mx-auto text-[10px] text-purple-400/30 tracking-widest uppercase">
            THINKING // INTERNAL REASONING
          </div>
        </div>

        {/* Thinking text stream */}
        <div className="flex-1 overflow-y-auto p-4 custom-scrollbar">
          {thinkingText ? (
            <p className="text-[11px] text-purple-200/60 whitespace-pre-wrap leading-relaxed">
              {thinkingText}
              {isActive && (
                <span className="inline-block w-1.5 h-3 bg-purple-400/70 ml-0.5 animate-pulse rounded-sm align-middle" />
              )}
            </p>
          ) : (
            <div className="h-full flex flex-col items-center justify-center gap-3 text-purple-400/20">
              <Sparkles className="w-8 h-8" />
              <p className="text-xs font-mono text-center">
                {isActive
                  ? "Waiting for thinking tokens..."
                  : "No thinking tokens yet.\nEnable a thinking model in settings."}
              </p>
            </div>
          )}
          <div ref={bottomRef} />
        </div>

        {/* Footer stats */}
        {thinkingText && (
          <div className="px-4 py-2 border-t border-purple-500/10 bg-purple-900/5 flex justify-between items-center shrink-0">
            <span className="text-[9px] font-mono text-purple-400/30 uppercase tracking-widest">
              {thinkingText.length.toLocaleString()} chars
            </span>
            <span className="text-[9px] font-mono text-purple-400/20 uppercase tracking-widest">
              ~{Math.ceil(thinkingText.length / 4).toLocaleString()} tokens est.
            </span>
          </div>
        )}
      </div>
    </motion.div>
  );
}
