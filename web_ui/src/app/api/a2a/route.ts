import { NextRequest, NextResponse } from "next/server";
import { getOrchestratorBaseUrl } from "@/app/api/_utils/upstream";

export const runtime = "nodejs";

/**
 * A2A (Agent-to-Agent) Protocol Implementation
 * 
 * Based on Google's A2A specification for inter-agent communication.
 * https://github.com/google/A2A
 * 
 * This endpoint allows other AI agents/systems to:
 * - Invoke IncidentFox agents programmatically
 * - Get structured responses in A2A format
 * - Chain with other A2A-compatible agents
 * 
 * Supported A2A methods:
 * - tasks/send: Send a task to our agent
 * - tasks/get: Get status of a running task
 * - agent/authenticatedExtendedCard: Get agent capabilities
 */

// A2A Agent Card - describes our capabilities
const AGENT_CARD = {
  name: "IncidentFox",
  description: "AI-powered incident investigation and infrastructure automation agent",
  url: process.env.A2A_PUBLIC_URL || "https://incidentfox.example.com/api/a2a",
  provider: {
    organization: "IncidentFox",
    url: "https://incidentfox.io",
  },
  version: "1.0.0",
  capabilities: {
    streaming: false,
    pushNotifications: false,
    stateTransitionHistory: true,
  },
  authentication: {
    schemes: ["bearer"],
  },
  defaultInputModes: ["text"],
  defaultOutputModes: ["text", "json"],
  skills: [
    {
      id: "incident-investigation",
      name: "Incident Investigation",
      description: "Investigate production incidents, find root causes, and suggest fixes",
      tags: ["incident", "debugging", "root-cause-analysis"],
      examples: [
        "Investigate why pod nginx-abc123 is crashing",
        "What's causing high latency in the payments service?",
        "Analyze the recent spike in error rates",
      ],
    },
    {
      id: "kubernetes-troubleshooting",
      name: "Kubernetes Troubleshooting",
      description: "Debug Kubernetes issues including pods, deployments, and services",
      tags: ["kubernetes", "k8s", "containers", "debugging"],
      examples: [
        "List all crashing pods in the production namespace",
        "Why is the deployment not rolling out?",
        "Check resource usage for pods with high memory",
      ],
    },
    {
      id: "aws-debugging",
      name: "AWS Resource Debugging",
      description: "Investigate AWS infrastructure issues",
      tags: ["aws", "cloud", "infrastructure"],
      examples: [
        "Check the status of EC2 instance i-abc123",
        "Why is the Lambda function timing out?",
        "Analyze CloudWatch logs for errors",
      ],
    },
    {
      id: "metrics-analysis",
      name: "Metrics & Anomaly Detection",
      description: "Analyze metrics, detect anomalies, and forecast trends",
      tags: ["metrics", "monitoring", "anomaly-detection", "forecasting"],
      examples: [
        "Detect anomalies in the latency metrics",
        "Forecast when disk space will run out",
        "Correlate CPU usage with error rates",
      ],
    },
    {
      id: "code-analysis",
      name: "Code Analysis",
      description: "Analyze code, review changes, and identify bugs",
      tags: ["code", "review", "debugging"],
      examples: [
        "Review the latest PR for potential issues",
        "Find the source of the null pointer exception",
        "Analyze the authentication flow for security issues",
      ],
    },
  ],
};

// A2A Task state
interface A2ATask {
  id: string;
  status: {
    state: "submitted" | "working" | "input-required" | "completed" | "failed" | "canceled";
    message?: { role: string; parts: Array<{ text?: string; data?: unknown }> };
    timestamp: string;
  };
  artifacts?: Array<{
    name: string;
    parts: Array<{ text?: string; data?: unknown }>;
  }>;
  history?: Array<{
    state: string;
    timestamp: string;
    message?: unknown;
  }>;
}

// In-memory task store (in production, use Redis/DB)
const taskStore = new Map<string, A2ATask>();

export async function POST(req: NextRequest) {
  const authHeader = req.headers.get("authorization");
  const internalToken = (process.env.ORCHESTRATOR_INTERNAL_TOKEN || "").trim();
  const a2aSecret = (process.env.A2A_SECRET || "").trim();

  // Verify authentication
  if (a2aSecret) {
    if (!authHeader || !authHeader.startsWith("Bearer ")) {
      return NextResponse.json({ error: "unauthorized" }, { status: 401 });
    }
    const token = authHeader.substring(7);
    if (token !== a2aSecret) {
      return NextResponse.json({ error: "invalid_token" }, { status: 401 });
    }
  }

  let body: any;
  try {
    body = await req.json();
  } catch {
    return NextResponse.json({ error: "invalid_json" }, { status: 400 });
  }

  const method = body.method || "";
  const params = body.params || {};
  const requestId = body.id || `req-${Date.now()}`;

  console.log(`[A2A] Received method: ${method}`);

  // Route A2A methods
  switch (method) {
    case "agent/authenticatedExtendedCard":
      return NextResponse.json({
        jsonrpc: "2.0",
        id: requestId,
        result: AGENT_CARD,
      });

    case "tasks/send":
      return handleTaskSend(params, requestId, internalToken);

    case "tasks/get":
      return handleTaskGet(params, requestId);

    case "tasks/cancel":
      return handleTaskCancel(params, requestId);

    default:
      return NextResponse.json({
        jsonrpc: "2.0",
        id: requestId,
        error: {
          code: -32601,
          message: `Method not found: ${method}`,
        },
      }, { status: 404 });
  }
}

