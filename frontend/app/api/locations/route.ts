import { NextRequest } from "next/server";
import { proxyApiRequest } from "@/lib/server-api-proxy";

const travelModes = new Set(["flight", "train", "bus"]);

export async function GET(request: NextRequest) {
  const mode = request.nextUrl.searchParams.get("mode") ?? "";
  const query = request.nextUrl.searchParams.get("q")?.trim().slice(0, 64) ?? "";
  const requestedLimit = Number(request.nextUrl.searchParams.get("limit") ?? "10");
  const limit = Number.isFinite(requestedLimit)
    ? Math.min(20, Math.max(1, Math.trunc(requestedLimit)))
    : 10;

  if (!travelModes.has(mode)) {
    return Response.json(
      { error: { message: "نوع سفر معتبر نیست." } },
      { status: 400 },
    );
  }

  const params = new URLSearchParams({ mode, q: query, limit: String(limit) });

  return proxyApiRequest({
    request,
    path: ["locations"],
    searchParams: params,
    timeoutMs: 8_000,
    failureMessage: "دریافت فهرست شهرها ممکن نشد.",
  });
}
