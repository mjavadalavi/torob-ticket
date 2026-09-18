import "server-only";

const backendApiUrl = (
  process.env.API_URL
  ?? "http://127.0.0.1:8000/api/v1"
).replace(/\/$/, "");

const forwardedResponseHeaders = ["location", "retry-after"] as const;

function sameOriginLocation(value: string) {
  try {
    const upstreamBase = new URL(backendApiUrl);
    const upstreamLocation = new URL(value);
    const apiPath = upstreamBase.pathname.replace(/\/$/, "");
    const searchJobPath = upstreamLocation.pathname.slice(apiPath.length);
    if (
      upstreamLocation.origin !== upstreamBase.origin
      || !upstreamLocation.pathname.startsWith(`${apiPath}/`)
      || !/^\/search-jobs\/src_[a-f0-9]{32}$/.test(searchJobPath)
    ) {
      return null;
    }

    return `/api/travel${searchJobPath}${upstreamLocation.search}`;
  } catch {
    return null;
  }
}

type ProxyRequest = {
  request: Request;
  path: readonly string[];
  searchParams?: URLSearchParams;
  timeoutMs?: number;
  failureMessage: string;
};

export async function proxyApiRequest({
  request,
  path,
  searchParams,
  timeoutMs = 15_000,
  failureMessage,
}: ProxyRequest) {
  const encodedPath = path.map((segment) => encodeURIComponent(segment)).join("/");
  const upstreamUrl = new URL(`${backendApiUrl}/${encodedPath}`);
  upstreamUrl.search = searchParams?.toString() ?? new URL(request.url).searchParams.toString();

  try {
    const upstreamResponse = await fetch(upstreamUrl, {
      method: request.method,
      headers: {
        accept: "application/json",
        ...(request.method === "POST" ? { "content-type": "application/json" } : {}),
      },
      body: request.method === "POST" ? await request.text() : undefined,
      cache: "no-store",
      signal: AbortSignal.timeout(timeoutMs),
    });
    const body = await upstreamResponse.arrayBuffer();
    const responseHeaders = new Headers({
      "content-type": upstreamResponse.headers.get("content-type") ?? "application/json",
      "cache-control": "no-store",
    });
    for (const headerName of forwardedResponseHeaders) {
      const value = upstreamResponse.headers.get(headerName);
      if (value === null) continue;
      if (headerName === "location") {
        const location = sameOriginLocation(value);
        if (location !== null) responseHeaders.set(headerName, location);
      } else {
        responseHeaders.set(headerName, value);
      }
    }
    return new Response(body, {
      status: upstreamResponse.status,
      headers: responseHeaders,
    });
  } catch {
    return Response.json(
      { error: { message: failureMessage } },
      { status: 502, headers: { "cache-control": "no-store" } },
    );
  }
}
