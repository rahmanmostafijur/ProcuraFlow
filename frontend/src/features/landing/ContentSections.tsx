import { Card } from "@/components/ui/Card";

import { FEATURES, HOW_STEPS, PROBLEMS, type IconItem } from "./landing-content";
import { SectionHeading } from "./SectionHeading";

function IconCard({ item }: { item: IconItem }) {
  return (
    <Card padding="lg" className="space-y-3">
      <span className="flex h-10 w-10 items-center justify-center rounded-control bg-brand-subtle text-brand-subtle-fg">
        <item.icon aria-hidden="true" className="h-5 w-5" />
      </span>
      <h3 className="text-title text-text-primary">{item.title}</h3>
      <p className="text-cell text-text-secondary">{item.body}</p>
    </Card>
  );
}

export function ProblemSection() {
  return (
    <section aria-labelledby="problem-title" className="bg-surface py-16">
      <div className="mx-auto max-w-6xl space-y-10 px-4 sm:px-6">
        <SectionHeading id="problem-title" eyebrow="The problem today" title="Buying without a system costs money">
          Most small and mid-sized teams buy through email, chat and a spreadsheet. It works until the numbers have to
          be right.
        </SectionHeading>
        <ul className="grid gap-4 md:grid-cols-3">
          {PROBLEMS.map((item) => (
            <li key={item.title}>
              <IconCard item={item} />
            </li>
          ))}
        </ul>
      </div>
    </section>
  );
}

export function HowItWorksSection() {
  return (
    <section aria-labelledby="how-title" className="py-16">
      <div className="mx-auto max-w-6xl space-y-10 px-4 sm:px-6">
        <SectionHeading id="how-title" eyebrow="How it works" title="Six steps from request to paid" />
        <ol className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {HOW_STEPS.map((step, index) => (
            <li key={step.title}>
              <Card padding="lg" className="h-full space-y-2">
                <p className="text-caption uppercase text-brand">Step {index + 1}</p>
                <h3 className="text-title text-text-primary">{step.title}</h3>
                <p className="text-cell text-text-secondary">{step.body}</p>
              </Card>
            </li>
          ))}
        </ol>
      </div>
    </section>
  );
}

export function FeaturesSection() {
  return (
    <section aria-labelledby="features-title" className="bg-surface py-16">
      <div className="mx-auto max-w-6xl space-y-10 px-4 sm:px-6">
        <SectionHeading id="features-title" eyebrow="What is included" title="Everything between request and payment" />
        <ul className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {FEATURES.map((item) => (
            <li key={item.title}>
              <IconCard item={item} />
            </li>
          ))}
        </ul>
      </div>
    </section>
  );
}
