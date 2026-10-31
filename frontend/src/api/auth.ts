import { useMutation } from "@tanstack/react-query";

import { apiClient } from "./client";

export interface TokenPasswordInput {
  token: string;
  password: string;
}

export interface ChangePasswordInput {
  current_password: string;
  new_password: string;
}

export function useRequestPasswordReset() {
  return useMutation({
    mutationFn: async (email: string) => {
      await apiClient.post("/auth/password-reset/request", { email });
    },
  });
}

export function useConfirmPasswordReset() {
  return useMutation({
    mutationFn: async (input: TokenPasswordInput) => {
      await apiClient.post("/auth/password-reset/confirm", input);
    },
  });
}

export function useAcceptInvitation() {
  return useMutation({
    mutationFn: async (input: TokenPasswordInput) => {
      await apiClient.post("/auth/invitations/accept", input);
    },
  });
}

export function useChangePassword() {
  return useMutation({
    mutationFn: async (input: ChangePasswordInput) => {
      await apiClient.post("/auth/change-password", input);
    },
  });
}
