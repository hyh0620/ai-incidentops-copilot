import { NextRequest, NextResponse } from "next/server";

import { DEMO_PERSONA_COOKIE, defaultDemoPersonaId, personaById, normalizeDemoPersonaId } from "@/lib/persona";

export function proxy(request: NextRequest) {
  const personaId = normalizeDemoPersonaId(request.cookies.get(DEMO_PERSONA_COOKIE)?.value || defaultDemoPersonaId);
  const persona = personaById(personaId);
  const pathname = request.nextUrl.pathname;

  if (pathname.startsWith("/admin") && persona.role !== "admin") {
    const url = request.nextUrl.clone();
    url.pathname = "/requester/dashboard";
    const response = NextResponse.redirect(url);
    response.cookies.set(DEMO_PERSONA_COOKIE, personaId, { path: "/", maxAge: 60 * 60 * 24 * 30, sameSite: "lax" });
    return response;
  }
  if (pathname.startsWith("/requester") && persona.role === "admin") {
    const url = request.nextUrl.clone();
    url.pathname = "/admin/dashboard";
    const response = NextResponse.redirect(url);
    response.cookies.set(DEMO_PERSONA_COOKIE, personaId, { path: "/", maxAge: 60 * 60 * 24 * 30, sameSite: "lax" });
    return response;
  }

  if (request.cookies.has(DEMO_PERSONA_COOKIE)) {
    return NextResponse.next();
  }

  const requestHeaders = new Headers(request.headers);
  const existingCookie = requestHeaders.get("cookie");
  const personaCookie = `${DEMO_PERSONA_COOKIE}=${personaId}`;
  requestHeaders.set("cookie", existingCookie ? `${existingCookie}; ${personaCookie}` : personaCookie);

  const response = NextResponse.next({ request: { headers: requestHeaders } });
  response.cookies.set(DEMO_PERSONA_COOKIE, personaId, {
    path: "/",
    maxAge: 60 * 60 * 24 * 30,
    sameSite: "lax"
  });
  return response;
}

export const config = {
  matcher: ["/", "/requester/:path*", "/admin/:path*"]
};
