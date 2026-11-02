import { useEffect } from "react";

import { SecuritySection, SelfHostedSection, TrustSection } from "./AssuranceSections";
import { FeaturesSection, HowItWorksSection, ProblemSection } from "./ContentSections";
import { CtaSection, LandingFooter } from "./CtaSection";
import { FaqSection } from "./FaqSection";
import { HeroSection } from "./HeroSection";
import { LandingHeader } from "./LandingHeader";

export const LANDING_TITLE = "ProcuraFlow: self-hosted procure-to-pay with numbers you can trust";

export function LandingPage() {
  useEffect(() => {
    const previous = document.title;
    document.title = LANDING_TITLE;
    return () => {
      document.title = previous;
    };
  }, []);

  return (
    <div className="min-h-screen bg-bg text-text-primary">
      <LandingHeader />
      <main>
        <HeroSection />
        <ProblemSection />
        <HowItWorksSection />
        <FeaturesSection />
        <TrustSection />
        <SecuritySection />
        <SelfHostedSection />
        <FaqSection />
        <CtaSection />
      </main>
      <LandingFooter />
    </div>
  );
}
