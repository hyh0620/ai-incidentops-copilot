export const DEMO_PERSONA_COOKIE = "incidentops_demo_user_id";

export type DemoPersonaRole = "requester" | "admin";

export interface DemoPersona {
  id: string;
  label: string;
  role: DemoPersonaRole;
  roleLabel: string;
  description: string;
}

export const demoPersonas: DemoPersona[] = [
  { id: "1", label: "报障员工 A", role: "requester", roleLabel: "请求人", description: "只能查看和提交自己的工单" },
  { id: "2", label: "报障员工 B", role: "requester", roleLabel: "请求人", description: "用于验证请求人之间的数据隔离" },
  { id: "7", label: "运维管理员", role: "admin", roleLabel: "管理员", description: "可查看全部工单、复核和统计" }
];

export const defaultDemoPersonaId = "1";

export function normalizeDemoPersonaId(value: string | number | null | undefined): string {
  const candidate = String(value ?? "").trim();
  return demoPersonas.some((persona) => persona.id === candidate) ? candidate : defaultDemoPersonaId;
}

export function parseCookieValue(cookieHeader: string, name: string): string | null {
  const parts = cookieHeader.split(";").map((part) => part.trim());
  const prefix = `${name}=`;
  const matched = parts.find((part) => part.startsWith(prefix));
  return matched ? decodeURIComponent(matched.slice(prefix.length)) : null;
}

export function personaIdFromCookie(cookieHeader: string | undefined | null): string {
  return normalizeDemoPersonaId(parseCookieValue(cookieHeader || "", DEMO_PERSONA_COOKIE));
}

export function personaById(id: string | number | null | undefined): DemoPersona {
  const normalized = normalizeDemoPersonaId(id);
  return demoPersonas.find((persona) => persona.id === normalized) || demoPersonas[0];
}

export function buildPersonaHeaders(existing?: HeadersInit, personaId = defaultDemoPersonaId): Headers {
  const headers = new Headers(existing);
  headers.set("X-Demo-User-Id", normalizeDemoPersonaId(personaId));
  return headers;
}
