import { ChevronDown } from "lucide-react";
import { useState } from "react";

import { FOCUS_RING } from "@/components/ui/focus";
import { cn } from "@/lib/utils";

import { FAQS } from "./landing-content";
import { SectionHeading } from "./SectionHeading";

/** Disclosure pattern: each question is a button with aria-expanded controlling its answer region. */
export function FaqSection() {
  const [openIds, setOpenIds] = useState<readonly string[]>([]);
  const toggle = (id: string) =>
    setOpenIds((ids) => (ids.includes(id) ? ids.filter((open) => open !== id) : [...ids, id]));

  return (
    <section aria-labelledby="faq-title" className="bg-surface py-16">
      <div className="mx-auto max-w-3xl space-y-8 px-4 sm:px-6">
        <SectionHeading id="faq-title" eyebrow="FAQ" title="Questions people ask" />
        <ul className="divide-y divide-border rounded-card border border-border">
          {FAQS.map((item) => {
            const isOpen = openIds.includes(item.id);
            return (
              <li key={item.id}>
                <h3>
                  <button
                    type="button"
                    id={`faq-q-${item.id}`}
                    aria-expanded={isOpen}
                    aria-controls={`faq-a-${item.id}`}
                    onClick={() => toggle(item.id)}
                    className={cn(
                      "flex min-h-11 w-full items-center justify-between gap-3 px-4 py-3 text-left text-body font-medium text-text-primary hover:bg-bg",
                      FOCUS_RING,
                    )}
                  >
                    {item.question}
                    <ChevronDown
                      aria-hidden="true"
                      className={cn("h-5 w-5 shrink-0 transition-transform duration-fast", isOpen && "rotate-180")}
                    />
                  </button>
                </h3>
                <div
                  id={`faq-a-${item.id}`}
                  role="region"
                  aria-labelledby={`faq-q-${item.id}`}
                  hidden={!isOpen}
                  className="px-4 pb-4 text-cell text-text-secondary"
                >
                  {item.answer}
                </div>
              </li>
            );
          })}
        </ul>
      </div>
    </section>
  );
}
