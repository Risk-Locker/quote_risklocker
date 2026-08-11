import { NextRequest, NextResponse } from "next/server";

const SESSION_COOKIE = process.env.SESSION_COOKIE_NAME || "risklocker_session";

export function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl;
  if (!request.cookies.get(SESSION_COOKIE)) {
    const url = request.nextUrl.clone();
    url.pathname = "/login";
    url.search = "";
    return NextResponse.redirect(url);
  }
  return NextResponse.next();
}

export const config = {
  matcher: [
    "/upload/:path*",
    "/sessions/:path*",
    "/batches/:path*",
    "/builder/:path*",
    "/settings/:path*",
    "/admin/:path*",
    "/trash/:path*",
    "/client-records/:path*",
    "/inbox/:path*",
    "/review/:path*",
  ],
};
