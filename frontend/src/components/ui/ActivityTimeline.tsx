import { type FormEvent, type ReactNode, useId, useState } from "react";

import { formatDateTime, formatRelative } from "@/lib/format";

import { Button } from "./Button";
import { Textarea } from "./Textarea";

export interface ActivityEvent {
  id: string | number;
  actor: string;
  /** What happened, e.g. "approved the request" or "added a comment". */
  action: ReactNode;
  at: string;
  /** Free text attached to the event (a comment or rejection reason). */
  comment?: string;
}

interface ActivityTimelineProps {
  events: ActivityEvent[];
  /** Newest first when true (the default for activity feeds). */
  newestFirst?: boolean;
  /** Shows a comment box when given. May be async; the box clears on success and keeps the text on failure. */
  onAddComment?: (text: string) => void | Promise<void>;
  /** Injectable for deterministic relative times in tests. */
  now?: Date;
  emptyText?: string;
}

function initials(name: string): string {
  return name
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0].toUpperCase())
    .join("");
}

function CommentComposer({ onAddComment }: { onAddComment: (text: string) => void | Promise<void> }) {
  const inputId = useId();
  const [text, setText] = useState("");
  const [posting, setPosting] = useState(false);
  const [failed, setFailed] = useState(false);

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    const trimmed = text.trim();
    if (!trimmed) return;
    setPosting(true);
    setFailed(false);
    try {
      await onAddComment(trimmed);
      setText("");
    } catch {
      setFailed(true);
    } finally {
      setPosting(false);
    }
  };

  return (
    <form onSubmit={(event) => void submit(event)} className="space-y-2 border-t border-border pt-4">
      <label htmlFor={inputId} className="block text-sm font-medium text-text-primary">
        Add a comment
      </label>
      <Textarea
        id={inputId}
        rows={3}
        value={text}
        onChange={(event) => setText(event.target.value)}
        error={failed ? "The comment could not be posted. Try again." : undefined}
      />
      <Button type="submit" size="sm" loading={posting} disabled={!text.trim()}>
        Post comment
      </Button>
    </form>
  );
}

export function ActivityTimeline({
  events,
  newestFirst = true,
  onAddComment,
  now,
  emptyText = "No activity yet.",
}: ActivityTimelineProps) {
  const ordered = [...events].sort((a, b) => (newestFirst ? -1 : 1) * a.at.localeCompare(b.at));
  return (
    <section aria-label="Activity" className="space-y-4">
      {ordered.length === 0 ? (
        <p className="text-sm text-text-secondary">{emptyText}</p>
      ) : (
        <ol className="space-y-5">
          {ordered.map((event) => (
            <li key={event.id} className="flex gap-3">
              <span
                aria-hidden="true"
                className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-brand-subtle text-xs font-semibold text-brand-subtle-fg"
              >
                {initials(event.actor)}
              </span>
              <div className="min-w-0 flex-1">
                <p className="text-sm text-text-primary">
                  <span className="font-semibold">{event.actor}</span> {event.action}
                </p>
                <time dateTime={event.at} title={formatDateTime(event.at)} className="text-xs text-text-secondary">
                  {formatRelative(event.at, now)}
                </time>
                {event.comment && (
                  <blockquote className="mt-2 rounded-control border-l-4 border-border-strong bg-bg px-3 py-2 text-sm text-text-primary">
                    {event.comment}
                  </blockquote>
                )}
              </div>
            </li>
          ))}
        </ol>
      )}
      {onAddComment && <CommentComposer onAddComment={onAddComment} />}
    </section>
  );
}
