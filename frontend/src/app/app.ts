import { Component, ElementRef, OnDestroy, OnInit, computed, inject, signal, viewChild } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { Attachment, BrainApi, ChatEvent, ConversationSummary, Health, Stats } from './brain-api';

interface ToolStep { name: string; ok: boolean | null; ms: number | null; }

interface Turn {
  role: 'user' | 'assistant' | 'error';
  text: string;
  tools: ToolStep[];
  stats?: string;
}

@Component({
  selector: 'app-root',
  imports: [FormsModule],
  templateUrl: './app.html',
  styleUrl: './app.css',
})
export class App implements OnInit, OnDestroy {
  private api = inject(BrainApi);
  private scroller = viewChild<ElementRef<HTMLElement>>('scroller');

  health = signal<Health | null>(null);
  conversations = signal<ConversationSummary[]>([]);
  conversationId = signal<string | null>(null);
  turns = signal<Turn[]>([]);
  draft = signal('');
  attachments = signal<Attachment[]>([]);
  uploading = signal(false);
  uploadError = signal('');
  busy = signal(false);
  waitSeconds = signal(0);
  waitingForFirstWord = signal(false);

  brainReady = computed(() => this.health()?.brain.ok ?? false);
  toolSummary = computed(() => {
    const t = Object.values(this.health()?.tools ?? {});
    return `${t.filter(x => x.ok).length}/${t.length}`;
  });
  toolsOk = computed(() => {
    const t = Object.values(this.health()?.tools ?? {});
    return t.length > 0 && t.every(x => x.ok);
  });

  private timer: ReturnType<typeof setInterval> | null = null;
  private healthTimer: ReturnType<typeof setInterval> | null = null;

  async ngOnInit() {
    await Promise.all([this.refreshHealth(), this.refreshConversations()]);
    this.healthTimer = setInterval(() => this.refreshHealth(), 30000);
  }

  ngOnDestroy() {
    if (this.healthTimer) clearInterval(this.healthTimer);
    this.stopTimer();
  }

  async refreshHealth() {
    try { this.health.set(await this.api.health()); } catch { this.health.set(null); }
  }

  async refreshConversations() {
    try { this.conversations.set(await this.api.conversations()); } catch { /* shown via health */ }
  }

  newChat() {
    if (this.busy()) return;
    this.conversationId.set(null);
    this.turns.set([]);
  }

  async open(c: ConversationSummary) {
    if (this.busy()) return;
    const stored = await this.api.messages(c.id);
    const turns: Turn[] = [];
    let pendingTools: ToolStep[] = [];
    for (const m of stored) {
      if (m.role === 'tool') {
        pendingTools.push({ name: m.tool_name ?? '?', ok: m.ok, ms: m.duration_ms });
      } else if (m.role === 'user') {
        const text = m.content.replace(/\n\n\[Attached file: (.+?) \| file_id: \w+\]/g, '\n\n📎 $1');
        turns.push({ role: 'user', text, tools: [] });
      } else {
        turns.push({ role: m.role, text: m.content, tools: pendingTools });
        pendingTools = [];
      }
    }
    this.conversationId.set(c.id);
    this.turns.set(turns);
    this.scrollDown();
  }

  async attach(input: HTMLInputElement) {
    const list = Array.from(input.files ?? []);
    input.value = '';
    this.uploadError.set('');
    this.uploading.set(true);
    for (const f of list) {
      try {
        const a = await this.api.upload(f);
        this.attachments.update(x => [...x, a]);
      } catch (err) {
        this.uploadError.set(`${f.name}: ${err instanceof Error ? err.message : err}`);
      }
    }
    this.uploading.set(false);
  }

  removeAttachment(id: string) {
    this.attachments.update(x => x.filter(a => a.file_id !== id));
  }

  onKey(e: KeyboardEvent) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      this.send();
    }
  }

  async send() {
    const files = this.attachments();
    const text = this.draft().trim() || (files.length ? 'What is this file?' : '');
    if (!text || this.busy() || this.uploading()) return;
    this.draft.set('');
    this.attachments.set([]);
    this.uploadError.set('');
    const shown = files.length ? `${text}\n\n📎 ${files.map(f => f.name).join(', ')}` : text;
    this.busy.set(true);
    const isNew = this.conversationId() === null;
    const reply: Turn = { role: 'assistant', text: '', tools: [] };
    this.turns.update(t => [...t, { role: 'user', text: shown, tools: [] }, reply]);
    this.startTimer();
    this.scrollDown();

    const update = () => this.turns.update(t => [...t]);
    try {
      await this.api.chat(text, this.conversationId(), files.map(f => f.file_id), (e: ChatEvent) => {
        switch (e.type) {
          case 'conversation':
            this.conversationId.set(e.id);
            break;
          case 'token':
            this.waitingForFirstWord.set(false);
            reply.text += e.text;
            break;
          case 'tool':
            reply.tools.push({ name: e.name, ok: null, ms: null });
            break;
          case 'tool_result': {
            const step = [...reply.tools].reverse().find(s => s.name === e.name && s.ok === null);
            if (step) { step.ok = e.ok; step.ms = e.duration_ms; }
            break;
          }
          case 'done':
            reply.stats = this.describeStats(e.stats);
            break;
          case 'error':
            reply.role = 'error';
            reply.text = (reply.text ? reply.text + '\n\n' : '') + e.text;
            break;
        }
        update();
        this.scrollDown();
      });
    } catch (err) {
      reply.role = 'error';
      reply.text = `Couldn't reach the app server: ${err}`;
      update();
    } finally {
      this.stopTimer();
      this.busy.set(false);
      if (isNew) this.refreshConversations();
    }
  }

  private describeStats(s: Stats | null): string | undefined {
    if (!s?.eval_count || !s.eval_duration) return undefined;
    const rate = s.eval_count / (s.eval_duration / 1e9);
    const total = s.total_duration ? ` · ${(s.total_duration / 1e9).toFixed(1)}s` : '';
    return `${s.eval_count} tokens · ${rate.toFixed(1)} tok/s${total}`;
  }

  private startTimer() {
    this.waitSeconds.set(0);
    this.waitingForFirstWord.set(true);
    this.timer = setInterval(() => this.waitSeconds.update(s => s + 1), 1000);
  }

  private stopTimer() {
    if (this.timer) clearInterval(this.timer);
    this.timer = null;
    this.waitingForFirstWord.set(false);
  }

  private scrollDown() {
    queueMicrotask(() => {
      const el = this.scroller()?.nativeElement;
      if (el) el.scrollTop = el.scrollHeight;
    });
  }
}
