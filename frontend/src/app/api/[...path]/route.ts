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
  const raw = process.env.BACKEND_API_ORIGIN || "http://127.0.0.1:8100";
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
    const resolvedParams = await context.params;
    const pathSegments = resolvedParams?.path || [];
    const encodedPath = Array.isArray(pathSegments)
      ? pathSegments.map(encodeURIComponent).join("/")
      : String(pathSegments);
    const target = new URL(`/api/${encodedPath}${request.nextUrl.search}`, origin);

    const headers = new Headers(request.headers);
    headers.delete("host");
    for (const header of HOP_BY_HOP_HEADERS) headers.delete(header);

    let body: BodyInit | undefined = undefined;
    if (request.method !== "GET" && request.method !== "HEAD") {
      const buffer = await request.arrayBuffer();
      if (buffer.byteLength > 0) {
        body = buffer;
      }
    }

    const upstream = await fetch(target, {
      method: request.method,
      headers,
      body,
      redirect: "manual",
      cache: "no-store",
    });

    const responseHeaders = new Headers();
    upstream.headers.forEach((value, key) => {
      const lower = key.toLowerCase();
      if (!HOP_BY_HOP_HEADERS.has(lower) && lower !== "set-cookie") {
        responseHeaders.set(key, value);
      }
    });

    if (typeof upstream.headers.getSetCookie === "function") {
      const setCookies = upstream.headers.getSetCookie();
      for (const cookie of setCookies) {
        responseHeaders.append("set-cookie", cookie);
      }
    } else {
      const setCookie = upstream.headers.get("set-cookie");
      if (setCookie) {
        responseHeaders.set("set-cookie", setCookie);
      }
    }

    const isNullBodyStatus = upstream.status === 204 || upstream.status === 205 || upstream.status === 304;
    const contentType = upstream.headers.get("content-type") || "";
    if (!isNullBodyStatus && contentType.includes("text/event-stream") && upstream.body) {
      responseHeaders.set("cache-control", "no-cache, no-transform");
      responseHeaders.set("x-accel-buffering", "no");
      return new Response(upstream.body, {
        status: upstream.status,
        statusText: upstream.statusText,
        headers: responseHeaders,
      });
    }

    const responseBody = isNullBodyStatus ? null : await upstream.arrayBuffer();

    return new Response(responseBody, {
      status: upstream.status,
      statusText: upstream.statusText,
      headers: responseHeaders,
    });
  } catch (err) {
    console.error("[api-proxy] Error forwarding request to backend:", err);
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
