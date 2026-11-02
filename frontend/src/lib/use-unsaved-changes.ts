import { useEffect } from "react";

/**
 * Asks the browser to confirm before the tab is closed or reloaded while a form has edits that are not saved.
 * The app uses BrowserRouter, which cannot block in-app navigation, so this covers leaving the page only.
 */
export function useUnsavedChangesWarning(isDirty: boolean): void {
  useEffect(() => {
    if (!isDirty) return;
    const onBeforeUnload = (event: BeforeUnloadEvent) => {
      event.preventDefault();
      // Some browsers still require a returnValue to show the prompt.
      event.returnValue = "";
    };
    window.addEventListener("beforeunload", onBeforeUnload);
    return () => window.removeEventListener("beforeunload", onBeforeUnload);
  }, [isDirty]);
}
