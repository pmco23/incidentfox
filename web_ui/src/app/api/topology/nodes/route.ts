import { NextResponse } from "next/server";

export const runtime = "nodejs";

function getConfigServiceBaseUrl() {
  const baseUrl = process.env.CONFIG_SERVICE_URL;
  if (!baseUrl) {
    throw new Error("CONFIG_SERVICE_URL is not set");
  }
  return baseUrl;
}

export async function GET() {
  try {
    const baseUrl = getConfigServiceBaseUrl();
    const orgId = process.env.ORG_ID || "org1";

    const upstreamUrl = new URL(`/api/v1/admin/orgs/${orgId}/nodes`, baseUrl);
    const res = await fetch(upstreamUrl, {
      // Avoid caching stale config/topology
      cache: "no-store",
    });

    const contentType = res.headers.get("content-type") || "application/json";
    const body = await res.text();

    return new NextResponse(body, {
      status: res.status,
      headers: {
        "content-type": contentType,
      },
    });
  } catch (err: any) {
    return NextResponse.json(
      {
        error: "Failed to fetch topology nodes",
        details: err?.message || String(err),
      },
      { status: 502 },
    );
  }
}


