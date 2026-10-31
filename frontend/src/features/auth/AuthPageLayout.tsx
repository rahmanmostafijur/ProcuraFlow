import type { ReactNode } from "react";

interface AuthPageLayoutProps {
  title: string;
  description?: string;
  children: ReactNode;
}

/** The centred card shared by the public account pages (forgot, reset, accept invitation). */
export function AuthPageLayout({ title, description, children }: AuthPageLayoutProps) {
  return (
    <div className="flex min-h-screen items-center justify-center bg-slate-50 px-4">
      <div className="w-full max-w-sm">
        <div className="mb-8 flex flex-col items-center gap-2 text-center">
          <h1 className="text-xl font-semibold text-slate-900">{title}</h1>
          {description && <p className="text-sm text-slate-500">{description}</p>}
        </div>
        {children}
      </div>
    </div>
  );
}
