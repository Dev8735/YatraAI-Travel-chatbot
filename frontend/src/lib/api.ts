import type { ApiErrorBody, ChatResponse } from "./types";

const CLIENT_KEY = "yatra.clientId";

/** Anonymous per-browser id that scopes conversations and itineraries (not authentication). */
export function getClientId(): string {
  if (typeof window === "undefined") return "server-render-0000";
  let id = window.localStorage.getItem(CLIENT_KEY);
  if (!id || !/^[A-Za-z0-9-]{8,64}$/.test(id)) {
    id = crypto.randomUUID();
    window.localStorage.setItem(CLIENT_KEY, id);
  }
  return id;
}

export class ApiError extends Error {
  constructor(public status: number, public code: string, message: string, public details?: Record<string, unknown>) {
    super(message);
  }
}

async function toError(res: Response): Promise<ApiError> {
  try {
    const body = (await res.json()) as ApiErrorBody;
    return new ApiError(res.status, body.error.code, body.error.message, body.error.details);
  } catch {
    if (res.status >= 500 || res.status === 0) {
      return new ApiError(res.status, "backend_unavailable", "The YatraAI server is not reachable. Is the backend running?");
    }
    return new ApiError(res.status, "http_error", `Request failed (${res.status}).`);
  }
}

export async function api<T>(path: string, init: RequestInit = {}): Promise<T> {
  let res: Response;
  try {
    res = await fetch(path, {
      ...init,
      headers: { "Content-Type": "application/json", "X-Client-Id": getClientId(), ...(init.headers ?? {}) },
    });
  } catch {
    throw new ApiError(0, "offline", "You appear to be offline, or the server could not be reached.");
  }
  if (!res.ok) throw await toError(res);
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

export interface SSEEvent { event: string; data: string }

/** Incremental Server-Sent Events parser (handles events split across network chunks). */
export function createSSEParser(onEvent: (e: SSEEvent) => void): (chunk: string) => void {
  let buffer = "";
  return (chunk: string) => {
    buffer += chunk.replace(/\r\n/g, "\n");
    let idx: number;
    while ((idx = buffer.indexOf("\n\n")) !== -1) {
      const raw = buffer.slice(0, idx);
      buffer = buffer.slice(idx + 2);
      let event = "message";
      const data: string[] = [];
      for (const line of raw.split("\n")) {
        if (line.startsWith(":")) continue; // comment / keep-alive ping
        if (line.startsWith("event:")) event = line.slice(6).trim();
        else if (line.startsWith("data:")) data.push(line.slice(5).replace(/^ /, ""));
      }
      if (data.length) onEvent({ event, data: data.join("\n") });
    }
  };
}

export interface StreamHandlers {
  onMeta?: (meta: { conversation_id: string; intent: string; language: string }) => void;
  onDelta?: (text: string) => void;
  onFinal: (response: ChatResponse) => void;
  onError: (err: ApiError) => void;
}

export async function streamChat(message: string, conversationId: string | null, handlers: StreamHandlers,
                                 signal?: AbortSignal): Promise<void> {
  let res: Response;
  try {
    res = await fetch("/api/chat/stream", {
      method: "POST",
      headers: { "Content-Type": "application/json", "X-Client-Id": getClientId(), Accept: "text/event-stream" },
      body: JSON.stringify({ message, conversation_id: conversationId }),
      signal,
    });
  } catch (e) {
    if ((e as Error).name === "AbortError") return;
    handlers.onError(new ApiError(0, "offline", "You appear to be offline, or the server could not be reached."));
    return;
  }
  if (!res.ok || !res.body) {
    handlers.onError(await toError(res));
    return;
  }
  let finished = false;
  const parse = createSSEParser(({ event, data }) => {
    try {
      const payload = JSON.parse(data);
      if (event === "meta") handlers.onMeta?.(payload);
      else if (event === "delta") handlers.onDelta?.(payload.text);
      else if (event === "final") { finished = true; handlers.onFinal(payload); }
      else if (event === "error") { finished = true; handlers.onError(new ApiError(500, payload.code, payload.message)); }
    } catch {
      /* ignore malformed frames */
    }
  });
  const reader = res.body.pipeThrough(new TextDecoderStream()).getReader();
  try {
    for (;;) {
      const { value, done } = await reader.read();
      if (done) break;
      parse(value);
    }
  } catch (e) {
    if ((e as Error).name !== "AbortError" && !finished) {
      handlers.onError(new ApiError(0, "stream_interrupted", "The connection was interrupted. Please try again."));
    }
    return;
  }
  if (!finished) handlers.onError(new ApiError(0, "stream_incomplete", "The response ended unexpectedly. Please try again."));
}
