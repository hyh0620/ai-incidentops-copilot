import { NextRequest, NextResponse } from "next/server";

import { DEMO_PERSONA_COOKIE, defaultDemoPersonaId } from "@/lib/persona";

function defaultPersonaForPath(pathname: string) {
  return pathname.startsWith("/admin") ? "7" : defaultDemoPersonaId;
}

export function proxy(request: NextRequest) {
  if (request.cookies.has(DEMO_PERSONA_COOKIE)) {
    return NextResponse.next();
  }

  const personaId = defaultPersonaForPath(request.nextUrl.pathname);
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
