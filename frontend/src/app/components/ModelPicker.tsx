"use client";

import React, { useState, useRef, useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { ChevronDown, Zap, Brain, Cpu, Check, Sparkles } from "lucide-react";

interface ModelPickerProps {
  provider: string;
  model: string;
  updateBackendSettings: (provider?: string, model?: string, thinkingLevel?: string) => void;
  className?: string;
}

const GOOGLE_MODELS = [
  { id: "gemini-2.5-flash", label: "Gemini 2.5 Flash", desc: "Superfast & smart", icon: Zap, color: "text-rose-400", activeBg: "bg-rose-500/10 border-rose-500/20 text-rose-300" },
  { id: "gemini-2.5-pro", label: "Gemini 2.5 Pro", desc: "Complex logic & coding", icon: Brain, color: "text-purple-400", activeBg: "bg-purple-500/10 border-purple-500/20 text-purple-300" },
  { id: "gemini-2.0-flash", label: "Gemini 2.0 Flash", desc: "Legacy fast model", icon: Cpu, color: "text-amber-400", activeBg: "bg-amber-500/10 border-amber-500/20 text-amber-300" },
];

const OPENAI_MODELS = [
  { id: "gpt-4o-mini", label: "GPT-4o Mini", desc: "Fast & highly efficient", icon: Zap, color: "text-emerald-400", activeBg: "bg-emerald-500/10 border-emerald-500/20 text-emerald-300" },
  { id: "gpt-4o", label: "GPT-4o", desc: "Balanced intelligence", icon: Cpu, color: "text-teal-400", activeBg: "bg-teal-500/10 border-teal-500/20 text-teal-300" },
  { id: "o3-mini", label: "o3-mini", desc: "Deep reasoning power", icon: Brain, color: "text-cyan-400", activeBg: "bg-cyan-500/10 border-cyan-500/20 text-cyan-300" },
];

const MODEL_MAP: Record<string, { label: string; short: string; color: string; icon: React.ComponentType<any> }> = {
  "gemini-2.5-flash": { label: "Gemini 2.5 Flash", short: "Flash 2.5", color: "text-rose-400", icon: Zap },
  "gemini-2.5-pro": { label: "Gemini 2.5 Pro", short: "Pro 2.5", color: "text-purple-400", icon: Brain },
  "gemini-2.0-flash": { label: "Gemini 2.0 Flash", short: "Flash 2.0", color: "text-amber-400", icon: Cpu },
  "gpt-4o-mini": { label: "GPT-4o Mini", short: "4o Mini", color: "text-emerald-400", icon: Zap },
  "gpt-4o": { label: "GPT-4o", short: "GPT-4o", color: "text-teal-400", icon: Cpu },
  "o3-mini": { label: "o3-mini", short: "o3-mini", color: "text-cyan-400", icon: Brain },
};

function getModelInfo(modelId: string) {
  return MODEL_MAP[modelId] || {
    label: modelId,
    short: modelId.replace("gemini-", "").replace("gpt-", "").toUpperCase(),
    color: "text-purple-400",
    icon: Cpu,
  };
}

export default function ModelPicker({ provider, model, updateBackendSettings, className }: ModelPickerProps) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  const isGoogle = provider === "Google (Gemini)";
  const models = isGoogle ? GOOGLE_MODELS : OPENAI_MODELS;
  const currentModelInfo = getModelInfo(model);
  const ModelIcon = currentModelInfo.icon;

  useEffect(() => {
    const handleClick = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", handleClick);
    return () => document.removeEventListener("mousedown", handleClick);
  }, []);

  const selectModel = (modelId: string) => {
    updateBackendSettings(undefined, modelId);
    setOpen(false);
  };

  const toggleProvider = (newProv: string) => {
    if (newProv === "Google") {
      updateBackendSettings("Google (Gemini)", "gemini-2.5-flash");
    } else {
      updateBackendSettings("OpenAI", "gpt-4o");
    }
  };

  return (
    <div ref={ref} className={`relative shrink-0 ${className || ""}`}>
      <button
        onClick={() => setOpen((v) => !v)}
        title={`Model: ${model} (${provider})`}
        className={`group flex items-center gap-2.5 px-3.5 h-full rounded-xl border text-xs font-semibold transition-all duration-300 select-none whitespace-nowrap cursor-pointer backdrop-blur-md shadow-inner
          ${open
            ? isGoogle
              ? "bg-rose-500/10 border-rose-500/35 text-rose-300 shadow-[0_0_15px_rgba(244,63,94,0.12)]"
              : "bg-emerald-500/10 border-emerald-500/35 text-emerald-300 shadow-[0_0_15px_rgba(16,185,129,0.12)]"
            : "bg-[#111116]/40 border-white/10 text-[#F4F4F6]/50 hover:text-[#F4F4F6]/85 hover:border-white/20 hover:bg-[#181822]/60"
          }`}
      >
        {/* Animated pulse dot indicator */}
        <span className="relative flex h-2 w-2 shrink-0">
          <span className={`animate-ping absolute inline-flex h-full w-full rounded-full opacity-75 duration-1000
            ${isGoogle ? "bg-rose-500" : "bg-emerald-500"}`} 
          />
          <span className={`relative inline-flex rounded-full h-2 w-2
            ${isGoogle ? "bg-rose-500 shadow-[0_0_6px_#f43f5e]" : "bg-emerald-500 shadow-[0_0_6px_#10b981]"}`} 
          />
        </span>

        {/* Selected Model Icon */}
        <ModelIcon className={`w-3.5 h-3.5 shrink-0 transition-transform group-hover:scale-110 ${currentModelInfo.color}`} />
        
        {/* Selected Model Text */}
        <span className="font-mono tracking-tight text-[11px] font-bold">{currentModelInfo.short}</span>
        
        {/* Chevron */}
        <ChevronDown className={`w-3.5 h-3.5 shrink-0 text-[#F4F4F6]/30 transition-transform duration-300 ${open ? "rotate-180 text-current" : "group-hover:text-[#F4F4F6]/50"}`} />
      </button>

      <AnimatePresence>
        {open && (
          <motion.div
            initial={{ opacity: 0, scale: 0.96, y: 8 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.96, y: 8 }}
            transition={{ duration: 0.18, ease: [0.16, 1, 0.3, 1] }}
            className="absolute bottom-full mb-3 right-0 z-50 w-[260px] bg-[#0a0a0f]/95 border border-white/10 rounded-2xl shadow-[0_20px_50px_rgba(0,0,0,0.7)] backdrop-blur-xl p-2.5 flex flex-col gap-2"
          >
            {/* Header / Segmented Tab Switcher */}
            <div className="flex p-0.5 bg-black/45 border border-white/5 rounded-xl text-[10px] font-bold select-none">
              <button
                type="button"
                onClick={() => toggleProvider("Google")}
                className={`flex-1 flex items-center justify-center gap-1.5 py-1.5 rounded-lg transition-all duration-200 cursor-pointer
                  ${isGoogle
                    ? "bg-rose-500/15 border border-rose-500/25 text-rose-300 font-semibold shadow-inner"
                    : "text-[#F4F4F6]/40 hover:text-[#F4F4F6]/75 border border-transparent"
                  }`}
              >
                <Sparkles className="w-3 h-3 text-rose-400" />
                Google
              </button>
              <button
                type="button"
                onClick={() => toggleProvider("OpenAI")}
                className={`flex-1 flex items-center justify-center gap-1.5 py-1.5 rounded-lg transition-all duration-200 cursor-pointer
                  ${!isGoogle
                    ? "bg-emerald-500/15 border border-emerald-500/25 text-emerald-300 font-semibold shadow-inner"
                    : "text-[#F4F4F6]/40 hover:text-[#F4F4F6]/75 border border-transparent"
                  }`}
              >
                <Cpu className="w-3 h-3 text-emerald-400" />
                OpenAI
              </button>
            </div>

            {/* List Header */}
            <div className="px-1.5 py-0.5 flex justify-between items-center">
              <span className="text-[9px] font-mono text-[#F4F4F6]/30 uppercase tracking-widest">
                Select Model preset
              </span>
              <span className={`text-[8px] px-1.5 py-0.5 rounded font-mono border uppercase tracking-wider
                ${isGoogle ? "border-rose-500/20 text-rose-400/80 bg-rose-500/5" : "border-emerald-500/20 text-emerald-400/80 bg-emerald-500/5"}`}
              >
                {isGoogle ? "gemini" : "openai"}
              </span>
            </div>

            {/* Models Presets List */}
            <div className="flex flex-col gap-1">
              {models.map((m) => {
                const Icon = m.icon;
                const active = model === m.id;
                return (
                  <button
                    key={m.id}
                    onClick={() => selectModel(m.id)}
                    className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-xl text-left transition-all duration-200 group/item cursor-pointer border relative overflow-hidden
                      ${active
                        ? isGoogle
                          ? "bg-rose-500/10 border-rose-500/25 text-rose-300 shadow-sm"
                          : "bg-emerald-500/10 border-emerald-500/25 text-emerald-300 shadow-sm"
                        : "bg-transparent border-transparent text-[#F4F4F6]/60 hover:bg-white/[0.03] hover:border-white/5 hover:text-[#F4F4F6]"
                      }`}
                  >
                    {/* Active Accent Highlight Line */}
                    {active && (
                      <span className={`absolute left-0 top-2 bottom-2 w-0.5 rounded-r
                        ${isGoogle ? "bg-rose-400" : "bg-emerald-400"}`} 
                      />
                    )}

                    {/* Icon Box */}
                    <div className={`p-1.5 rounded-lg border shrink-0 transition-all duration-200 group-hover/item:scale-105
                      ${active
                        ? isGoogle
                          ? "bg-rose-950/20 border-rose-500/20"
                          : "bg-emerald-950/20 border-emerald-500/20"
                        : "bg-black/25 border-white/5 group-hover/item:border-white/10"
                      }`}
                    >
                      <Icon className={`w-3.5 h-3.5 ${active ? (isGoogle ? "text-rose-400" : "text-emerald-400") : "text-[#F4F4F6]/30 group-hover/item:text-[#F4F4F6]/65"}`} />
                    </div>

                    {/* Meta Text */}
                    <div className="flex flex-col min-w-0">
                      <span className="text-xs font-semibold tracking-tight">{m.label}</span>
                      <span className="text-[10px] text-[#F4F4F6]/35 group-hover/item:text-[#F4F4F6]/50 mt-0.5 truncate">{m.desc}</span>
                    </div>

                    {/* Selected Checkmark Indicator */}
                    {active && (
                      <div className={`ml-auto p-0.5 rounded-full shrink-0 flex items-center justify-center
                        ${isGoogle ? "bg-rose-500/20 text-rose-400" : "bg-emerald-500/20 text-emerald-400"}`}
                      >
                        <Check className="w-3 h-3 stroke-[2.5]" />
                      </div>
                    )}
                  </button>
                );
              })}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
