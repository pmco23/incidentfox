import { NextRequest, NextResponse } from 'next/server';

const CONFIG_SERVICE_URL = process.env.CONFIG_SERVICE_URL || 'http://localhost:8080';

export async function GET(request: NextRequest) {
  try {
    // Pass through query parameters (category, featured)
    const searchParams = request.nextUrl.searchParams;
    const queryString = searchParams.toString();
    const url = `${CONFIG_SERVICE_URL}/api/v1/integrations/schemas${queryString ? `?${queryString}` : ''}`;

    const res = await fetch(url, {
      headers: {
        'Content-Type': 'application/json',
      },
    });

    if (!res.ok) {
      const text = await res.text();
      console.error('Config service error:', res.status, text);
      return NextResponse.json({ error: text }, { status: res.status });
    }

    const data = await res.json();
    return NextResponse.json(data, { status: res.status });
  } catch (error) {
    console.error('Failed to fetch integration schemas:', error);
    return NextResponse.json({ error: 'Internal server error' }, { status: 500 });
  }
}
