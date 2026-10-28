"use client";

import clsx from "clsx";
import { History, Send, Square, X } from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";
import { api, ApiError, streamChat } from "@/lib/api";
import type { ChatResponse, ConversationDetail, ConversationSummary, MessageMeta, Page } from "@/lib/types";
import { useHealth } from "../health";
import { Button, Notice } from "../ui";
import { AssistantMessage } from "./AssistantMessage";
import { ConversationSidebar } from "./ConversationSidebar";

const MAX_CHARS = 2000;

const EXAMPLES = [
  { label: "Grounded Q&A", text: "What is the best time to visit Varanasi?" },
  { label: "Itinerary", text: "Plan a 3-day trip to Jaipur for heritage and food" },
  { label: "Compare", text: "Compare Goa and Kerala for a relaxed beach trip" },
  { label: "हिंदी", text: "मुझे उदयपुर में 2 दिन घूमने का प्लान बनाओ" },
  { label: "ગુજરાતી", text: "અમદાવાદથી ઉદયપુર કેટલું દૂર છે?" },
  { label: "Hinglish", text: "Rishikesh mein rafting kab hoti hai?" },
];

interface UIMessage { id: string; role: "user" | "assistant"; content: string; meta?: MessageMeta; streaming?: boolean; error?: string }

function metaFrom(r: ChatResponse): MessageMeta {
  return { citations: r.citations, evidence: r.evidence, answer_mode: r.answer_mode, blocks: r.blocks,
           suggestions: r.suggestions, notices: r.notices, intent: r.intent, language: r.language };
}

