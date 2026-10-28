"use client";

import clsx from "clsx";
import { Check, MessageSquarePlus, Pencil, Trash2, X } from "lucide-react";
import { useState } from "react";
import type { ConversationSummary } from "@/lib/types";
import { Button, inputClass, Spinner } from "../ui";

export function ConversationSidebar({ items, activeId, loading, error, onSelect, onNew, onRename, onDelete }: {
  items: ConversationSummary[];
  activeId: string | null;
  loading: boolean;
  error: string | null;
  onSelect: (id: string) => void;
  onNew: () => void;
  onRename: (id: string, title: string) => Promise<void>;
  onDelete: (id: string) => Promise<void>;
}) {
  const [editing, setEditing] = useState<string | null>(null);
  const [draft, setDraft] = useState("");
  const [confirming, setConfirming] = useState<string | null>(null);

  return (
    <nav aria-label="Conversations" className="flex h-full flex-col gap-2">
      <Button onClick={onNew} className="w-full"><MessageSquarePlus className="h-4 w-4" aria-hidden /> New chat</Button>
      <h2 className="px-1 pt-2 text-xs font-medium uppercase tracking-wide text-muted">History</h2>
      {loading && <Spinner label="Loading chats" />}
      {error && <p className="px-1 text-xs text-danger">{error}</p>}
      {!loading && !error && items.length === 0 && <p className="px-1 text-sm text-muted">No conversations yet.</p>}
      <ul className="-mx-1 flex-1 space-y-0.5 overflow-y-auto px-1">
        {items.map((c) => (
          <li key={c.id}>
            {editing === c.id ? (
              <form
                className="flex items-center gap-1"
                onSubmit={async (e) => { e.preventDefault(); if (draft.trim()) await onRename(c.id, draft.trim()); setEditing(null); }}
              >
                <label className="sr-only" htmlFor={`rename-${c.id}`}>Conversation title</label>
                <input id={`rename-${c.id}`} className={clsx(inputClass, "h-8")} value={draft} maxLength={200}
                       onChange={(e) => setDraft(e.target.value)} autoFocus />
                <Button size="sm" variant="ghost" type="submit" aria-label="Save title"><Check className="h-4 w-4" aria-hidden /></Button>
                <Button size="sm" variant="ghost" type="button" aria-label="Cancel rename" onClick={() => setEditing(null)}><X className="h-4 w-4" aria-hidden /></Button>
              </form>
            ) : confirming === c.id ? (
              <div className="flex items-center gap-1 rounded-lg bg-danger-soft px-2 py-1 text-sm">
                <span className="flex-1 text-danger">Delete this chat?</span>
                <Button size="sm" variant="danger" onClick={async () => { await onDelete(c.id); setConfirming(null); }}>Delete</Button>
                <Button size="sm" variant="ghost" onClick={() => setConfirming(null)}>Cancel</Button>
              </div>
            ) : (
              <div className={clsx("group flex items-center rounded-lg", activeId === c.id ? "bg-primary/10" : "hover:bg-surface-muted")}>
                <button type="button" onClick={() => onSelect(c.id)} aria-current={activeId === c.id ? "true" : undefined}
                        className={clsx("min-w-0 flex-1 truncate px-2 py-1.5 text-left text-sm", activeId === c.id && "font-medium text-primary")}>
                  {c.title}
                </button>
                <span className="flex opacity-100 lg:opacity-0 lg:group-focus-within:opacity-100 lg:group-hover:opacity-100">
                  <Button size="sm" variant="ghost" aria-label={`Rename “${c.title}”`} onClick={() => { setEditing(c.id); setDraft(c.title); }}>
                    <Pencil className="h-3.5 w-3.5" aria-hidden />
                  </Button>
                  <Button size="sm" variant="ghost" aria-label={`Delete “${c.title}”`} onClick={() => setConfirming(c.id)}>
                    <Trash2 className="h-3.5 w-3.5" aria-hidden />
                  </Button>
                </span>
              </div>
            )}
          </li>
        ))}
      </ul>
      <p className="px-1 text-[11px] leading-snug text-muted">
        Chats are tied to this browser (no account). Anyone using this browser can see them.
      </p>
    </nav>
  );
}
