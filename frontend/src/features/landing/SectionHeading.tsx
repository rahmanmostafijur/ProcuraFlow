import type { ReactNode } from "react";

interface SectionHeadingProps {
  id: string;
  eyebrow: string;
  title: string;
  children?: ReactNode;
}

export function SectionHeading({ id, eyebrow, title, children }: SectionHeadingProps) {
  return (
    <div className="mx-auto max-w-2xl text-center">
      <p className="text-caption uppercase text-brand">{eyebrow}</p>
      <h2 id={id} className="mt-2 text-display-sm text-text-primary sm:text-display-lg">
        {title}
      </h2>
      {children && <p className="mt-4 text-body text-text-secondary">{children}</p>}
    </div>
  );
}
