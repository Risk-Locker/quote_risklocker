"use client";

export function apiErrorMessage(err: unknown): string {
  return err instanceof Error ? err.message : "Something went wrong.";
}
