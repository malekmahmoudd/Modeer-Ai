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
  tagline: string;
  composer_placeholder: string;
  empty_prompt: string;
  starters: string[];
}

/** The API no longer publishes how an agent is built — only what a screen shows. */
export type AgentDetail = Agent;

/** How an assistant reply ended. Replies saved before this existed completed. */
export type Completion = "completed" | "truncated" | "interrupted" | "failed";

/** A file sent with a message. */
export interface Attachment {
  id: string;
  filename: string;
  kind: string;
  size_bytes: number;
}

export interface Message {
  id: string;
  role: "user" | "assistant" | "system";
  content: string;
  meta: Record<string, unknown> & {
    attachments?: Attachment[];
    context?: ContextDiagnostics;
    provider?: string;
    model?: string;
    notice?: string;
  };
  completion?: Completion;
  created_at: string;
  /** When the person saved this reply; null when not saved. */
  pinned_at?: string | null;
}

export interface Conversation {
  id: string;
  agent_id: string;
  title: string;
  created_at: string;
  last_message_at: string | null;
  incognito?: boolean;
  expires_at?: string | null;
}

/** A message or title that matched a search. */
export interface SearchHit {
  conversation_id: string;
  agent_id: string;
  title: string;
  message_id: string;
  role: "user" | "assistant";
  snippet: string;
  created_at: string;
}

/** A reply the person saved. */
export interface PinnedReply {
  message_id: string;
  conversation_id: string;
  agent_id: string;
  title: string;
  content: string;
  pinned_at: string;
}

/** GET /briefings/week: the last seven days and the next seven. */
export interface WeekReview {
  from: string;
  to: string;
  summary: string;
  plan_steps_done: number;
  checkins: Record<string, number>;
  goals_done: string[];
  followups_passed: string[];
  coming_up: { title: string; due_on: string; agent: string }[];
  plan_steps_due: number;
  spending: Record<string, number>;
  quiet_goals: string[];
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
  /** Passages from the person's files this reply was given. */
  documents?: RetrievedPassage[];
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
  /** What the fact said before this update, when it replaced a value. */
  previous_value?: string | null;
}

/** A goal change Leo applied (or declined) because the user asked for it. */
export interface GoalChangeNote {
  op: "add" | "done" | "pause" | "resume" | "priority";
  title: string;
  goal_id: string | null;
  priority: number | null;
  target_date: string | null;
  applied: boolean;
  reason: string;
}

/** Something the team now keeps track of, reported after a turn. */
export interface TrackedNote {
  title?: string;
  text?: string;
  due_on?: string;
  stored?: boolean;
  steps?: number;
}

/** How much of today's AI allowance is left. */
export interface Allowance {
  used: number;
  limit: number;
  remaining: number;
  messages_left: number;
  resets_at: number;
}

/** A note left for a teammate at the user's request. */
export interface HandoffNote {
  agent_id: string;
  agent_name: string;
  brief: string;
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
  detail?: string;
  source: "goal" | "memory" | "prompt";
  agent: string | null;
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
  memory_auto: boolean;
  timezone?: string | null;
  /** Interface language; null follows the browser. */
  locale?: "en" | "ar" | null;
  created_at: string;
}

export interface AuthStatus {
  required: boolean;
  signup_enabled: boolean;
}

export interface AccountSecurity {
  has_password: boolean;
  recovery_codes_left: number;
  email: string | null;
  /** Two-step sign-in with an authenticator app is on. */
  two_factor?: boolean;
}

/** A device signed in to this account (GET /auth/sessions). */
export interface SignedInDevice {
  id: string;
  current: boolean;
  browser: string | null;
  system: string | null;
  /** The first part of the network address, e.g. "203.0.113.x". */
  network: string | null;
  method: string;
  signed_in_at: string;
  last_seen_at: string | null;
}

/** One specialist's answer to an Ask My Team question. */
export interface TeamTake {
  agent_id: string;
  name: string;
  answer: string;
  completion: Completion;
  conversation_id: string | null;
}

export interface TeamAnswer {
  question: string;
  takes: TeamTake[];
  synthesis: string;
  conversation_id: string | null;
}

export type ChatStreamEvent =
  | { type: "start"; conversation_id: string; agent_id: string; context: ContextDiagnostics }
  | { type: "delta"; text: string }
  | {
      type: "end";
      conversation_id: string;
      message_id: string;
      content: string;
      completion: Completion;
      notice: string;
      context_used: boolean;
    }
  | {
      type: "memory";
      conversation_id: string;
      memory_candidates: MemoryCandidate[];
      goal_changes?: GoalChangeNote[];
      handoffs?: HandoffNote[];
      followups?: TrackedNote[];
      followups_closed?: { id: string; title: string; outcome: string | null }[];
      checkins?: TrackedNote[];
      plans?: TrackedNote[];
      plan_progress?: TrackedNote[];
      allowance?: Allowance | null;
      newly_onboarded: boolean;
      error?: string;
    }
  | { type: "error"; error: string; status?: number; conversation_id?: string };

/** A file given to an agent. Only its extracted text is kept. */
export interface UserDocument {
  id: string;
  agent_id: string;
  shared: boolean;
  filename: string;
  kind: "pdf" | "docx" | "txt" | "md" | "image";
  size_bytes: number;
  status: "processing" | "ready" | "failed";
  /** Why it failed, or a note such as "only the first part was kept". */
  error: string | null;
  pages: number;
  chars: number;
  /** False when the server runs keyword search only. */
  searchable_by_meaning: boolean;
  created_at: string | null;
  preview?: string;
  chunks?: number;
}

/** A passage a reply was given, as reported in the turn's context diagnostics. */
export interface RetrievedPassage {
  label: string;
  document_id: string;
  filename: string;
  page: number | null;
  score: number;
}

/** A dated thing the team follows up on. */
export interface FollowUp {
  id: string;
  agent_id: string;
  title: string;
  due_on: string;
  /** Last day, for things that span days (a trip). */
  ends_on: string | null;
  status: "pending" | "done" | "dismissed";
  asked_at: string | null;
  source_message_id: string | null;
}

export interface PlanStep {
  id: string;
  position: number;
  text: string;
  due_on: string | null;
  done: boolean;
}

/** A plan an agent wrote that the person kept as a checklist. */
export interface SavedPlan {
  id: string;
  agent_id: string;
  goal_id: string | null;
  title: string;
  status: "active" | "done" | "archived";
  starts_on: string;
  done: number;
  steps: PlanStep[];
}

export interface CheckIn {
  id: string;
  agent_id: string;
  text: string;
  amount: number | null;
  unit: string | null;
  /** Structured parts: sets/reps/load for a lift, currency/direction for money. */
  details: Record<string, string | number> | null;
  logged_on: string;
}

/** Why the team knows a fact: the message it came from and earlier values. */
export interface MemorySource {
  id: string;
  source: string;
  saved_by_you: boolean;
  learned_from: {
    message_id: string;
    conversation_id: string;
    agent_id: string;
    said_at: string | null;
    excerpt: string;
  } | null;
  history: { value: string; source: string; replaced_at: string; replaced_by?: string }[];
}
