import { Monitor, Moon, Sun } from "lucide-react";

import { IconButton } from "@/components/ui/IconButton";
import { type ThemeMode, useTheme } from "@/lib/theme";

const NEXT_MODE: Record<ThemeMode, ThemeMode> = { light: "dark", dark: "system", system: "light" };
const LABEL: Record<ThemeMode, string> = { light: "Light", dark: "Dark", system: "System" };
const ICON: Record<ThemeMode, typeof Sun> = { light: Sun, dark: Moon, system: Monitor };

/** One button that steps through light, dark and system; the label names the current choice. */
export function ThemeToggle() {
  const { mode, setMode } = useTheme();
  const Icon = ICON[mode];
  return (
    <IconButton
      aria-label={`Theme: ${LABEL[mode]}. Switch to ${LABEL[NEXT_MODE[mode]]}`}
      icon={<Icon className="h-4 w-4" />}
      onClick={() => setMode(NEXT_MODE[mode])}
    />
  );
}
