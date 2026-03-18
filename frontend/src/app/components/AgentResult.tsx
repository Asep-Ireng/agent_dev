import React from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Sparkles } from "lucide-react";
import ReactMarkdown from "react-markdown";

interface AgentResultProps {
  agentResult: string;
  developerLoading: boolean;
}

export default function AgentResult({
  agentResult,
  developerLoading,
}: AgentResultProps) {
  if (!agentResult || developerLoading) return null;

  return (
    <AnimatePresence>
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
            <span className="text-xs text-[#EAEFEF]/60 font-medium uppercase tracking-wider">
              Development Summary
            </span>
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
    </AnimatePresence>
  );
}
