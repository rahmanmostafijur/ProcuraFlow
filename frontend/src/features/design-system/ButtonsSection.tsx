import { Download, Plus, Trash2 } from "lucide-react";

import { Button, type ButtonVariant } from "@/components/ui/Button";
import { FORCED_FOCUS } from "@/components/ui/focus";
import { IconButton } from "@/components/ui/IconButton";

import { Section, StateCell, StateRow, SubHeading, ThemePair } from "./showcase";

const VARIANTS: ButtonVariant[] = ["primary", "secondary", "danger", "ghost"];

// A real :hover cannot be pinned from CSS, so the hover look is repeated as plain classes.
const FORCED_HOVER: Record<ButtonVariant, string> = {
  primary: "bg-brand-hover",
  secondary: "bg-bg",
  danger: "opacity-90",
  ghost: "bg-bg text-text-primary",
};

function VariantRow({ variant }: { variant: ButtonVariant }) {
  return (
    <StateRow>
      <StateCell label={`${variant}: default`}>
        <Button variant={variant}>Label</Button>
      </StateCell>
      <StateCell label="Hover (forced)">
        <Button variant={variant} className={FORCED_HOVER[variant]}>
          Label
        </Button>
      </StateCell>
      <StateCell label="Focus (forced)">
        <Button variant={variant} className={FORCED_FOCUS}>
          Label
        </Button>
      </StateCell>
      <StateCell label="Disabled">
        <Button variant={variant} disabled>
          Label
        </Button>
      </StateCell>
      <StateCell label="Loading">
        <Button variant={variant} loading>
          Saving
        </Button>
      </StateCell>
      <StateCell label="With icon">
        <Button variant={variant} leadingIcon={<Plus aria-hidden="true" className="h-4 w-4" />}>
          New
        </Button>
      </StateCell>
    </StateRow>
  );
}

export function ButtonsSection() {
  return (
    <Section
      id="buttons"
      title="Buttons"
      intro="One primary action per view; everything else is secondary or a quiet ghost button. Icon-only buttons must carry an aria-label."
    >
      <ThemePair>
        <div className="space-y-6">
          {VARIANTS.map((variant) => (
            <VariantRow key={variant} variant={variant} />
          ))}
          <div>
            <SubHeading>Sizes</SubHeading>
            <StateRow>
              <Button size="sm">Small</Button>
              <Button size="md">Medium</Button>
              <Button size="lg">Large</Button>
            </StateRow>
          </div>
          <div>
            <SubHeading>Icon buttons</SubHeading>
            <StateRow>
              <StateCell label="Default">
                <IconButton aria-label="Download" icon={<Download className="h-4 w-4" />} />
              </StateCell>
              <StateCell label="Hover (forced)">
                <IconButton
                  aria-label="Download hovered"
                  className="bg-bg text-text-primary"
                  icon={<Download className="h-4 w-4" />}
                />
              </StateCell>
              <StateCell label="Focus (forced)">
                <IconButton
                  aria-label="Download focused"
                  className={FORCED_FOCUS}
                  icon={<Download className="h-4 w-4" />}
                />
              </StateCell>
              <StateCell label="Disabled">
                <IconButton aria-label="Download disabled" disabled icon={<Download className="h-4 w-4" />} />
              </StateCell>
              <StateCell label="Loading">
                <IconButton aria-label="Downloading" loading icon={<Download className="h-4 w-4" />} />
              </StateCell>
              <StateCell label="Danger">
                <IconButton aria-label="Delete row" variant="danger" icon={<Trash2 className="h-4 w-4" />} />
              </StateCell>
            </StateRow>
          </div>
        </div>
      </ThemePair>
    </Section>
  );
}
