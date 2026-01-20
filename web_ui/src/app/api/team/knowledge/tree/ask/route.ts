import { NextRequest, NextResponse } from 'next/server';

const RAPTOR_API_URL = process.env.RAPTOR_API_URL || 'http://localhost:8000';

/**
 * POST /api/team/knowledge/tree/ask
 * Ask a question and get an answer from the knowledge base with citations
 */
export async function POST(request: NextRequest) {
  const token = request.cookies.get('incidentfox_session_token')?.value;
  
  if (!token) {
    return NextResponse.json({ error: 'Not authenticated' }, { status: 401 });
  }

  try {
    const body = await request.json();
    const { question, tree = 'mega_ultra_v2', top_k = 5 } = body;
    
    if (!question) {
      return NextResponse.json({ error: 'Question is required' }, { status: 400 });
    }

    const res = await fetch(`${RAPTOR_API_URL}/api/v1/answer`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Accept': 'application/json',
      },
      body: JSON.stringify({ question, tree, top_k }),
    });
    
    if (!res.ok) {
      const err = await res.text();
      return NextResponse.json({ error: err }, { status: res.status });
    }
    
    const data = await res.json();
    return NextResponse.json(data);
  } catch (e: any) {
    console.error('RAPTOR API error:', e);
    return NextResponse.json({ error: e?.message || 'Failed to answer question' }, { status: 500 });
  }
}

