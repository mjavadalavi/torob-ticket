import { expect, test } from "@playwright/test";
import { proxyLogoResponse, trustedLogoUrl } from "../../app/api/logo/route";
import { proxiedLogoUrl } from "../../components/operator-logo";

test("logo proxy rejects URLs outside the exact provider asset allowlist", async ({ request }) => {
  const rejectedUrls = [
    "http://cdn.alibaba.ir/logo.png",
    "https://cdn.alibaba.ir.evil.test/logo.png",
    "https://fs.snapptrip.com.evil.test/logo.png",
    "https://store.snapptrip.com.evil.test/logo.png",
    "https://user:password@cdn.alibaba.ir/logo.png",
    "https://127.0.0.1/logo.png",
    "https://localhost/logo.png",
  ];

  for (const url of rejectedUrls) {
    const response = await request.get(`/api/logo?url=${encodeURIComponent(url)}`);
    expect(response.status(), url).toBe(400);
    expect(response.headers()["cache-control"]).toBe("no-store");
    expect(response.headers()["x-content-type-options"]).toBe("nosniff");
  }
});

test("train operator logos pass both client and server allowlists", () => {
  const logoUrl = "https://fs.snapptrip.com/images/train/uploads/raja.png";
  expect(trustedLogoUrl(logoUrl)?.toString()).toBe(logoUrl);
  expect(proxiedLogoUrl(logoUrl)).toBe(
    `/api/logo?url=${encodeURIComponent(logoUrl)}`,
  );

  const mrbilitLogoUrl = "https://train.mrbilit.com/Content/Logos/svg/raja.svg";
  expect(trustedLogoUrl(mrbilitLogoUrl)?.toString()).toBe(mrbilitLogoUrl);
  expect(proxiedLogoUrl(mrbilitLogoUrl)).toBe(
    `/api/logo?url=${encodeURIComponent(mrbilitLogoUrl)}`,
  );
});

test("seller logos pass the allowlist for all active OTA sources", () => {
  for (const logoUrl of [
    "https://safar724.com/content/images/logo.png",
    "https://cdn-a.cdnfl2.ir/upload/flytoday/public/white-labels/flytodayircom/images/logo.svg",
    "https://mrbilit.com/favicon.ico",
    "https://www.booking.ir/assets/images/logo.png",
  ]) {
    expect(trustedLogoUrl(logoUrl)?.toString()).toBe(logoUrl);
    expect(proxiedLogoUrl(logoUrl)).toBe(
      `/api/logo?url=${encodeURIComponent(logoUrl)}`,
    );
  }
});

test("logo proxy requires a URL", async ({ request }) => {
  const response = await request.get("/api/logo");
  expect(response.status()).toBe(400);
});

test("logo proxy serves a verified provider image with hardened headers", async () => {
  const logoUrl = "https://cdn.alibaba.ir/static/img/airlines/Domestic/W5.png";
  const response = await proxyLogoResponse(logoUrl, async () => ({
    body: Uint8Array.from([137, 80, 78, 71]).buffer,
    contentType: "image/png",
  }));

  expect(response.status).toBe(200);
  expect(response.headers.get("content-type")).toBe("image/png");
  expect(response.headers.get("cross-origin-resource-policy")).toBe("same-origin");
  expect(response.headers.get("x-content-type-options")).toBe("nosniff");
  expect(response.headers.get("content-security-policy")).toContain("sandbox");
  const body = await response.arrayBuffer();
  expect(body.byteLength).toBeGreaterThan(0);
  expect(body.byteLength).toBeLessThanOrEqual(512 * 1_024);
});
