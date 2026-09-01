import { NextRequest, NextResponse } from "next/server";

const SESSION_COOKIE = process.env.SESSION_COOKIE_NAME || "risklocker_session";

export function middleware(request: NextRequest) {
  const { pathname, search } = request.nextUrl;
  if (!request.cookies.get(SESSION_COOKIE)) {
    const host = request.headers.get("x-forwarded-host") || request.headers.get("host");
    const proto = request.headers.get("x-forwarded-proto") || (request.url.startsWith("https") ? "https" : "http");
    const origin = host ? `${proto}://${host}` : request.nextUrl.origin;
    const loginUrl = new URL(`/login?redirect=${encodeURIComponent(pathname + search)}`, origin);
    return NextResponse.redirect(loginUrl);
  }
  return NextResponse.next();
}

export const config = {
  matcher: [
    "/upload/:path*",
    "/sessions/:path*",
    "/batches/:path*",
    "/builder/:path*",
    "/extraction/:path*",
    "/settings/:path*",
    "/admin/:path*",
    "/trash/:path*",
    "/client-records/:path*",
    "/inbox/:path*",
    "/review/:path*",
  ],
};
