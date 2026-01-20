import { NextRequest, NextResponse } from "next/server";
import { getOrchestratorBaseUrl, getUpstreamAuthHeaders } from "@/app/api/_utils/upstream";

/**
 * POST /api/orchestrator/sync-cronjobs
 *
 * Syncs CronJobs (AI Pipeline, Dependency Discovery) based on team config.
 * Proxies to orchestrator's /api/v1/teams/me/sync-cronjobs endpoint.
 *
 * Uses team token authentication - no request body needed.
 * The orchestrator determines org_id/team_node_id from the team token.
 */
export async function POST(req: NextRequest) {
  try {
    const baseUrl = getOrchestratorBaseUrl();
    // Use team endpoint (not admin) so team users can self-service
    const upstreamUrl = new URL("/api/v1/teams/me/sync-cronjobs", baseUrl);
    const authHeaders = getUpstreamAuthHeaders(req);

    const res = await fetch(upstreamUrl, {
      method: "POST",
      headers: {
        ...authHeaders,
        "content-type": "application/json",
      },
      // No body needed - team endpoint uses token to determine team
      body: "{}",
    });

    const contentType = res.headers.get("content-type") || "application/json";
    const resBody = await res.text();
    return new NextResponse(resBody, {
      status: res.status,
      headers: { "content-type": contentType },
    });
  } catch (err: any) {
    return NextResponse.json(
      { ok: false, error: "Failed to sync cronjobs", details: err?.message || String(err) },
      { status: 502 }
    );
  }
}
