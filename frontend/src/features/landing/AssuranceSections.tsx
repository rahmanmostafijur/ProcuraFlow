import { Check } from "lucide-react";

import { Card } from "@/components/ui/Card";

import { SECURITY_POINTS, TRUST_POINTS } from "./landing-content";
import { SAMPLE_LINES, SAMPLE_TOTALS } from "./pipeline-data";
import { SectionHeading } from "./SectionHeading";

export function TrustSection() {
  return (
    <section aria-labelledby="trust-title" className="py-16">
      <div className="mx-auto max-w-6xl space-y-10 px-4 sm:px-6">
        <SectionHeading id="trust-title" eyebrow="Numbers you can trust" title="Totals that agree, everywhere">
          A procurement tool is only useful if finance believes its figures. These rules are built in, not configured.
        </SectionHeading>
        <div className="grid gap-4 lg:grid-cols-[1fr_1fr]">
          <ul className="space-y-4">
            {TRUST_POINTS.map((point) => (
              <li key={point.title} className="flex gap-3">
                <span className="mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-success-bg text-success-fg">
                  <Check aria-hidden="true" className="h-4 w-4" />
                </span>
                <div>
                  <h3 className="text-title text-text-primary">{point.title}</h3>
                  <p className="text-cell text-text-secondary">{point.body}</p>
                </div>
              </li>
            ))}
          </ul>
          <Card padding="lg" className="space-y-2">
            <h3 className="text-title text-text-primary">A worked example</h3>
            <p className="text-cell text-text-secondary">
              Tax of 20% on {SAMPLE_LINES[1].net} is 11.994, which rounds half-up to {SAMPLE_LINES[1].tax}. The two
              rounded line taxes ({SAMPLE_LINES[0].tax} + {SAMPLE_LINES[1].tax}) give {SAMPLE_TOTALS.tax}, so net{" "}
              {SAMPLE_TOTALS.net} + tax {SAMPLE_TOTALS.tax} = {SAMPLE_TOTALS.gross} {SAMPLE_TOTALS.currency}, on the
              order, the invoice and the dashboard alike.
            </p>
          </Card>
        </div>
      </div>
    </section>
  );
}

export function SecuritySection() {
  return (
    <section aria-labelledby="security-title" className="bg-surface py-16">
      <div className="mx-auto max-w-6xl space-y-10 px-4 sm:px-6">
        <SectionHeading id="security-title" eyebrow="Security" title="Built to be audited">
          Controls that matter for money and supplier data, on by default.
        </SectionHeading>
        <ul className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {SECURITY_POINTS.map((point) => (
            <li key={point.title}>
              <Card padding="lg" className="h-full space-y-2">
                <point.icon aria-hidden="true" className="h-6 w-6 text-brand" />
                <h3 className="text-title text-text-primary">{point.title}</h3>
                <p className="text-cell text-text-secondary">{point.body}</p>
              </Card>
            </li>
          ))}
        </ul>
      </div>
    </section>
  );
}

export function SelfHostedSection() {
  return (
    <section aria-labelledby="hosted-title" className="py-16">
      <div className="mx-auto max-w-3xl space-y-4 px-4 text-center sm:px-6">
        <SectionHeading id="hosted-title" eyebrow="Pricing model" title="Self-hosted, one-time licence">
          You run ProcuraFlow on your own server or hosting account. You buy the licence once, keep your data in your
          own PostgreSQL database, and decide when to upgrade. There are no per-seat fees and no monthly subscription
          for the software.
        </SectionHeading>
      </div>
    </section>
  );
}
