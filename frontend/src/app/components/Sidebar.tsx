import React from "react";
import { motion } from "framer-motion";
import { Sparkles, Settings2 } from "lucide-react";

interface SidebarProps {
  provider: string;
  setProvider: (p: string) => void;
  model: string;
  setModel: (m: string) => void;
  openaiModel: string;
  setOpenaiModel: (m: string) => void;
  googleModel: string;
  setGoogleModel: (m: string) => void;
  thinkingLevel: string;
  setThinkingLevel: (level: string) => void;
  workspacePath: string;
  setWorkspacePath: (path: string) => void;
  requireApproval: boolean;
  setRequireApproval: (val: boolean) => void;
  developerLoading: boolean;
  updateBackendSettings: (provider?: string, model?: string, thinkingLevel?: string) => void;
  onOpenExistingCodebase: () => void;
  onCloseCodebase: () => void;
  isCodebaseActive: boolean;
}

export default function Sidebar({
  provider,
  setProvider,
  model,
  setModel,
  openaiModel,
  setOpenaiModel,
  googleModel,
  setGoogleModel,
  thinkingLevel,
  setThinkingLevel,
  workspacePath,
  setWorkspacePath,
  requireApproval,
  setRequireApproval,
  developerLoading,
  updateBackendSettings,
  onOpenExistingCodebase,
  onCloseCodebase,
  isCodebaseActive,
}: SidebarProps) {
  return (
    <motion.aside
      initial={{ x: -300, opacity: 0 }}
      animate={{ x: 0, opacity: 1 }}
      transition={{ duration: 0.5, ease: "easeOut" }}
      className="w-80 bg-black/20 backdrop-blur-md border-r border-[#F4F4F6]/5 p-6 flex flex-col shadow-2xl z-10"
    >
      <div className="flex items-center gap-3 mb-10">
        <div className="p-2 bg-gradient-to-br from-[#E51937] to-[#E51937] rounded-xl shadow-lg shadow-[#E51937]/30">
          <Sparkles className="w-5 h-5 text-[#F4F4F6]" />
        </div>
        <h1 className="text-xl font-bold bg-clip-text text-transparent bg-gradient-to-r from-[#F4F4F6] to-[#71717A]">
          Duh Le
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
                  setModel(p === "OpenAI" ? openaiModel : googleModel);
                  updateBackendSettings(p);
                }}
                className={`px-3 py-2 rounded-lg text-sm font-medium transition-all duration-200 border 
                  ${provider === p
                    ? "bg-[#E51937]/30 border-[#E51937]/50 text-[#F4F4F6] shadow-inner"
                    : "bg-black/20 border-[#F4F4F6]/5 hover:bg-[#F4F4F6]/5 text-[#F4F4F6]/60"
                  }`}
              >
                {p.split(" ")[0]}
              </button>
            ))}
          </div>
        </div>

        <div className="space-y-2">
          <label className="text-xs font-semibold text-slate-500 uppercase tracking-wider">
            Model
          </label>
          <input
            type="text"
            value={model}
            onChange={(e) => {
              setModel(e.target.value);
              if (provider === "OpenAI") setOpenaiModel(e.target.value);
              else setGoogleModel(e.target.value);
              updateBackendSettings(undefined, e.target.value);
            }}
            className="w-full bg-black/20 border border-[#F4F4F6]/5 rounded-lg px-4 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-[#E51937]/50 transition-all placeholder:text-[#F4F4F6]/40"
          />
        </div>

        {provider === "Google (Gemini)" && (
          <div className="space-y-2">
            <label className="text-xs font-semibold text-slate-500 uppercase tracking-wider">
              Thinking Level
            </label>
            <select
              value={thinkingLevel}
              onChange={(e) => {
                setThinkingLevel(e.target.value);
                updateBackendSettings(undefined, undefined, e.target.value);
              }}
              className="w-full bg-black/20 border border-[#F4F4F6]/5 rounded-lg px-4 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-[#E51937]/50 transition-all text-[#F4F4F6]"
            >
              <option value="none" className="bg-[#0A0A0B]">None (Default)</option>
              <option value="minimal" className="bg-[#0A0A0B]">Minimal</option>
              <option value="low" className="bg-[#0A0A0B]">Low</option>
              <option value="medium" className="bg-[#0A0A0B]">Medium</option>
              <option value="high" className="bg-[#0A0A0B]">High</option>
            </select>
          </div>
        )}

        <div className="space-y-2">
          <label className="text-xs font-semibold text-slate-500 uppercase tracking-wider">
            Workspace Path
          </label>
          <input
            type="text"
            placeholder="./workspace"
            value={workspacePath}
            onChange={(e) => setWorkspacePath(e.target.value)}
            className="w-full bg-black/20 border border-[#F4F4F6]/5 rounded-lg px-4 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-[#E51937]/50 transition-all font-mono placeholder:text-[#F4F4F6]/40"
          />
          <p className="text-[10px] text-[#71717A]/50 mt-1">
            Directory where the agent writes code.
          </p>
          {isCodebaseActive ? (
            <button
              onClick={onCloseCodebase}
              disabled={developerLoading}
              className="w-full mt-2 py-2 bg-white/5 hover:bg-[#E51937]/25 border border-white/10 hover:border-[#E51937]/35 text-[#F4F4F6] rounded-xl text-xs font-semibold tracking-wider transition-all active:scale-95 disabled:opacity-50 disabled:pointer-events-none flex items-center justify-center gap-1.5 shadow-md shadow-[#E51937]/10 uppercase"
              title="Close direct session and return to Lead Designer spec phase"
            >
              ✕ Close Codebase
            </button>
          ) : (
            <button
              onClick={onOpenExistingCodebase}
              disabled={developerLoading}
              className="w-full mt-2 py-2 bg-white/5 hover:bg-[#E51937]/25 border border-white/10 hover:border-[#E51937]/35 text-[#F4F4F6] rounded-xl text-xs font-semibold tracking-wider transition-all active:scale-95 disabled:opacity-50 disabled:pointer-events-none flex items-center justify-center gap-1.5 shadow-md shadow-black/10 uppercase"
              title="Bypass design planning and talk directly to Developer"
            >
              📂 Open Codebase
            </button>
          )}
        </div>

        <div className="space-y-2 pt-2 border-t border-[#F4F4F6]/5">
          <label className="text-xs font-semibold text-slate-500 uppercase tracking-wider flex items-center justify-between">
            <span>HITL Verification</span>
            <button
              onClick={() => {
                const newVal = !requireApproval;
                setRequireApproval(newVal);
                if (developerLoading) {
                  fetch(
                    `http://localhost:8000/api/develop/toggle-approval?require=${newVal}`,
                    { method: "POST" }
                  ).catch(() => { });
                }
              }}
              className={`relative inline-flex h-5 w-9 shrink-0 cursor-pointer rounded-full transition-colors duration-200 ease-in-out ${requireApproval ? "bg-[#E51937]" : "bg-[#F4F4F6]/20"
                }`}
            >
              <span
                className={`inline-block h-4 w-4 transform rounded-full bg-white shadow transition duration-200 ease-in-out mt-0.5 ${requireApproval ? "translate-x-4" : "translate-x-0.5"
                  }`}
              />
            </button>
          </label>
          <p className="text-[10px] text-[#F4F4F6]/40 mt-1">
            Require explicit approval before executing any Terminal commands.
          </p>
        </div>
      </div>
    </motion.aside>
  );
}
