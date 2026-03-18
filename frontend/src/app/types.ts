export type LogEntry =
  | { type: "thought"; text: string }
  | { type: "model_thinking"; text: string }
  | { type: "tool_call"; tool: string; input: string }
  | { type: "tool_input"; input: string }
  | {
      type: "tool_result";
      tool: string;
      cwd: string;
      cmd: string;
      stdout: string;
      stderr: string;
      exit_code: number | null;
      success: boolean;
      raw: string;
    }
  | { type: "final_answer"; text: string }
  | { type: "system"; text: string; level: "info" | "warn" | "error" }
  | { type: "log"; text: string }
  | { type: "cmd_start"; cwd: string; cmd: string }
  | { type: "cmd_output"; stream: "stdout" | "stderr"; line: string }
  | { type: "cmd_end"; exit_code: number; success: boolean };
