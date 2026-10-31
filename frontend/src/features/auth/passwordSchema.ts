import { z } from "zod";

// Mirrors the API: 8 to 128 characters.
export const newPasswordSchema = z
  .string()
  .min(8, "Password must be at least 8 characters")
  .max(128, "Password must be at most 128 characters");

export const setPasswordSchema = z
  .object({ password: newPasswordSchema, confirm: z.string().min(1, "Confirm your password") })
  .refine((values) => values.password === values.confirm, {
    message: "Passwords do not match",
    path: ["confirm"],
  });

export type SetPasswordValues = z.infer<typeof setPasswordSchema>;
