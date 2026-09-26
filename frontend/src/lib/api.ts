"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import { t } from "@/lib/i18n";

export const API_BASE = process.env.NEXT_PUBLIC_API_URL || "/api";

/** Pages a signed-out person can use. A 401 there is an answer, not a reason to leave. */
export const PUBLIC_PAGES = ["/login", "/privacy", "/signup", "/recover"];

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

/**
 * A validation failure arrives as a list of objects, one per field. Turned into
 * the sentences they carry — otherwise a form shows "[object Object]".
 */
function readableDetail(detail: unknown): string {
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) {
    return detail
      .map((item) => (item && typeof item === "object" && "msg" in item ? String(item.msg) : ""))
      .map((msg) => msg.replace(/^Value error, /, ""))
      .filter(Boolean)
      .join(" ");
  }
  return "";
}

export async function apiFetch<T>(
  path: string,
  init: RequestInit = {},
): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(init.headers || {}),
    },
  });
  if (res.status === 401 && typeof window !== "undefined" && !PUBLIC_PAGES.includes(window.location.pathname)) {
    window.location.assign("/login");
  }
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = readableDetail(body.detail) || JSON.stringify(body);
    } catch {
      /* keep statusText */
    }
    throw new ApiError(res.status, detail);
  }
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

/** What the upload endpoint accepts. Checked here first, so a phone does not
 *  send 10 MB over mobile data only to be told no. */
export const UPLOAD_TYPES = ".pdf,.docx,.txt,.md,.jpg,.jpeg,.png,.webp";
export const UPLOAD_MAX_BYTES = 10 * 1024 * 1024;

/** Why an upload was refused, in words, by status code. */
const UPLOAD_ERRORS: Record<number, () => string> = {
  409: () => t("upload.limit"),
  413: () => t("upload.tooBig"),
  415: () => t("upload.type"),
};

const IMAGE = /\.(jpe?g|png|webp)$/i;
/** Longest side a photo is sent at: what OCR reads best, a fraction of the bytes. */
const PHOTO_SIDE = 2400;

/**
 * A photo, redrawn at most 2400px on its longest side as a JPEG. Redrawing
 * drops everything but the pixels — including the GPS position a phone camera
 * writes into the file — and turns a 6 MB photo into a few hundred KB, which
 * matters on a weak connection. Anything else, or any failure, is sent as is.
 */
async function preparePhoto(file: File): Promise<File> {
  if (!IMAGE.test(file.name) || typeof createImageBitmap === "undefined") return file;
  try {
    const bitmap = await createImageBitmap(file, { imageOrientation: "from-image" });
    const scale = Math.min(1, PHOTO_SIDE / Math.max(bitmap.width, bitmap.height));
    const canvas = document.createElement("canvas");
    canvas.width = Math.round(bitmap.width * scale);
    canvas.height = Math.round(bitmap.height * scale);
    const context = canvas.getContext("2d");
    if (!context) return file;
    context.fillStyle = "#ffffff"; // transparent PNG areas read as white, not black
    context.fillRect(0, 0, canvas.width, canvas.height);
    context.drawImage(bitmap, 0, 0, canvas.width, canvas.height);
    bitmap.close();
    const blob = await new Promise<Blob | null>((done) => canvas.toBlob(done, "image/jpeg", 0.88));
    if (!blob) return file;
    return new File([blob], file.name.replace(IMAGE, ".jpg"), { type: "image/jpeg" });
  } catch {
    return file;
  }
}

/**
 * Upload a file to one agent. Uses XMLHttpRequest because fetch cannot report
 * upload progress. `onProgress` gets 0–1; the returned `abort` cancels. The
 * server answers at once with status "processing"; poll /documents/{id}.
 */
export function uploadDocument(
  file: File,
  agentId: string,
  opts: { shared?: boolean; onProgress?: (fraction: number) => void } = {},
): { promise: Promise<import("@/types").UserDocument>; abort: () => void } {
  const xhr = new XMLHttpRequest();
  let cancelled = false;

  const send = (upload: File) =>
    new Promise<import("@/types").UserDocument>((resolve, reject) => {
      if (cancelled) {
        reject(new ApiError(0, t("upload.cancelled")));
        return;
      }
      if (upload.size > UPLOAD_MAX_BYTES) {
        reject(new ApiError(413, UPLOAD_ERRORS[413]()));
        return;
      }
      const form = new FormData();
      form.append("file", upload);
      form.append("agent_id", agentId);
      form.append("shared", opts.shared ? "true" : "false");
      xhr.open("POST", `${API_BASE}/documents`);
      xhr.upload.onprogress = (e) => {
        if (e.lengthComputable) opts.onProgress?.(e.loaded / e.total);
      };
      xhr.onload = () => {
        let body: { detail?: unknown } | null = null;
        try {
          body = JSON.parse(xhr.responseText);
        } catch {
          /* not JSON */
        }
        if (xhr.status === 401 && !PUBLIC_PAGES.includes(window.location.pathname)) {
          window.location.assign("/login");
        }
        if (xhr.status >= 200 && xhr.status < 300) {
          resolve(body as import("@/types").UserDocument);
        } else {
          const detail = readableDetail(body?.detail) || UPLOAD_ERRORS[xhr.status]?.() || t("upload.failed");
          reject(new ApiError(xhr.status, detail));
        }
      };
      xhr.onerror = () => reject(new ApiError(0, t("upload.interrupted")));
      xhr.onabort = () => reject(new ApiError(0, t("upload.cancelled")));
      xhr.send(form);
    });

  const name = file.name.toLowerCase();
  const promise = UPLOAD_TYPES.split(",").some((ext) => name.endsWith(ext))
    ? preparePhoto(file).then(send)
    : Promise.reject(new ApiError(415, UPLOAD_ERRORS[415]()));
  return {
    promise,
    abort: () => {
      cancelled = true;
      xhr.abort();
    },
  };
}

/** Minimal data hook: fetch on mount, expose loading/error and a refetch. */
export function useApi<T>(path: string | null, deps: unknown[] = []) {
  const [data, setData] = useState<T | null>(null);
  const [loading, setLoading] = useState(Boolean(path));
  const [error, setError] = useState<string | null>(null);
  const mounted = useRef(true);
  const requestId = useRef(0);

  const load = useCallback(async () => {
    const request = ++requestId.current;
    if (!mounted.current) return;
    if (!path) {
      setData(null);
      setLoading(false);
      setError(null);
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const result = await apiFetch<T>(path);
      if (mounted.current && request === requestId.current) setData(result);
    } catch (err) {
      if (mounted.current && request === requestId.current) {
        setError(err instanceof Error ? err.message : "Request failed");
      }
    } finally {
      if (mounted.current && request === requestId.current) setLoading(false);
    }
  }, [path]);

  useEffect(() => {
    const requests = requestId;
    mounted.current = true;
    load();
    return () => {
      mounted.current = false;
      ++requests.current;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [load, ...deps]);

  return { data, loading, error, refetch: load, setData };
}
