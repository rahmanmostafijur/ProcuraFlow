import type { ElementType, ReactNode } from "react";

/** Content for assistive technology only. */
export function VisuallyHidden({ children, as: Tag = "span" }: { children: ReactNode; as?: ElementType }) {
  return <Tag className="sr-only">{children}</Tag>;
}