async function handleTaskSend(
  params: { id?: string; message?: { role: string; parts: Array<{ text?: string }> }; sessionId?: string },
  requestId: string,
  internalToken: string
) {
  const taskId = params.id || `task-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;
  const message = params.message;

  if (!message?.parts?.length) {
    return NextResponse.json({
      jsonrpc: "2.0",
      id: requestId,
      error: { code: -32602, message: "Invalid params: message.parts required" },
    }, { status: 400 });
  }

  // Extract text from message parts
  const userQuery = message.parts
    .map(p => p.text || "")
    .filter(Boolean)
    .join("\n");

  if (!userQuery) {
    return NextResponse.json({
      jsonrpc: "2.0",
      id: requestId,
      error: { code: -32602, message: "Invalid params: no text in message" },
    }, { status: 400 });
  }

  // Create task in submitted state
  const task: A2ATask = {
    id: taskId,
    status: {
      state: "submitted",
      message: message,
      timestamp: new Date().toISOString(),
    },
    history: [{
      state: "submitted",
      timestamp: new Date().toISOString(),
    }],
  };
  taskStore.set(taskId, task);

  // Trigger investigation asynchronously
  const orgId = process.env.DEFAULT_ORG_ID || "org-default";
  const teamNodeId = process.env.DEFAULT_TEAM_NODE_ID || "team-default";
  
  // Update to working state
  task.status.state = "working";
  task.status.timestamp = new Date().toISOString();
  task.history!.push({ state: "working", timestamp: new Date().toISOString() });

  // Fire async task
  (async () => {
    try {
      const orchestratorUrl = getOrchestratorBaseUrl();
      
      const response = await fetch(`${orchestratorUrl}/api/v1/admin/agents/run`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "Authorization": `Bearer ${internalToken}`,
        },
        body: JSON.stringify({
          org_id: orgId,
          team_node_id: teamNodeId,
          agent_name: "planner",
          message: userQuery,
          context: {
            source: "a2a",
            session_id: params.sessionId,
          },
        }),
      });

      const result = await response.json();

      // Update task with result
      const storedTask = taskStore.get(taskId);
      if (storedTask) {
        if (response.ok && result.success !== false) {
          storedTask.status.state = "completed";
          storedTask.status.message = {
            role: "agent",
            parts: [{
              text: typeof result.output === "string" 
                ? result.output 
                : JSON.stringify(result.output, null, 2),
            }],
          };
          storedTask.artifacts = [{
            name: "investigation_result",
            parts: [{
              data: result.output,
            }],
          }];
        } else {
          storedTask.status.state = "failed";
          storedTask.status.message = {
            role: "agent",
            parts: [{ text: result.error || "Investigation failed" }],
          };
        }
        storedTask.status.timestamp = new Date().toISOString();
        storedTask.history!.push({
          state: storedTask.status.state,
          timestamp: new Date().toISOString(),
        });
      }
    } catch (err: any) {
      const storedTask = taskStore.get(taskId);
      if (storedTask) {
        storedTask.status.state = "failed";
        storedTask.status.message = {
          role: "agent",
          parts: [{ text: `Error: ${err?.message || String(err)}` }],
        };
        storedTask.status.timestamp = new Date().toISOString();
        storedTask.history!.push({
          state: "failed",
          timestamp: new Date().toISOString(),
        });
      }
    }
  })();

  // Return immediately with working state
  return NextResponse.json({
    jsonrpc: "2.0",
    id: requestId,
    result: task,
  });
}

async function handleTaskGet(params: { id?: string }, requestId: string) {
  const taskId = params.id;
  
  if (!taskId) {
    return NextResponse.json({
      jsonrpc: "2.0",
      id: requestId,
      error: { code: -32602, message: "Invalid params: id required" },
    }, { status: 400 });
  }

  const task = taskStore.get(taskId);
  
  if (!task) {
    return NextResponse.json({
      jsonrpc: "2.0",
      id: requestId,
      error: { code: -32001, message: "Task not found" },
    }, { status: 404 });
  }

  return NextResponse.json({
    jsonrpc: "2.0",
    id: requestId,
    result: task,
  });
}

async function handleTaskCancel(params: { id?: string }, requestId: string) {
  const taskId = params.id;
  
  if (!taskId) {
    return NextResponse.json({
      jsonrpc: "2.0",
      id: requestId,
      error: { code: -32602, message: "Invalid params: id required" },
    }, { status: 400 });
  }

  const task = taskStore.get(taskId);
  
  if (!task) {
    return NextResponse.json({
      jsonrpc: "2.0",
      id: requestId,
      error: { code: -32001, message: "Task not found" },
    }, { status: 404 });
  }

  // Only cancel if still in progress
  if (task.status.state === "working" || task.status.state === "submitted") {
    task.status.state = "canceled";
    task.status.timestamp = new Date().toISOString();
    task.history!.push({ state: "canceled", timestamp: new Date().toISOString() });
  }

  return NextResponse.json({
    jsonrpc: "2.0",
    id: requestId,
    result: task,
  });
}

// GET returns the public agent card
export async function GET() {
  return NextResponse.json({
    ...AGENT_CARD,
    endpoints: {
      base: "/api/a2a",
      methods: ["tasks/send", "tasks/get", "tasks/cancel", "agent/authenticatedExtendedCard"],
    },
  });
}

