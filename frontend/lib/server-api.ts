import { cookies } from "next/headers";

import { buildPersonaHeaders, DEMO_PERSONA_COOKIE, defaultDemoPersonaId, normalizeDemoPersonaId } from "@/lib/persona";

export const serverApiBase = process.env.API_BASE_URL || process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";

export async function getServerDemoPersonaId(): Promise<string> {
  const cookieStore = await cookies();
  return normalizeDemoPersonaId(cookieStore.get(DEMO_PERSONA_COOKIE)?.value || defaultDemoPersonaId);
}

export async function serverFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const personaId = await getServerDemoPersonaId();
  const response = await fetch(`${serverApiBase}${path}`, {
    ...init,
    cache: "no-store",
    headers: buildPersonaHeaders(init?.headers, personaId)
  });
  if (!response.ok) {
    throw new Error(`API request failed: ${response.status} ${path}`);
  }
  return response.json() as Promise<T>;
}
