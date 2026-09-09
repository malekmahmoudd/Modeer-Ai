export interface Agent {
  id: string;
  name: string;
  role: string;
  description: string;
  icon: string;
  accent: string;
  is_assistant: boolean;
  sort_order: number;
  expertise: string[];
}

export interface AgentDetail extends Agent {
  reasoning_framework: string[];
  response_behavior: string[];
  safety_boundaries: string[];
  shared_context_fields: string[];
  memory_namespace: string;
  prompt_version: number;
  model: { model: string | null; temperature: number; max_tokens: number };
}

export interface Message {
  id: string;
  role: "user" | "assistant" | "system";
  content: string;
  meta: Record<string, unknown> & {
    context?: ContextDiagnostics;
    provider?: string;
    model?: string;
  };
  created_at: string;
}

export interface Conversation {
  id: string;
  agent_id: string;
  title: string;
  created_at: string;
  last_message_at: string | null;
}

export interface ConversationDetail extends Conversation {
  messages: Message[];
}

export interface ContextDiagnostics {
  agent_id: string;
  prompt_version: number;
  shared_memory_used: string[];
  agent_memory_used: string[];
  personal_context_count: number;
  history_messages: number;
  system_chars: number;
}

export interface MemoryCandidate {
  scope: "shared" | "agent";
  agent_id: string | null;
  category: string;
  key: string;
  value: string;
  confidence: number;
  stored: boolean;
  reason: string;
}

export interface SharedMemory {
  id: string;
  scope: string;
  category: string;
  key: string;
  value: string;
  source: string;
  confidence: number;
  sensitive: boolean;
  pinned: boolean;
  created_at: string;
  updated_at: string;
}

export interface AgentMemory {
  id: string;
  scope: string;
  agent_id: string;
  category: string;
  key: string;
  value: string;
  source: string;
  confidence: number;
  sensitive: boolean;
  created_at: string;
  updated_at: string;
}

export interface Goal {
  id: string;
  title: string;
  detail: string;
  priority: number;
  status: "active" | "done" | "paused";
  target_date: string | null;
  created_at: string;
  updated_at: string;
}

export interface BriefingItem {
  icon: string;
  text: string;
  source: string;
}

export interface Briefing {
  id: string;
  summary: string;
  items: BriefingItem[];
  generated_for_date: string;
  created_at: string;
}

export interface UserProfile {
  id: string;
  email: string | null;
  display_name: string;
  onboarded: boolean;
  profile: Record<string, unknown>;
  created_at: string;
}

export type ChatStreamEvent =
  | { type: "start"; conversation_id: string; agent_id: string; context: ContextDiagnostics }
  | { type: "delta"; text: string }
  | {
      type: "end";
      conversation_id: string;
      message_id: string;
      content: string;
      memory_candidates: MemoryCandidate[];
      context_used: boolean;
    }
  | { type: "error"; error: string };
