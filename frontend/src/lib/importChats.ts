/**
 * Reading another assistant's export in the browser. Only what the person
 * wrote is kept (never the assistant's replies), and the file itself is never
 * uploaded: the text sent is at most what the server reads (18,000 characters).
 */

const LIMIT = 18_000;
// Messages that say something about the writer come first.
const ABOUT_ME = /\b(i am|i'm|i work|i live|i have|my |i study|i want|i prefer)\b|أنا|عندي|أعمل|أسكن|أدرس|أفضّل|أفضل/i;

type Json = unknown;

function userMessages(data: Json): string[] {
  const out: string[] = [];
  const conversations = Array.isArray(data) ? data : [];
  for (const convo of conversations) {
    if (!convo || typeof convo !== "object") continue;
    // ChatGPT: { mapping: { id: { message: { author: { role }, content: { parts } } } } }
    const mapping = (convo as { mapping?: Record<string, { message?: { author?: { role?: string }; content?: { parts?: unknown[] } } }> }).mapping;
    if (mapping) {
      for (const node of Object.values(mapping)) {
        const m = node?.message;
        if (m?.author?.role !== "user") continue;
        const text = (m.content?.parts ?? []).filter((p): p is string => typeof p === "string").join("\n").trim();
        if (text) out.push(text);
      }
    }
    // Claude: { chat_messages: [{ sender: "human", text }] }
    const messages = (convo as { chat_messages?: { sender?: string; text?: string }[] }).chat_messages;
    if (Array.isArray(messages)) {
      for (const m of messages) if (m?.sender === "human" && m.text?.trim()) out.push(m.text.trim());
    }
  }
  return out;
}

/** The text to read facts from: a pasted memory list, notes, or an export file. */
export function importText(raw: string): string {
  let messages: string[] | null = null;
  const trimmed = raw.trim();
  if (trimmed.startsWith("[") || trimmed.startsWith("{")) {
    try {
      const parsed = JSON.parse(trimmed);
      messages = userMessages(Array.isArray(parsed) ? parsed : [parsed]);
    } catch {
      messages = null;
    }
  }
  if (!messages) return trimmed.slice(0, LIMIT);
  const unique = [...new Set(messages.map((m) => m.slice(0, 1500)))];
  const ordered = [...unique.filter((m) => ABOUT_ME.test(m)), ...unique.filter((m) => !ABOUT_ME.test(m))];
  let text = "";
  for (const m of ordered) {
    if (text.length + m.length + 2 > LIMIT) break;
    text += `${m}\n\n`;
  }
  return text.trim();
}
