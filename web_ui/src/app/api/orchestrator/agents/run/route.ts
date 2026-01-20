import { NextRequest, NextResponse } from "next/server";
import { getOrchestratorBaseUrl, getUpstreamAuthHeaders, requireAdminSession } from "@/app/api/_utils/upstream";

export const runtime = "nodejs";

export async function POST(req: NextRequest) {
  try {
    await requireAdminSession(req);
  } catch (e: any) {
    const status = e?.status || (String(e?.message || "").includes("missing_auth") ? 401 : 403);
    return NextResponse.json({ error: "Admin session required" }, { status });
  }

  const body = await req.json();

  const upstream = `${getOrchestratorBaseUrl()}/api/v1/admin/agents/run`;
  const res = await fetch(upstream, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...getUpstreamAuthHeaders(req),
    },
    body: JSON.stringify(body),
  });

  const text = await res.text();
  return new NextResponse(text, {
    status: res.status,
    headers: { "Content-Type": res.headers.get("content-type") ?? "application/json" },
  });
}


