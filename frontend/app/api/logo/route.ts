import type { NextRequest } from "next/server";
import { get as httpsGet } from "node:https";

export const runtime = "nodejs";

const FETCH_TIMEOUT_MS = 4_000;
const MAX_LOGO_BYTES = 512 * 1_024;
const MAX_URL_LENGTH = 2_048;
const TRUSTED_LOGO_HOSTS = new Set([
  "cdn.alibaba.ir",
  "fs.snapptrip.com",
  "store.snapptrip.com",
  "static.mrbilit.com",
  "train.mrbilit.com",
  "cdn.safar724.com",
  "safar724.com",
  "cdn-a.cdnfl2.ir",
  "mrbilit.com",
  "payaneha.com",
  "www.payaneha.com",
  "s3.ir-thr-at1.arvanstorage.ir",
  "booking.ir",
  "www.booking.ir",
  "avaair.ir",
  "flykish.com",
  "www.flykish.com",
]);
const ALLOWED_CONTENT_TYPES = new Set([
  "image/avif",
  "image/gif",
  "image/x-icon",
  "image/vnd.microsoft.icon",
  "image/jpeg",
  "image/png",
  "image/svg+xml",
  "image/webp",
]);

class LogoProxyError extends Error {
  constructor(readonly status: number) {
    super("Logo proxy request rejected");
  }
}

function errorResponse(status: number) {
  return new Response(null, {
    status,
    headers: {
      "cache-control": "no-store",
      "x-content-type-options": "nosniff",
    },
  });
}

export function trustedLogoUrl(value: string | null): URL | null {
  if (!value || value.length > MAX_URL_LENGTH) return null;

  try {
    const url = new URL(value);
    if (
      url.protocol !== "https:"
      || url.username !== ""
      || url.password !== ""
      || (url.port !== "" && url.port !== "443")
      || !TRUSTED_LOGO_HOSTS.has(url.hostname.toLowerCase())
    ) {
      return null;
    }
    url.hash = "";
    return url;
  } catch {
    return null;
  }
}

type LogoFetcher = (url: URL) => Promise<{ body: ArrayBuffer; contentType: string }>;

function fetchLogo(url: URL): Promise<{ body: ArrayBuffer; contentType: string }> {
  return new Promise((resolve, reject) => {
    const upstreamRequest = httpsGet(url, {
      headers: {
        accept: "image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8",
      },
      timeout: FETCH_TIMEOUT_MS,
    }, (upstream) => {
      const status = upstream.statusCode ?? 502;
      if (status < 200 || status >= 300) {
        upstream.resume();
        reject(new LogoProxyError(status === 404 ? 404 : 502));
        return;
      }

      const contentType = upstream.headers["content-type"]?.split(";", 1)[0]?.trim().toLowerCase() ?? "";
      if (!ALLOWED_CONTENT_TYPES.has(contentType)) {
        upstream.resume();
        reject(new LogoProxyError(415));
        return;
      }

      const declaredLength = Number(upstream.headers["content-length"]);
      if (Number.isFinite(declaredLength) && declaredLength > MAX_LOGO_BYTES) {
        upstream.destroy();
        reject(new LogoProxyError(413));
        return;
      }

      const chunks: Uint8Array[] = [];
      let length = 0;
      upstream.on("data", (chunk: Buffer) => {
        length += chunk.byteLength;
        if (length > MAX_LOGO_BYTES) {
          upstream.destroy(new LogoProxyError(413));
          return;
        }
        chunks.push(chunk);
      });
      upstream.on("error", reject);
      upstream.on("end", () => {
        const body = new Uint8Array(length);
        let offset = 0;
        for (const chunk of chunks) {
          body.set(chunk, offset);
          offset += chunk.byteLength;
        }
        resolve({ body: body.buffer, contentType });
      });
    });

    upstreamRequest.on("timeout", () => upstreamRequest.destroy(new Error("Logo request timed out")));
    upstreamRequest.on("error", reject);
  });
}

export async function proxyLogoResponse(
  value: string | null,
  fetcher: LogoFetcher = fetchLogo,
) {
  const logoUrl = trustedLogoUrl(value);
  if (logoUrl === null) return errorResponse(400);

  try {
    // node:https does not follow redirects. Keeping that behavior is part of
    // the SSRF boundary: every request must target the verified host directly.
    const { body, contentType } = await fetcher(logoUrl);
    return new Response(body, {
      status: 200,
      headers: {
        "cache-control": "public, max-age=86400, stale-while-revalidate=604800",
        "content-length": String(body.byteLength),
        "content-security-policy": "default-src 'none'; style-src 'unsafe-inline'; sandbox",
        "content-type": contentType,
        "cross-origin-resource-policy": "same-origin",
        "x-content-type-options": "nosniff",
        "x-frame-options": "DENY",
      },
    });
  } catch (cause) {
    if (cause instanceof LogoProxyError) return errorResponse(cause.status);
    return errorResponse(504);
  }
}

export async function GET(request: NextRequest) {
  return proxyLogoResponse(request.nextUrl.searchParams.get("url"));
}
