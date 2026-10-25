import { absoluteLogoUrl } from "@/api/companySettings";
import type { Branding } from "@/api/types";
import { cn } from "@/lib/utils";

interface CompanyMarkProps {
  branding: Branding | undefined;
  size?: "sm" | "lg";
  showName?: boolean;
}

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
  const box = size === "lg" ? "h-12 w-12 text-lg" : "h-8 w-8 text-sm";

  return (
    <div className="flex min-w-0 items-center gap-2">
      {logo ? (
        <img src={logo} alt={`${name} logo`} className={cn("shrink-0 rounded-md object-contain", box)} />
      ) : (
        <div
          aria-hidden="true"
          className={cn("flex shrink-0 items-center justify-center rounded-md font-bold text-white", box)}
          style={{ backgroundColor: "var(--company-brand, #0F766E)" }}
        >
          {initials(name)}
        </div>
      )}
      {showName && <span className="truncate text-lg font-semibold text-slate-900">{name}</span>}
    </div>
  );
}
