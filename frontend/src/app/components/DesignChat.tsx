import React from "react";
import { Sparkles, Box, Loader2, Paperclip, Send } from "lucide-react";

interface DesignChatProps {
  chatHistory: { role: "user" | "agent"; content: string }[];
  currentMessage: string;
  setCurrentMessage: (msg: string) => void;
  attachedFiles: File[];
  setAttachedFiles: React.Dispatch<React.SetStateAction<File[]>>;
  designerLoading: boolean;
  handleChatSubmit: () => void;
}

export default function DesignChat({
  chatHistory,
  currentMessage,
  setCurrentMessage,
  attachedFiles,
  setAttachedFiles,
  designerLoading,
  handleChatSubmit,
}: DesignChatProps) {
  return (
    <div className="flex flex-col bg-black/20 border border-[#EAEFEF]/5 rounded-2xl shadow-xl overflow-hidden h-full">
      <div className="p-4 bg-gradient-to-r from-[#FF9B51]/40 to-[#FF9B51]/20 border-b border-[#EAEFEF]/5">
        <h3 className="text-lg font-medium text-[#EAEFEF] flex items-center gap-2">
          <Sparkles className="w-4 h-4 text-[#FF9B51]" /> Chat with Lead
          Designer
        </h3>
        <p className="text-xs text-[#EAEFEF]/60 mt-1">
          Start by describing your app. Attach PDFs or Images.
        </p>
      </div>

      <div className="flex-1 overflow-y-auto p-4 space-y-4 custom-scrollbar">
        {chatHistory.length === 0 && (
          <div className="h-full flex flex-col items-center justify-center text-[#EAEFEF]/30 space-y-3">
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
              className={`max-w-[80%] rounded-2xl px-4 py-2 text-sm ${
                msg.role === "user"
                  ? "bg-[#FF9B51] text-[#25343F] font-medium"
                  : "bg-white/5 border border-white/10 text-[#EAEFEF]/90"
              }`}
            >
              {msg.content}
            </div>
          </div>
        ))}
        {designerLoading && (
          <div className="flex justify-start">
            <div className="max-w-[80%] rounded-2xl px-4 py-2 text-sm bg-white/5 border border-white/10 text-[#EAEFEF]/60 flex items-center gap-2">
              <Loader2 className="w-4 h-4 animate-spin" /> Rethinking
              architecture...
            </div>
          </div>
        )}
      </div>

      <div className="p-4 bg-[#0A0A0B]/50 border-t border-[#EAEFEF]/5 space-y-3">
        {/* File Previews */}
        {attachedFiles.length > 0 && (
          <div className="flex gap-2 mx-2 overflow-x-auto custom-scrollbar pb-2">
            {attachedFiles.map((f, i) => (
              <div
                key={i}
                className="flex items-center gap-2 shrink-0 bg-[#FF9B51]/30 border border-[#FF9B51]/50 text-[#EAEFEF] text-xs px-2 py-1 rounded-md"
              >
                <span className="truncate max-w-[100px]">{f.name}</span>
                <button
                  onClick={() =>
                    setAttachedFiles((prev) =>
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
  );
}
