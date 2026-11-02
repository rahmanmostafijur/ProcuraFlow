import { LandingLink } from "./LandingLink";
import { PipelineDemo } from "./PipelineDemo";

export function HeroSection() {
  return (
    <section
      aria-labelledby="hero-title"
      className="mx-auto grid max-w-6xl gap-10 px-4 py-12 sm:px-6 lg:grid-cols-2 lg:items-center lg:py-20"
    >
      <div className="space-y-6">
        <p className="text-caption uppercase text-brand">Self-hosted procure-to-pay</p>
        <h1 id="hero-title" className="text-display-md text-text-primary sm:text-display-xl">
          Procurement numbers you can trust. No monthly fee.
        </h1>
        <p className="max-w-xl text-body text-text-secondary">
          ProcuraFlow takes a purchase from request to paid invoice in one place. Every amount is exact, every total
          reconciles across screens, and you pay once for the licence instead of every month for every seat.
        </p>
        <div className="flex flex-wrap gap-3">
          <LandingLink to="/login?demo=1" size="lg">
            Try the live demo
          </LandingLink>
          <LandingLink to="/login" variant="secondary" size="lg">
            Sign in
          </LandingLink>
        </div>
        <p className="text-cell text-text-secondary">The demo needs no sign-up and runs on sample data.</p>
      </div>
      <PipelineDemo />
    </section>
  );
}
