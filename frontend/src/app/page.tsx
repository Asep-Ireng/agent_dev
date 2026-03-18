"use client";

import React, { useState, useEffect } from "react";
import { motion } from "framer-motion";
import { ChevronUp } from "lucide-react";
import { LogEntry } from "./types";

import Sidebar from "./components/Sidebar";
import DesignChat from "./components/DesignChat";
import SpecViewer from "./components/SpecViewer";
import Terminal from "./components/Terminal";
import AgentResult from "./components/AgentResult";
import DevChat from "./components/DevChat";

export default function Home() {
  const [provider, setProvider] = useState("Google (Gemini)");
  const [model, setModel] = useState("gemini-2.5-flash");
  const [googleModel, setGoogleModel] = useState("gemini-2.5-flash");
  const [openaiModel, setOpenaiModel] = useState("gpt-4o");
  const [thinkingLevel, setThinkingLevel] = useState("none");

  const [workspacePath, setWorkspacePath] = useState("./workspace");

  const [chatHistory, setChatHistory] = useState<
    { role: "user" | "agent"; content: string }[]
  >([]);
  const [currentMessage, setCurrentMessage] = useState("");
  const [attachedFiles, setAttachedFiles] = useState<File[]>([]);

  const [spec, setSpec] = useState("");
  // Removed code state as it was unused in original file
  const [specTab, setSpecTab] = useState<"preview" | "edit">("preview");

  const [designerLoading, setDesignerLoading] = useState(false);
  const [developerLoading, setDeveloperLoading] = useState(false);

  const [actionLogs, setActionLogs] = useState<LogEntry[]>([]);
  const [requireApproval, setRequireApproval] = useState(true);
  const [pendingCommand, setPendingCommand] = useState<string | null>(null);
  const [rejectReason, setRejectReason] = useState("");
  const [expandedThoughts, setExpandedThoughts] = useState<Set<number>>(
    new Set()
  );
  const [agentResult, setAgentResult] = useState<string>("");
  const [devChatMessages, setDevChatMessages] = useState<
    { role: string; content: string }[]
  >([]);
  const [devChatInput, setDevChatInput] = useState("");
  const [devChatLoading, setDevChatLoading] = useState(false);
  const [devChatFiles, setDevChatFiles] = useState<File[]>([]);
  const [devChatMode, setDevChatMode] = useState<"ask" | "apply">("ask");
  const [pendingApplyTask, setPendingApplyTask] = useState<string | null>(null);

  // Fetch settings from backend on mount
  useEffect(() => {
    fetch("http://localhost:8000/api/settings")
      .then((res) => res.json())
      .then((data) => {
        setProvider(data.provider);
        setModel(data.model);
        setGoogleModel(data.google_model);
        setOpenaiModel(data.openai_model);
        if (data.thinking_level) setThinkingLevel(data.thinking_level);
        if (data.workspace_path) setWorkspacePath(data.workspace_path);
      })
      .catch(() => {});
  }, []);

  // Sync provider/model changes to backend
  const updateBackendSettings = (newProvider?: string, newModel?: string, newThinkingLevel?: string) => {
    const body: Record<string, string> = {};
    if (newProvider !== undefined) body.provider = newProvider;
    if (newModel !== undefined) body.model = newModel;
    if (newThinkingLevel !== undefined) body.thinking_level = newThinkingLevel;
    fetch("http://localhost:8000/api/settings", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }).catch(() => {});
  };

  const handleChatSubmit = async () => {
    if (!currentMessage.trim() && attachedFiles.length === 0) return;

    const userText = currentMessage;
    setChatHistory((prev) => [...prev, { role: "user", content: userText }]);
    setCurrentMessage("");
    setDesignerLoading(true);

    try {
      const formData = new FormData();
      formData.append("idea", userText);
      formData.append("spec", spec); // send current spec context
      attachedFiles.forEach((file) => formData.append("files", file));

      const res = await fetch("http://localhost:8000/api/design/chat", {
        method: "POST",
        body: formData,
      });

      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "API failed");

      setSpec(data.spec);
      setChatHistory((prev) => [
        ...prev,
        { role: "agent", content: data.summary || "Specification updated." },
      ]);
      setAttachedFiles([]);
      setSpecTab("preview");
    } catch (err: unknown) {
      console.error("Design API Error:", err);
      if (err instanceof Error) {
        alert("Error: " + err.message);
      } else {
        alert("An unknown error occurred.");
      }
    } finally {
      setDesignerLoading(false);
    }
  };

  const addLog = (entry: LogEntry) => {
    setActionLogs((prev) => [...prev, entry]);
  };

  const handleDevelop = () => {
    setDeveloperLoading(true);
    setActionLogs([]);
    setExpandedThoughts(new Set());
    setAgentResult("");
    setDevChatMessages([]);
    setDevChatInput("");

    const processSSEStream = async (
      reader: ReadableStreamDefaultReader<Uint8Array>
    ) => {
      const decoder = new TextDecoder();
      let buffer = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n");
        buffer = lines.pop() || "";

        let currentEvent = "";
        for (const line of lines) {
          if (line.startsWith("event: ")) {
            currentEvent = line.slice(7).trim();
          } else if (line.startsWith("data: ")) {
            const dataStr = line.slice(6);
            try {
              const data = JSON.parse(dataStr);
              handleSSEEvent(currentEvent, data);

              if (currentEvent === "done") {
                const status =
                  data.status ||
                  (data.killed ? "killed" : data.error ? "failed" : "success");
                const summary = data.status_summary
                  ? ` — ${data.status_summary}`
                  : "";
                switch (status) {
                  case "killed":
                    addLog({
                      type: "system",
                      text: "Agent stopped by user.",
                      level: "warn",
                    });
                    break;
                  case "failed":
                    addLog({
                      type: "system",
                      text: `Development failed.${summary}`,
                      level: "error",
                    });
                    break;
                  case "partial":
                    addLog({
                      type: "system",
                      text: `Development partially completed — some issues occurred.${summary}`,
                      level: "warn",
                    });
                    break;
                  case "success":
                  default:
                    addLog({
                      type: "system",
                      text: `Development completed successfully!${summary}`,
                      level: "info",
                    });
                    break;
                }
                setPendingCommand(null);
                setDeveloperLoading(false);
                return;
              }
            } catch (e) {
              console.error(`Failed to parse ${currentEvent} event:`, e);
            }
          }
        }
      }
    };

    const handleSSEEvent = (
      eventType: string,
      data: Record<string, unknown>
    ) => {
      switch (eventType) {
        case "thought":
          addLog({ type: "thought", text: data.text as string });
          break;
        case "model_thinking":
          addLog({ type: "model_thinking", text: data.text as string });
          break;
        case "tool_call":
          addLog({
            type: "tool_call",
            tool: data.tool as string,
            input: (data.input as string) || "",
          });
          break;
        case "tool_input":
          addLog({ type: "tool_input", input: data.input as string });
          break;
        case "tool_result":
          addLog({
            type: "tool_result",
            ...(data as Record<string, unknown>),
          } as LogEntry);
          break;
        case "final_answer":
          addLog({ type: "final_answer", text: data.text as string });
          break;
        case "system":
          addLog({
            type: "system",
            text: data.text as string,
            level: (data.level as "info" | "warn" | "error") || "info",
          });
          break;
        case "log":
          addLog({ type: "log", text: data.text as string });
          break;
        case "cmd_start":
          addLog({
            type: "cmd_start",
            cwd: data.cwd as string,
            cmd: data.cmd as string,
          });
          break;
        case "cmd_output":
          addLog({
            type: "cmd_output",
            stream: data.stream as "stdout" | "stderr",
            line: data.line as string,
          });
          break;
        case "cmd_end":
          addLog({
            type: "cmd_end",
            exit_code: data.exit_code as number,
            success: data.success as boolean,
          });
          break;
        case "result":
          if (data.text) setAgentResult(data.text as string);
          break;
        case "action_required":
          setPendingCommand(data.command as string);
          break;
      }
    };

    fetch("http://localhost:8000/api/develop", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        spec: spec,
        workspace_path: workspacePath,
        require_approval: requireApproval,
      }),
    })
      .then((res) => {
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const reader = res.body!.getReader();
        return processSSEStream(reader);
      })
      .catch((err) => {
        console.error("Develop stream failed:", err);
        addLog({
          type: "system",
          text: "Connection closed or errored.",
          level: "error",
        });
        setPendingCommand(null);
        setDeveloperLoading(false);
      });
  };

  const handleStopDevelop = async () => {
    try {
      addLog({ type: "system", text: "Sending kill signal...", level: "warn" });
      await fetch("http://localhost:8000/api/develop/stop", { method: "POST" });
    } catch (err) {
      console.error("Failed to send stop signal:", err);
    }
  };

  const handleDevChat = async () => {
    if (!devChatInput.trim() || devChatLoading) return;

    const userMessage = devChatInput.trim();
    const filesToSend = [...devChatFiles];
    setDevChatInput("");
    setDevChatFiles([]);

    const modeLabel = devChatMode === "apply" ? "🔧" : "💬";
    const displayText =
      filesToSend.length > 0
        ? `${modeLabel} ${userMessage} [📎 ${filesToSend.length} file${
            filesToSend.length > 1 ? "s" : ""
          }]`
        : `${modeLabel} ${userMessage}`;
    setDevChatMessages((prev) => [
      ...prev,
      { role: "user", content: displayText },
    ]);
    setDevChatLoading(true);

    if (devChatMode === "apply") {
      try {
        const formData = new FormData();
        formData.append(
          "message",
          `The user wants you to make the following change:\n\n"${userMessage}"\n\nCreate a brief, specific plan of what you will do. List the files you will read, modify, or create, and describe the changes concisely. Do NOT execute anything yet — just describe the plan.`
        );
        formData.append("spec", spec);
        formData.append("workspace_path", workspacePath);
        formData.append("history", JSON.stringify(devChatMessages));
        filesToSend.forEach((file) => formData.append("files", file));

        const response = await fetch("http://localhost:8000/api/dev-chat", {
          method: "POST",
          body: formData,
        });

        if (!response.ok) throw new Error(`HTTP ${response.status}`);

        const data = await response.json();
        setPendingApplyTask(userMessage);
        setDevChatMessages((prev) => [
          ...prev,
          {
            role: "assistant",
            content: `**📋 Proposed Plan:**\n\n${data.reply}\n\n---\n_Click **Proceed** below to execute this plan, or type a follow-up to refine it._`,
          },
        ]);
      } catch (err) {
        console.error("Dev chat plan error:", err);
        setDevChatMessages((prev) => [
          ...prev,
          {
            role: "assistant",
            content: "Failed to generate a plan. Check the backend.",
          },
        ]);
        setPendingApplyTask(null);
      } finally {
        setDevChatLoading(false);
      }
    } else {
      try {
        const formData = new FormData();
        formData.append("message", userMessage);
        formData.append("spec", spec);
        formData.append("workspace_path", workspacePath);
        formData.append("history", JSON.stringify(devChatMessages));
        filesToSend.forEach((file) => formData.append("files", file));

        const response = await fetch("http://localhost:8000/api/dev-chat", {
          method: "POST",
          body: formData,
        });

        if (!response.ok) throw new Error(`HTTP ${response.status}`);

        const data = await response.json();
        setDevChatMessages((prev) => [
          ...prev,
          { role: "assistant", content: data.reply },
        ]);
      } catch (err) {
        console.error("Dev chat error:", err);
        setDevChatMessages((prev) => [
          ...prev,
          {
            role: "assistant",
            content:
              "Sorry, something went wrong. Check that the backend is running.",
          },
        ]);
      } finally {
        setDevChatLoading(false);
      }
    }
  };

  const handleApplyProceed = () => {
    if (!pendingApplyTask) return;

    const taskToExecute = pendingApplyTask;
    setPendingApplyTask(null);
    setDevChatMessages((prev) => [
      ...prev,
      { role: "user", content: "▶ Proceeding with the plan..." },
    ]);
    setDeveloperLoading(true);
    setActionLogs([]);

    const chatContext = devChatMessages
      .slice(-10)
      .map((m) => `${m.role === "user" ? "User" : "Dev"}: ${m.content}`)
      .join("\n");
    const fullTask = chatContext
      ? `${taskToExecute}\n\n--- Chat Context ---\n${chatContext}`
      : taskToExecute;

    const processSSEStream = async (
      reader: ReadableStreamDefaultReader<Uint8Array>
    ) => {
      const decoder = new TextDecoder();
      let buffer = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n");
        buffer = lines.pop() || "";

        let currentEvent = "";
        for (const line of lines) {
          if (line.startsWith("event: ")) {
            currentEvent = line.slice(7).trim();
          } else if (line.startsWith("data: ")) {
            const dataStr = line.slice(6);
            try {
              const data = JSON.parse(dataStr);

              switch (currentEvent) {
                case "thought":
                  addLog({ type: "thought", text: data.text });
                  break;
                case "tool_call":
                  addLog({
                    type: "tool_call",
                    tool: data.tool,
                    input: data.input,
                  });
                  break;
                case "tool_input":
                  addLog({ type: "tool_input", input: data.input });
                  break;
                case "tool_result":
                  addLog({ type: "tool_result", ...data });
                  break;
                case "final_answer":
                  addLog({ type: "final_answer", text: data.text });
                  break;
                case "system":
                  addLog({
                    type: "system",
                    text: data.text,
                    level: data.level,
                  });
                  break;
                case "log":
                  addLog({ type: "log", text: data.text });
                  break;
                case "cmd_start":
                  addLog({ type: "cmd_start", cwd: data.cwd, cmd: data.cmd });
                  break;
                case "cmd_output":
                  addLog({
                    type: "cmd_output",
                    stream: data.stream,
                    line: data.line,
                  });
                  break;
                case "cmd_end":
                  addLog({
                    type: "cmd_end",
                    exit_code: data.exit_code,
                    success: data.success,
                  });
                  break;
                case "action_required":
                  setPendingCommand(data.command);
                  break;
                case "result":
                  if (data.text) {
                    setDevChatMessages((prev) => [
                      ...prev,
                      {
                        role: "assistant",
                        content: `✅ **Changes Applied:**\n\n${data.text}`,
                      },
                    ]);
                    setAgentResult(data.text);
                  }
                  break;
                case "done":
                  setDeveloperLoading(false);
                  return;
              }
            } catch (e) {
              console.error(`Failed to parse ${currentEvent} event:`, e);
            }
          }
        }
      }
    };

    fetch("http://localhost:8000/api/dev-iterate", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        task: fullTask,
        spec: spec,
        dev_context: agentResult || "",
        workspace_path: workspacePath,
        require_approval: requireApproval,
      }),
    })
      .then((res) => {
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const reader = res.body!.getReader();
        return processSSEStream(reader);
      })
      .catch((err) => {
        console.error("Iterate stream failed:", err);
        addLog({
          type: "system",
          text: "Iteration connection closed or errored.",
          level: "error",
        });
        setDeveloperLoading(false);
      });
  };

  const handleCommandApproval = async (approved: boolean) => {
    try {
      setPendingCommand(null);
      await fetch("http://localhost:8000/api/develop/approve", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          approved,
          feedback: approved ? undefined : rejectReason,
        }),
      });
      setRejectReason("");
    } catch (err) {
      console.error("Failed to send approval:", err);
    }
  };

  return (
    <div className="flex h-screen bg-[#25343F] text-[#EAEFEF]/80 font-sans selection:bg-[#FF9B51]/30 overflow-hidden">
      <Sidebar
        provider={provider}
        setProvider={setProvider}
        model={model}
        setModel={setModel}
        openaiModel={openaiModel}
        setOpenaiModel={setOpenaiModel}
        googleModel={googleModel}
        setGoogleModel={setGoogleModel}
        thinkingLevel={thinkingLevel}
        setThinkingLevel={setThinkingLevel}
        workspacePath={workspacePath}
        setWorkspacePath={setWorkspacePath}
        requireApproval={requireApproval}
        setRequireApproval={setRequireApproval}
        developerLoading={developerLoading}
        updateBackendSettings={updateBackendSettings}
      />

      <main className="flex-1 overflow-y-auto p-10 relative">
        <div className="max-w-4xl mx-auto space-y-12 pb-32">
          {/* HEADER AREA */}
          <motion.div
            initial={{ y: 20, opacity: 0 }}
            animate={{ y: 0, opacity: 1 }}
            transition={{ delay: 0.1 }}
            className="space-y-2"
          >
            <h2 className="text-3xl font-light text-[#EAEFEF] tracking-tight">
              What are we building?
            </h2>
            <p className="text-[#EAEFEF]/60 text-sm">
              Enter a high level idea and watch the agents build the software.
            </p>
          </motion.div>

          {/* MAIN INTERFACE: Split view for Chat & Spec */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-8 h-[600px]">
            <DesignChat
              chatHistory={chatHistory}
              currentMessage={currentMessage}
              setCurrentMessage={setCurrentMessage}
              attachedFiles={attachedFiles}
              setAttachedFiles={setAttachedFiles}
              designerLoading={designerLoading}
              handleChatSubmit={handleChatSubmit}
            />

            <SpecViewer
              spec={spec}
              setSpec={setSpec}
              specTab={specTab}
              setSpecTab={setSpecTab}
              developerLoading={developerLoading}
              designerLoading={designerLoading}
              handleDevelop={handleDevelop}
              handleStopDevelop={handleStopDevelop}
            />
          </div>

          <Terminal
            actionLogs={actionLogs}
            developerLoading={developerLoading}
            workspacePath={workspacePath}
            pendingCommand={pendingCommand}
            rejectReason={rejectReason}
            setRejectReason={setRejectReason}
            handleCommandApproval={handleCommandApproval}
            expandedThoughts={expandedThoughts}
            setExpandedThoughts={setExpandedThoughts}
          />

          <AgentResult
            agentResult={agentResult}
            developerLoading={developerLoading}
          />

          <DevChat
            devChatMessages={devChatMessages}
            devChatInput={devChatInput}
            setDevChatInput={setDevChatInput}
            devChatLoading={devChatLoading}
            devChatFiles={devChatFiles}
            setDevChatFiles={setDevChatFiles}
            devChatMode={devChatMode}
            setDevChatMode={setDevChatMode}
            pendingApplyTask={pendingApplyTask}
            setPendingApplyTask={setPendingApplyTask}
            agentResult={agentResult}
            developerLoading={developerLoading}
            handleDevChat={handleDevChat}
            handleApplyProceed={handleApplyProceed}
            setDevChatMessages={setDevChatMessages}
          />
        </div>
      </main>

      <button
        onClick={() => window.scrollTo({ top: 0, behavior: "smooth" })}
        className="fixed bottom-6 right-6 z-50 w-10 h-10 bg-[#395370]/80 hover:bg-[#395370] text-[#EAEFEF] rounded-full shadow-lg shadow-black/30 flex items-center justify-center transition-all hover:scale-110 active:scale-95 backdrop-blur-sm border border-white/10"
        title="Scroll to top"
      >
        <ChevronUp className="w-5 h-5" />
      </button>

      <style
        dangerouslySetInnerHTML={{
          __html: `
        .custom-scrollbar::-webkit-scrollbar { width: 8px; }
        .custom-scrollbar::-webkit-scrollbar-track { background: transparent; }
        .custom-scrollbar::-webkit-scrollbar-thumb { background: rgba(255,255,255,0.1); border-radius: 4px; }
        .custom-scrollbar::-webkit-scrollbar-thumb:hover { background: rgba(255,255,255,0.2); }
      `,
        }}
      />
    </div>
  );
}
