import type { ReactNode } from "react";

import { cn } from "@/lib/utils";

import { type DiffLineKind, diffLines } from "./diff-lines";

export interface FieldChange {
  field: string;
  before: ReactNode;
  after: ReactNode;
}

type DiffViewerProps =
  | { changes: FieldChange[]; before?: never; after?: never; label?: string }
  | { before: string; after: string; changes?: never; label?: string };

const MARKS: Record<DiffLineKind, { sign: string; word: string; row: string }> = {
  added: { sign: "+", word: "Added", row: "bg-success-bg text-success-fg" },
  removed: { sign: "−", word: "Removed", row: "bg-danger-bg text-danger-fg" },
  same: { sign: " ", word: "Unchanged", row: "text-text-primary" },
};

const EMPTY = "—";

function FieldDiff({ changes }: { changes: FieldChange[] }) {
  return (
    <table className="w-full text-sm">
      <thead>
        <tr className="text-left text-caption uppercase text-text-secondary">
          <th scope="col" className="py-2 pr-4">
            Field
          </th>
          <th scope="col" className="py-2 pr-4">
            Before
          </th>
          <th scope="col" className="py-2">
            After
          </th>
        </tr>
      </thead>
      <tbody className="divide-y divide-border">
        {changes.map((change) => (
          <tr key={change.field} className="align-top">
            <th scope="row" className="py-2 pr-4 text-left font-medium text-text-primary">
              {change.field}
            </th>
            <td className="py-2 pr-4">
              <span className={cn("inline-flex gap-1.5 rounded-control px-2 py-0.5", MARKS.removed.row)}>
                <span aria-hidden="true" className="font-mono font-semibold">
                  {MARKS.removed.sign}
                </span>
                <span className="sr-only">{MARKS.removed.word}: </span>
                <del>{change.before ?? EMPTY}</del>
              </span>
            </td>
            <td className="py-2">
              <span className={cn("inline-flex gap-1.5 rounded-control px-2 py-0.5", MARKS.added.row)}>
                <span aria-hidden="true" className="font-mono font-semibold">
                  {MARKS.added.sign}
                </span>
                <span className="sr-only">{MARKS.added.word}: </span>
                <ins className="no-underline">{change.after ?? EMPTY}</ins>
              </span>
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

function TextDiff({ before, after }: { before: string; after: string }) {
  const lines = diffLines(before, after);
  return (
    <div className="overflow-x-auto rounded-control border border-border font-mono text-xs">
      {lines.map((line, index) => {
        const mark = MARKS[line.kind];
        return (
          <div key={index} className={cn("flex gap-2 px-3 py-0.5", mark.row)}>
            <span aria-hidden="true" className="w-3 shrink-0 select-none font-semibold">
              {mark.sign}
            </span>
            <span className="sr-only">{mark.word}: </span>
            <span className="whitespace-pre-wrap break-words">{line.text || " "}</span>
          </div>
        );
      })}
    </div>
  );
}

/** Before/after for field edits or text. Added and removed are marked with + and − and a spoken word, not colour alone. */
export function DiffViewer(props: DiffViewerProps) {
  return (
    <div role="group" aria-label={props.label ?? "Changes"}>
      {props.changes ? <FieldDiff changes={props.changes} /> : <TextDiff before={props.before} after={props.after} />}
    </div>
  );
}
