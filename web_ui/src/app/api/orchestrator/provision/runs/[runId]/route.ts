import { NextRequest, NextResponse } from "next/server";
import { getOrchestratorBaseUrl, getUpstreamAuthHeaders, requireAdminSession } from "@/app/api/_utils/upstream";

export async function GET(req: NextRequest, ctx: { params: Promise<{ runId: string }> }) {
  try {
    await requireAdminSession(req);
    const { runId } = await ctx.params;
    const baseUrl = getOrchestratorBaseUrl();
    const upstreamUrl = new URL(`/api/v1/admin/provision/runs/${runId}`, baseUrl);
    const authHeaders = getUpstreamAuthHeaders(req);

    const res = await fetch(upstreamUrl, {
      method: "GET",
      headers: Object.keys(authHeaders).length ? authHeaders : undefined,
      cache: "no-store",
    });

    const contentType = res.headers.get("content-type") || "application/json";
    const body = await res.text();
    return new NextResponse(body, { status: res.status, headers: { "content-type": contentType } });
  } catch (err: any) {
    if (String(err?.message || "").includes("missing_auth")) {
      return NextResponse.json({ error: "Admin session required" }, { status: 401 });
    }
    return NextResponse.json(
      { error: "Failed to fetch provisioning run", details: err?.message || String(err) },
      { status: 502 },
    );
  }
}


