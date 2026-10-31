import { cn } from "@/lib/utils";

import { type PaletteSection, paletteOptionId } from "./palette-types";

interface PaletteResultsProps {
  sections: PaletteSection[];
  listId: string;
  activeIndex: number;
  onActivate: (index: number) => void;
}

/** Grouped options inside one listbox. Group headings are role=group labels, not selectable. */
export function PaletteResults({ sections, listId, activeIndex, onActivate }: PaletteResultsProps) {
  // Flat position of each section's first row, so options can be numbered without mutating during render.
  const starts = sections.map((_, i) => sections.slice(0, i).reduce((sum, section) => sum + section.rows.length, 0));
  return (
    <div id={listId} role="listbox" aria-label="Results" className="max-h-80 overflow-y-auto py-1">
      {sections.map((section, sectionIndex) => (
        <div key={section.id} role="group" aria-labelledby={`${listId}-${section.id}`}>
          <p id={`${listId}-${section.id}`} className="px-4 pb-1 pt-3 text-caption uppercase text-text-secondary">
            {section.label}
          </p>
          {section.rows.map((row, rowIndex) => {
            const position = starts[sectionIndex] + rowIndex;
            const isActive = position === activeIndex;
            return (
              // Enter on the input runs the highlighted row (aria-activedescendant), so no key handler is needed here.
              // eslint-disable-next-line jsx-a11y/click-events-have-key-events
              <div
                key={row.key}
                id={paletteOptionId(listId, position)}
                role="option"
                tabIndex={-1}
                aria-selected={isActive}
                onMouseDown={(event) => event.preventDefault()}
                onMouseMove={() => onActivate(position)}
                onClick={row.onSelect}
                className={cn(
                  "flex cursor-pointer items-center justify-between gap-3 px-4 py-2 text-sm text-text-primary",
                  isActive && "bg-brand-subtle text-brand-subtle-fg",
                )}
              >
                <span className="min-w-0">
                  <span className="block truncate font-medium">{row.label}</span>
                  {row.description && (
                    <span className="block truncate text-xs text-text-secondary">{row.description}</span>
                  )}
                </span>
                {row.kind && <span className="shrink-0 text-xs text-text-secondary">{row.kind}</span>}
              </div>
            );
          })}
        </div>
      ))}
    </div>
  );
}
