// Must be a literal process.env.NEXT_PUBLIC_* reference so Next can inline it at build time.
export const env = {
  apiUrl: process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000",
} as const;
