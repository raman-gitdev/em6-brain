import { Injectable } from '@angular/core';

export interface Health {
  brain: { ok: boolean; url: string; model: string; model_installed?: boolean; error?: string };
  database: { ok: boolean; error?: string };
  tools: Record<string, { ok: boolean; service?: string; tools?: string[]; error?: string }>;
}

export interface ConversationSummary { id: string; title: string; created_at: string; }

export interface StoredMessage {
  role: 'user' | 'assistant' | 'tool' | 'error';
  content: string;
  tool_name: string | null;
  ok: boolean | null;
  duration_ms: number | null;
}

export interface Attachment { file_id: string; name: string; size: number; }

export interface Stats { eval_count?: number; eval_duration?: number; total_duration?: number; }

export type ChatEvent =
  | { type: 'conversation'; id: string }
  | { type: 'token'; text: string }
  | { type: 'tool'; name: string; arguments: Record<string, unknown> }
  | { type: 'tool_result'; name: string; ok: boolean; duration_ms: number }
  | { type: 'done'; stats: Stats | null }
  | { type: 'error'; text: string };

/** The only place the front end talks to the orchestrator. */
@Injectable({ providedIn: 'root' })
export class BrainApi {
  async health(): Promise<Health> {
    return this.getJson('/api/health');
  }

  async conversations(): Promise<ConversationSummary[]> {
    return this.getJson('/api/conversations');
  }

  async messages(id: string): Promise<StoredMessage[]> {
    return this.getJson(`/api/conversations/${id}/messages`);
  }

  /** Uploads one file; the returned file_id goes with the next chat message. */
  async upload(file: File): Promise<Attachment> {
    const form = new FormData();
    form.append('file', file);
    const res = await fetch('/api/files', { method: 'POST', body: form });
    if (!res.ok) {
      const body = await res.json().catch(() => null);
      throw new Error(body?.detail ?? `Upload failed (${res.status})`);
    }
    return res.json() as Promise<Attachment>;
  }

  /** Sends a message and calls onEvent for every streamed event. */
  async chat(message: string, conversationId: string | null, attachments: string[],
             onEvent: (e: ChatEvent) => void): Promise<void> {
    const res = await fetch('/api/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ message, conversation_id: conversationId, attachments }),
    });
    if (!res.ok || !res.body) {
      const body = await res.json().catch(() => null);
      onEvent({ type: 'error', text: body?.detail ?? `Server returned ${res.status}` });
      return;
    }
    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';
    for (;;) {
      const { value, done } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      let nl: number;
      while ((nl = buffer.indexOf('\n')) >= 0) {
        const line = buffer.slice(0, nl).trim();
        buffer = buffer.slice(nl + 1);
        if (line) onEvent(JSON.parse(line) as ChatEvent);
      }
    }
  }

  private async getJson<T>(url: string): Promise<T> {
    const res = await fetch(url);
    if (!res.ok) throw new Error(`${url} returned ${res.status}`);
    return res.json() as Promise<T>;
  }
}