export function ChatWorkspace() {
  const { health } = useHealth();
  const [conversations, setConversations] = useState<ConversationSummary[]>([]);
  const [listState, setListState] = useState<{ loading: boolean; error: string | null }>({ loading: true, error: null });
  const [activeId, setActiveId] = useState<string | null>(null);
  const [messages, setMessages] = useState<UIMessage[]>([]);
  const [loadingConv, setLoadingConv] = useState(false);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [drawer, setDrawer] = useState(false);
  const abortRef = useRef<AbortController | null>(null);
  const endRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  const refreshList = useCallback(async () => {
    try {
      const page = await api<Page<ConversationSummary>>("/api/conversations?limit=50");
      setConversations(page.items);
      setListState({ loading: false, error: null });
    } catch (e) {
      setListState({ loading: false, error: (e as Error).message });
    }
  }, []);

  useEffect(() => { refreshList(); }, [refreshList]);
  useEffect(() => { endRef.current?.scrollIntoView({ behavior: "smooth", block: "end" }); }, [messages]);

  const openConversation = async (id: string) => {
    abortRef.current?.abort();
    setDrawer(false);
    setActiveId(id);
    setLoadingConv(true);
    setError(null);
    try {
      const conv = await api<ConversationDetail>(`/api/conversations/${id}`);
      setMessages(conv.messages.map((m) => ({ id: m.id, role: m.role, content: m.content, meta: m.metadata })));
    } catch (e) {
      setError((e as Error).message);
      setMessages([]);
    } finally {
      setLoadingConv(false);
    }
  };

  const newChat = () => {
    abortRef.current?.abort();
    setActiveId(null);
    setMessages([]);
    setError(null);
    setDrawer(false);
    inputRef.current?.focus();
  };

  const send = async (text: string) => {
    const message = text.trim();
    if (!message || busy) return;
    if (message.length > MAX_CHARS) { setError(`Messages are limited to ${MAX_CHARS} characters.`); return; }
    setError(null);
    setInput("");
    setBusy(true);
    const userMsg: UIMessage = { id: `u-${Date.now()}`, role: "user", content: message };
    const pendingId = `a-${Date.now()}`;
    setMessages((m) => [...m, userMsg, { id: pendingId, role: "assistant", content: "", streaming: true }]);
    const controller = new AbortController();
    abortRef.current = controller;
    await streamChat(message, activeId, {
      onMeta: (meta) => {
        if (!activeId) setActiveId(meta.conversation_id);
      },
      onDelta: (t) => setMessages((m) => m.map((x) => (x.id === pendingId ? { ...x, content: x.content + t } : x))),
      onFinal: (r) => {
        setActiveId(r.conversation_id);
        setMessages((m) => m.map((x) => (x.id === pendingId ? { id: r.message_id, role: "assistant", content: r.answer, meta: metaFrom(r) } : x)));
        refreshList();
      },
      onError: (err: ApiError) => {
        setMessages((m) => m.filter((x) => x.id !== pendingId));
        setError(err.code === "rate_limited" ? "You're sending messages quickly — please wait a moment." : err.message);
        setInput(message);
      },
    }, controller.signal);
    if (controller.signal.aborted) {
      setMessages((m) => m.map((x) => (x.id === pendingId ? { ...x, streaming: false, content: x.content || "(stopped)" } : x)));
    }
    setBusy(false);
    abortRef.current = null;
  };

  const sidebar = (
    <ConversationSidebar
      items={conversations} activeId={activeId} loading={listState.loading} error={listState.error}
      onSelect={openConversation} onNew={newChat}
      onRename={async (id, title) => { await api(`/api/conversations/${id}`, { method: "PATCH", body: JSON.stringify({ title }) }); refreshList(); }}
      onDelete={async (id) => { await api(`/api/conversations/${id}`, { method: "DELETE" }); if (id === activeId) newChat(); refreshList(); }}
    />
  );

  return (
    <div className="mx-auto flex h-[calc(100dvh-3.5rem-4rem)] max-w-7xl md:h-[calc(100dvh-3.5rem)]">
      <aside className="hidden w-72 shrink-0 border-r border-border p-3 lg:block">{sidebar}</aside>

      {drawer && (
        <div className="fixed inset-0 z-40 lg:hidden" role="dialog" aria-modal="true" aria-label="Conversation history">
          <button type="button" className="absolute inset-0 bg-black/40" aria-label="Close history" onClick={() => setDrawer(false)} />
          <div className="absolute inset-y-0 left-0 w-80 max-w-[85vw] bg-background p-3 shadow-xl">
            <div className="mb-2 flex justify-end">
              <Button size="sm" variant="ghost" onClick={() => setDrawer(false)} aria-label="Close history"><X className="h-4 w-4" aria-hidden /></Button>
            </div>
            {sidebar}
          </div>
        </div>
      )}

      <section className="flex min-w-0 flex-1 flex-col" aria-label="Chat">
        <div className="flex items-center gap-2 border-b border-border px-4 py-2 lg:hidden">
          <Button size="sm" variant="ghost" onClick={() => setDrawer(true)}><History className="h-4 w-4" aria-hidden /> History</Button>
          <Button size="sm" variant="ghost" onClick={newChat}>New chat</Button>
        </div>

        <div className="flex-1 overflow-y-auto px-4 py-6" aria-live="polite" aria-busy={busy}>
          {loadingConv ? (
            <p className="text-center text-muted" role="status">Loading conversation…</p>
          ) : messages.length === 0 ? (
            <div className="mx-auto max-w-2xl pt-6 text-center sm:pt-12">
              <h1 className="font-display text-3xl font-semibold tracking-tight sm:text-4xl">Where to next?</h1>
              <p className="mx-auto mt-3 max-w-lg text-muted">
                Ask travel questions answered from indexed websites — with sources — then turn ideas into an itinerary you can edit.
                Works in English, हिंदी, ગુજરાતી and Hinglish.
              </p>
              {health?.demo_mode && (
                <div className="mx-auto mt-4 max-w-lg text-left">
                  <Notice tone="warning">
                    Demo mode: answers quote a small sample travel guide, and place results come from a labelled sample dataset.
                    Add API keys (see README) for AI-written answers, live places and road routes.
                  </Notice>
                </div>
              )}
              <ul className="mt-6 grid gap-2 text-left sm:grid-cols-2">
                {EXAMPLES.map((ex) => (
                  <li key={ex.text}>
                    <button type="button" onClick={() => send(ex.text)}
                            className="w-full rounded-xl border border-border bg-surface p-3 text-sm transition-colors hover:border-primary">
                      <span className="block text-xs font-medium text-accent">{ex.label}</span>
                      {ex.text}
                    </button>
                  </li>
                ))}
              </ul>
            </div>
          ) : (
            <ol className="mx-auto max-w-3xl space-y-6">
              {messages.map((m) => (
                <li key={m.id} className={clsx("flex", m.role === "user" ? "justify-end" : "justify-start")}>
                  {m.role === "user" ? (
                    <div className="max-w-[85%] whitespace-pre-wrap rounded-2xl rounded-br-sm bg-primary px-4 py-2 text-primary-foreground">
                      <span className="sr-only">You said: </span>{m.content}
                    </div>
                  ) : (
                    <div className="w-full min-w-0">
                      <span className="sr-only">YatraAI replied:</span>
                      <AssistantMessage content={m.content} meta={m.meta} streaming={m.streaming} onPick={send} disabled={busy} />
                    </div>
                  )}
                </li>
              ))}
            </ol>
          )}
          <div ref={endRef} />
        </div>

        <div className="border-t border-border bg-background px-4 py-3">
          <div className="mx-auto max-w-3xl">
            {error && <div className="mb-2"><Notice tone="error">{error}</Notice></div>}
            <form onSubmit={(e) => { e.preventDefault(); send(input); }} className="flex items-end gap-2">
              <label htmlFor="chat-input" className="sr-only">Message YatraAI</label>
              <textarea
                id="chat-input"
                ref={inputRef}
                rows={1}
                value={input}
                maxLength={MAX_CHARS}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) { e.preventDefault(); send(input); } }}
                placeholder="Ask about a destination, or say “plan 3 days in Udaipur”…"
                className="max-h-40 min-h-11 flex-1 resize-none rounded-xl border border-border bg-surface px-3 py-2.5 text-sm placeholder:text-muted"
              />
              {busy ? (
                <Button type="button" variant="secondary" onClick={() => abortRef.current?.abort()} aria-label="Stop generating" className="h-11">
                  <Square className="h-4 w-4" aria-hidden />
                </Button>
              ) : (
                <Button type="submit" disabled={!input.trim()} aria-label="Send message" className="h-11">
                  <Send className="h-4 w-4" aria-hidden />
                </Button>
              )}
            </form>
            <p className="mt-1.5 flex justify-between text-[11px] text-muted">
              <span>Answers cite their sources. Verify prices, timings and availability before you travel.</span>
              <span aria-hidden={input.length < MAX_CHARS * 0.8}>{input.length > MAX_CHARS * 0.8 ? `${input.length}/${MAX_CHARS}` : ""}</span>
            </p>
          </div>
        </div>
      </section>
    </div>
  );
}
