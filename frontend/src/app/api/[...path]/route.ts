import type { NextRequest } from "next/server";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

type RouteContext = { params: Promise<{ path: string[] }> };

const HOP_BY_HOP_HEADERS = new Set([
  "connection",
  "keep-alive",
  "proxy-authenticate",
  "proxy-authorization",
  "te",
  "trailer",
  "transfer-encoding",
  "upgrade",
]);

function configuredBackendOrigin(): URL {
  const raw = process.env.BACKEND_API_ORIGIN || (process.env.NODE_ENV === "development" ? "http://127.0.0.1:8100" : "");
  if (!raw) throw new Error("BACKEND_API_ORIGIN is not configured.");
  const url = new URL(raw);
  if (!['http:', 'https:'].includes(url.protocol) || url.username || url.password || url.pathname !== "/") {
    throw new Error("BACKEND_API_ORIGIN must be an HTTP(S) origin without credentials or a path.");
  }
  return url;
}

async function proxy(request: NextRequest, context: RouteContext): Promise<Response> {
  try {
    const origin = configuredBackendOrigin();
    const { path } = await context.params;
    const encodedPath = path.map(encodeURIComponent).join("/");
    const target = new URL(`/api/${encodedPath}${request.nextUrl.search}`, origin);
    const headers = new Headers(request.headers);
    headers.delete("host");
    headers.delete("content-length");
    for (const header of HOP_BY_HOP_HEADERS) headers.delete(header);

    const upstream = await fetch(target, {
      method: request.method,
      headers,
      body: request.method === "GET" || request.method === "HEAD" ? undefined : request.body,
      redirect: "manual",
      cache: "no-store",
      duplex: "half",
    } as RequestInit & { duplex: "half" });
    const responseHeaders = new Headers(upstream.headers);
    for (const header of HOP_BY_HOP_HEADERS) responseHeaders.delete(header);
    return new Response(upstream.body, {
      status: upstream.status,
      statusText: upstream.statusText,
      headers: responseHeaders,
    });
  } catch {
    return Response.json(
      { error: { code: "dependency_unavailable", message: "The application service is temporarily unavailable." } },
      { status: 503 },
    );
  }
}

export const GET = proxy;
export const HEAD = proxy;
export const POST = proxy;
export const PUT = proxy;
export const PATCH = proxy;
export const DELETE = proxy;
export const OPTIONS = proxy;
