/**
 * Reading another assistant's export in the browser. Only what the person
 * wrote is kept, never the assistant's replies, and the file itself is never
 * uploaded: the text sent is at most what the server reads (18,000 characters).
 *
 * Two kinds of input, kept apart:
 * - an export file (JSON): must be a ChatGPT or Claude export with at least one
 *   message written by the person. Anything else is refused, never sent as it
 *   is, because a broken export still contains the assistant's side.
 * - notes (plain text): a pasted memory list or the person's own notes, sent
 *   as written.
 */

/** What the server reads from one import. */
export const IMPORT_LIMIT = 18_000;
/** Largest export file read at all; bigger ones would stall the page. */
export const IMPORT_FILE_MAX = 50 * 1024 * 1024;

export type ImportResult =
  | { ok: true; text: string; messages: number }
  | { ok: false; reason: "tooBig" | "malformed" | "unrecognised" | "noUserMessages" | "empty" };

// Messages that say something about the writer come first.
const ABOUT_ME = /\b(i am|i'm|i work|i live|i have|my |i study|i want|i prefer)\b|أنا|عندي|أعمل|أسكن|أدرس|أفضّل|أفضل/i;

type Obj = Record<string, unknown>;
const isObj = (v: unknown): v is Obj => typeof v === "object" && v !== null && !Array.isArray(v);

/** A ChatGPT conversation: { mapping: { id: { message: { author: { role }, content: { parts } } } } }. */
function chatgpt(convo: Obj): string[] | null {
  if (!isObj(convo.mapping)) return null;
  const out: string[] = [];
  for (const node of Object.values(convo.mapping)) {
    if (!isObj(node) || !isObj(node.message)) continue;
    const { author, content } = node.message;
    if (!isObj(author) || author.role !== "user") continue;
    if (!isObj(content) || !Array.isArray(content.parts)) continue;
    const text = content.parts.filter((p): p is string => typeof p === "string").join("\n").trim();
    if (text) out.push(text);
  }
  return out;
}

/** A Claude conversation: { chat_messages: [{ sender: "human", text }] }. */
function claude(convo: Obj): string[] | null {
  if (!Array.isArray(convo.chat_messages)) return null;
  const out: string[] = [];
  for (const m of convo.chat_messages) {
    if (!isObj(m) || m.sender !== "human") continue;
    let text = typeof m.text === "string" ? m.text : "";
    if (!text && Array.isArray(m.content)) {
      text = m.content
        .map((part) => (isObj(part) && part.type === "text" && typeof part.text === "string" ? part.text : ""))
        .join("\n");
    }
    if (text.trim()) out.push(text.trim());
  }
  return out;
}

/** The person's own messages from an export, most personal first, within the limit. */
export function readExport(raw: string): ImportResult {
  let parsed: unknown;
  try {
    parsed = JSON.parse(raw);
  } catch {
    return { ok: false, reason: "malformed" };
  }
  const conversations = Array.isArray(parsed) ? parsed : [parsed];
  let recognised = false;
  const messages: string[] = [];
  for (const convo of conversations) {
    if (!isObj(convo)) continue;
    const found = chatgpt(convo) ?? claude(convo);
    if (found === null) continue;
    recognised = true;
    messages.push(...found);
  }
  if (!recognised) return { ok: false, reason: "unrecognised" };
  if (!messages.length) return { ok: false, reason: "noUserMessages" };
  const unique = [...new Set(messages.map((m) => m.slice(0, 1500)))];
  const ordered = [...unique.filter((m) => ABOUT_ME.test(m)), ...unique.filter((m) => !ABOUT_ME.test(m))];
  let text = "";
  for (const m of ordered) {
    if (text.length + m.length + 2 > IMPORT_LIMIT) break;
    text += `${m}\n\n`;
  }
  return { ok: true, text: text.trim(), messages: unique.length };
}

/** Pasted text. Something that looks like an export must be a valid one:
 *  it is read as an export or refused, never sent as it is. */
export function readPasted(raw: string): ImportResult {
  const trimmed = raw.trim();
  if (!trimmed) return { ok: false, reason: "empty" };
  if (trimmed.startsWith("{") || trimmed.startsWith("[")) return readExport(trimmed);
  return { ok: true, text: trimmed.slice(0, IMPORT_LIMIT), messages: 0 };
}

/** A picked file: checked for size before it is read. */
export async function readFile(file: { size: number; text: () => Promise<string>; name: string }): Promise<ImportResult> {
  if (file.size > IMPORT_FILE_MAX) return { ok: false, reason: "tooBig" };
  const raw = await file.text();
  return /\.json$/i.test(file.name) ? readExport(raw) : readPasted(raw);
}
