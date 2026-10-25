import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render } from "@testing-library/react";
import type { ReactElement } from "react";
import { MemoryRouter } from "react-router-dom";
import { vi } from "vitest";

import { apiClient } from "@/api/client";
import type { User } from "@/api/types";
import { ToastProvider } from "@/components/ui/ToastProvider";
import { AuthContext } from "@/lib/auth-context";

export const testUser: User = {
  id: 1,
  email: "me@example.com",
  full_name: "Me Myself",
  is_active: true,
  role: { id: 1, name: "tester", description: null, permissions: [] },
  created_at: "2026-01-01T00:00:00Z",
};

interface RenderOptions {
  permissions?: string[];
  user?: User;
  route?: string;
}

/** Renders with query, router, toast and auth providers; the signed-in user holds exactly `permissions`. */
export function renderWithProviders(
  ui: ReactElement,
  { permissions = [], user = testUser, route = "/" }: RenderOptions = {},
) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <AuthContext.Provider
        value={{
          user,
          isLoading: false,
          login: () => Promise.resolve(),
          logout: () => undefined,
          hasPermission: (code) => permissions.includes(code),
        }}
      >
        <ToastProvider>
          <MemoryRouter initialEntries={[route]}>{ui}</MemoryRouter>
        </ToastProvider>
      </AuthContext.Provider>
    </QueryClientProvider>,
  );
}

/** Answers GET calls by exact path; an unlisted path fails the test loudly. */
export function mockGet(responses: Record<string, unknown>) {
  return vi.spyOn(apiClient, "get").mockImplementation((url, config) => {
    const answer = responses[url];
    if (answer === undefined) return Promise.reject(new Error(`unexpected GET ${url}`));
    const data =
      typeof answer === "function"
        ? (answer as (p?: Record<string, unknown>) => unknown)(config?.params as Record<string, unknown> | undefined)
        : answer;
    return Promise.resolve({ data });
  });
}
