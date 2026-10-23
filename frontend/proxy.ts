import { NextResponse, type NextRequest } from "next/server";

import { SESSION_COOKIE, SESSION_MAX_AGE } from "@/lib/session";

export function proxy(request: NextRequest) {
  const response = NextResponse.next();
  if (!request.cookies.has(SESSION_COOKIE)) {
    response.cookies.set(SESSION_COOKIE, crypto.randomUUID(), {
      httpOnly: true,
      sameSite: "lax",
      secure: process.env.NODE_ENV === "production",
      maxAge: SESSION_MAX_AGE,
      path: "/",
    });
  }
  return response;
}

export const config = {
  matcher: "/",
};
