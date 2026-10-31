import type { ReactElement } from "react";

import { cn } from "@/lib/utils";

import type { IllustrationName } from "./illustration-names";

/*
 * One original style for all of them: a 160x120 canvas, 2 px rounded outlines in the strong border colour, flat
 * fills from the brand tint and surface, and a single amber dot as the "look here" accent. Everything is token
 * coloured through classes, so dark mode follows the theme, and the SVG is decoration (aria-hidden).
 */
const LINE = "fill-none stroke-border-strong stroke-2 [stroke-linecap:round] [stroke-linejoin:round]";
const SURFACE = "fill-surface stroke-border-strong stroke-2 [stroke-linejoin:round]";
const TINT = "fill-brand-subtle stroke-brand stroke-2 [stroke-linejoin:round]";
const DOT = "fill-accent";

const SHAPES: Record<IllustrationName, ReactElement> = {
  inbox: (
    <>
      <path d="M30 70 L48 38 H112 L130 70 V96 a6 6 0 0 1 -6 6 H36 a6 6 0 0 1 -6 -6 Z" className={SURFACE} />
      <path d="M30 70 H62 a18 18 0 0 0 36 0 H130" className={TINT} />
      <path d="M62 52 H98 M68 61 H92" className={LINE} />
      <circle cx="122" cy="34" r="5" className={DOT} />
    </>
  ),
  search: (
    <>
      <rect x="26" y="26" width="76" height="68" rx="8" className={SURFACE} />
      <path d="M40 46 H88 M40 60 H72 M40 74 H80" className={LINE} />
      <circle cx="104" cy="70" r="22" className={TINT} />
      <path d="M120 86 L138 104" className="fill-none stroke-brand stroke-[5] [stroke-linecap:round]" />
      <circle cx="30" cy="100" r="5" className={DOT} />
    </>
  ),
  documents: (
    <>
      <rect x="46" y="22" width="68" height="82" rx="8" className={SURFACE} transform="rotate(6 80 63)" />
      <rect x="40" y="16" width="68" height="82" rx="8" className={SURFACE} />
      <path d="M54 38 H94 M54 52 H94 M54 66 H78" className={LINE} />
      <rect x="54" y="76" width="22" height="12" rx="3" className={TINT} />
      <circle cx="116" cy="26" r="5" className={DOT} />
    </>
  ),
  orders: (
    <>
      <path d="M22 34 H40 L52 78 H112 L124 46 H44" className={LINE} />
      <rect x="58" y="42" width="24" height="24" rx="4" className={TINT} />
      <rect x="86" y="50" width="20" height="16" rx="4" className={SURFACE} />
      <circle cx="64" cy="92" r="7" className={SURFACE} />
      <circle cx="104" cy="92" r="7" className={SURFACE} />
      <circle cx="130" cy="28" r="5" className={DOT} />
    </>
  ),
  approvals: (
    <>
      <rect x="34" y="24" width="72" height="80" rx="8" className={SURFACE} />
      <path d="M48 44 H92 M48 58 H92 M48 72 H72" className={LINE} />
      <circle cx="106" cy="82" r="22" className={TINT} />
      <path
        d="M95 82 L103 90 L118 74"
        className="fill-none stroke-brand stroke-[4] [stroke-linecap:round] [stroke-linejoin:round]"
      />
      <circle cx="30" cy="30" r="5" className={DOT} />
    </>
  ),
  suppliers: (
    <>
      <rect x="30" y="40" width="56" height="62" rx="6" className={SURFACE} />
      <rect x="86" y="62" width="44" height="40" rx="6" className={TINT} />
      <path d="M42 54 H52 M64 54 H74 M42 70 H52 M64 70 H74 M98 76 H108 M98 88 H108" className={LINE} />
      <path d="M58 102 V88 H66 V102" className={LINE} />
      <circle cx="108" cy="30" r="5" className={DOT} />
    </>
  ),
  files: (
    <>
      <path
        d="M26 40 a6 6 0 0 1 6 -6 H62 L72 46 H128 a6 6 0 0 1 6 6 V96 a6 6 0 0 1 -6 6 H32 a6 6 0 0 1 -6 -6 Z"
        className={SURFACE}
      />
      <path d="M26 58 H134" className={LINE} />
      <rect x="58" y="68" width="44" height="22" rx="4" className={TINT} />
      <path d="M68 79 H92" className="fill-none stroke-brand stroke-2 [stroke-linecap:round]" />
      <circle cx="128" cy="26" r="5" className={DOT} />
    </>
  ),
  error: (
    <>
      <path d="M22 78 H52 M108 78 H138" className={LINE} />
      <rect x="52" y="64" width="24" height="28" rx="6" className={SURFACE} />
      <rect x="84" y="64" width="24" height="28" rx="6" className={SURFACE} />
      <path d="M62 64 V54 M66 64 V54 M94 64 V54 M98 64 V54" className={LINE} />
      <path
        d="M78 36 L72 50 H84 L78 64"
        className="fill-none stroke-brand stroke-[3] [stroke-linecap:round] [stroke-linejoin:round]"
      />
      <circle cx="30" cy="40" r="5" className={DOT} />
    </>
  ),
};

export function Illustration({ name, className }: { name: IllustrationName; className?: string }) {
  return (
    <svg viewBox="0 0 160 120" aria-hidden="true" focusable="false" className={cn("h-28 w-36", className)}>
      {SHAPES[name]}
    </svg>
  );
}
