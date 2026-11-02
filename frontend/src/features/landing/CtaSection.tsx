import { LandingLink } from "./LandingLink";

export function CtaSection() {
  return (
    <section aria-labelledby="cta-title" className="px-4 py-16 sm:px-6">
      <div className="mx-auto max-w-4xl space-y-5 rounded-hero bg-brand px-6 py-12 text-center text-on-brand">
        <h2 id="cta-title" className="text-display-sm sm:text-display-lg">
          See it with real-looking data
        </h2>
        <p className="mx-auto max-w-xl text-body">
          Sign in to the live demo with one click as a requester, approver, finance user or supplier.
        </p>
        <LandingLink to="/login?demo=1" variant="secondary" size="lg">
          Open the live demo
        </LandingLink>
      </div>
    </section>
  );
}

export function LandingFooter() {
  return (
    <footer className="border-t border-border bg-surface py-8">
      <div className="mx-auto flex max-w-6xl flex-wrap items-center justify-between gap-3 px-4 text-cell text-text-secondary sm:px-6">
        <p>ProcuraFlow. Self-hosted procure-to-pay.</p>
        <LandingLink to="/login" variant="ghost" size="sm">
          Sign in
        </LandingLink>
      </div>
    </footer>
  );
}
