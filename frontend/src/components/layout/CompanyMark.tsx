import { absoluteLogoUrl } from "@/api/companySettings";
import type { Branding } from "@/api/types";
import { readableTextOn } from "@/lib/contrast";
import { cn } from "@/lib/utils";

interface CompanyMarkProps {
  branding: Branding | undefined;
  size?: "sm" | "lg";
  showName?: boolean;
}

const DEFAULT_BRAND = "#0F766E";

function initials(name: string): string {
  const words = name.trim().split(/\s+/).filter(Boolean);
  return (
    words
      .slice(0, 2)
      .map((word) => word[0]?.toUpperCase() ?? "")
      .join("") || "PF"
  );
}

/** The company's logo, or its initials on the brand colour when no logo has been uploaded. */
export function CompanyMark({ branding, size = "sm", showName = true }: CompanyMarkProps) {
  const name = branding?.company_name ?? "ProcuraFlow";
  const logo = absoluteLogoUrl(branding?.logo_url ?? null);
  const brand = /^#[0-9a-f]{6}$/i.test(branding?.brand_color ?? "") ? (branding?.brand_color as string) : DEFAULT_BRAND;
  const box = size === "lg" ? "h-12 w-12 text-lg" : "h-8 w-8 text-sm";

  return (
    <div className="flex min-w-0 items-center gap-2">
      {logo ? (
        <img src={logo} alt={`${name} logo`} className={cn("shrink-0 rounded-control object-contain", box)} />
      ) : (
        <div
          aria-hidden="true"
          className={cn("flex shrink-0 items-center justify-center rounded-control font-bold", box)}
          style={{ backgroundColor: brand, color: readableTextOn(brand) }}
        >
          {initials(name)}
        </div>
      )}
      {showName && <span className="truncate text-lg font-semibold text-text-primary">{name}</span>}
    </div>
  );
}
