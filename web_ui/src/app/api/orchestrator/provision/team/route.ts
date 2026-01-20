import { NextRequest, NextResponse } from "next/server";
import { getOrchestratorBaseUrl, getUpstreamAuthHeaders, requireAdminSession } from "@/app/api/_utils/upstream";

export async function POST(req: NextRequest) {
  try {
    await requireAdminSession(req);

    const baseUrl = getOrchestratorBaseUrl();
    const upstreamUrl = new URL("/api/v1/admin/provision/team", baseUrl);
    const authHeaders = getUpstreamAuthHeaders(req);

    const body = await req.text();

    const res = await fetch(upstreamUrl, {
      method: "POST",
      headers: {
        "content-type": req.headers.get("content-type") || "application/json",
        ...authHeaders,
      },
      body,
      cache: "no-store",
    });

    const contentType = res.headers.get("content-type") || "application/json";
    const respBody = await res.text();
    return new NextResponse(respBody, { status: res.status, headers: { "content-type": contentType } });
  } catch (err: any) {
    if (String(err?.message || "").includes("missing_auth")) {
      return NextResponse.json({ error: "Admin session required" }, { status: 401 });
    }
    return NextResponse.json(
      { error: "Failed to provision team", details: err?.message || String(err) },
      { status: 502 },
    );
  }
}


