import { proxyApiRequest } from "@/lib/server-api-proxy";

const offerPathPattern = /^offers\/[^/]+(?:\/(?:details|refund-rules|seat-map|redirect))?$/;
const searchJobPathPattern = /^search-jobs\/src_[a-f0-9]{32}$/;

function isAllowed(method: string, path: string) {
  if (method === "POST") return path === "search" || path === "search-jobs" || path === "nearby-dates";
  return method === "GET" && (offerPathPattern.test(path) || searchJobPathPattern.test(path));
}

async function forward(
  request: Request,
  { params }: { params: Promise<{ path: string[] }> },
) {
  const { path: segments } = await params;
  const path = segments.join("/");
  if (!isAllowed(request.method, path)) {
    return Response.json(
      { error: { message: "مسیر درخواستی معتبر نیست." } },
      { status: 404 },
    );
  }

  return proxyApiRequest({
    request,
    path: segments,
    timeoutMs: path === "nearby-dates" ? 30_000 : undefined,
    failureMessage: "ارتباط با سرویس فروش برقرار نشد.",
  });
}

export const GET = forward;
export const POST = forward;
