import { buildPersonaHeaders, personaIdFromCookie } from "@/lib/persona";

export const publicApiBase = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";
export const serverApiBase = process.env.API_BASE_URL || publicApiBase;

export async function clientFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const personaId = typeof document === "undefined" ? undefined : personaIdFromCookie(document.cookie);
  const response = await fetch(`${publicApiBase}${path}`, {
    ...init,
    headers: buildPersonaHeaders(init?.headers, personaId)
  });
  if (!response.ok) {
    const message = await response.text();
    throw new Error(message || `API request failed: ${response.status}`);
  }
  return response.json() as Promise<T>;
}
