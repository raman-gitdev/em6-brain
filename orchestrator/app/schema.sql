-- Brain log store. Runs on every orchestrator start; safe to re-run.
-- Every user question, brain answer and tool call is kept here: this is the
-- audit trail now and the training / RAG material later.

CREATE SCHEMA IF NOT EXISTS brain;

CREATE TABLE IF NOT EXISTS brain.conversation (
    conversation_id uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    title           text        NOT NULL,
    created_at      timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS brain.message (
    message_id      bigint      GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    conversation_id uuid        NOT NULL REFERENCES brain.conversation ON DELETE CASCADE,
    role            text        NOT NULL CHECK (role IN ('user', 'assistant', 'tool', 'error')),
    content         text        NOT NULL,
    tool_name       text,               -- role = tool: which tool ran
    tool_args       jsonb,              -- role = tool: what the brain asked for
    ok              boolean,            -- role = tool: did it succeed
    duration_ms     integer,            -- how long the brain or tool took
    model           text,               -- role = assistant: which model answered
    stats           jsonb,              -- role = assistant: token counts and rates from Ollama
    created_at      timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS message_conversation_idx
    ON brain.message (conversation_id, message_id);
