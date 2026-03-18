import React from "react";
import ReactMarkdown from "react-markdown";
import { Loader2, XCircle } from "lucide-react";

interface SpecViewerProps {
  spec: string;
  setSpec: (s: string) => void;
  specTab: "preview" | "edit";
  setSpecTab: (t: "preview" | "edit") => void;
  developerLoading: boolean;
  designerLoading: boolean;
  handleDevelop: () => void;
  handleStopDevelop: () => void;
}

export default function SpecViewer({
  spec,
  setSpec,
  specTab,
  setSpecTab,
  developerLoading,
  designerLoading,
  handleDevelop,
  handleStopDevelop,
}: SpecViewerProps) {
  return (
    <div className="flex flex-col bg-black/20 border border-[#EAEFEF]/5 rounded-2xl shadow-xl overflow-hidden h-full">
      {/* Tabs */}
      <div className="flex justify-between items-center bg-black/40 border-b border-[#EAEFEF]/5 p-2">
        <div className="flex gap-2">
          <button
            onClick={() => setSpecTab("preview")}
            className={`px-4 py-1.5 rounded-lg text-sm font-medium transition-all ${
              specTab === "preview"
                ? "bg-[#FF9B51]/40 text-[#EAEFEF]"
                : "text-[#EAEFEF]/50 hover:text-[#EAEFEF]/80 hover:bg-[#EAEFEF]/5"
            }`}
          >
            Preview
          </button>
          <button
            onClick={() => setSpecTab("edit")}
            className={`px-4 py-1.5 rounded-lg text-sm font-medium transition-all ${
              specTab === "edit"
                ? "bg-[#FF9B51]/40 text-[#EAEFEF]"
                : "text-[#EAEFEF]/50 hover:text-[#EAEFEF]/80 hover:bg-[#EAEFEF]/5"
            }`}
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
              {developerLoading ? (
                <Loader2 className="w-3 h-3 animate-spin" />
              ) : (
                "Approve & Dev →"
              )}
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
            <ReactMarkdown>
              {spec || "_Awaiting initial instructions..._"}
            </ReactMarkdown>
          </div>
        )}
      </div>
    </div>
  );
}
