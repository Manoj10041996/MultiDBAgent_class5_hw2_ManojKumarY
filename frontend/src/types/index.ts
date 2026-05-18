export interface ToolCallRecord {
  tool: string;
  args: Record<string, unknown> | string;
  result: string;
}

export interface ChatResponse {
  answer: string;
  tool_calls: ToolCallRecord[];
  warnings: string[];
  elapsed_ms: number;
}

export interface Message {
  id: string;
  role: 'user' | 'agent';
  content: string;
  trace?: ToolCallRecord[];
  warnings?: string[];
  elapsed_ms?: number;
}
