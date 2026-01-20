import { NextRequest, NextResponse } from 'next/server';
import { cookies } from 'next/headers';

const CONFIG_SERVICE_URL = process.env.CONFIG_SERVICE_URL || 'http://localhost:8080';

/**
 * OAuth callback handler.
 * Exchanges the auth code for tokens, validates the user, and creates a session.
 */
export async function GET(request: NextRequest) {
  const searchParams = request.nextUrl.searchParams;
  const code = searchParams.get('code');
  const state = searchParams.get('state');
  const error = searchParams.get('error');

  if (error) {
    return NextResponse.redirect(new URL(`/?error=${error}`, request.url));
  }

  if (!code) {
    return NextResponse.redirect(new URL('/?error=no_code', request.url));
  }

  // Parse state
  let stateData = { org_id: 'org1', returnTo: '/' };
  if (state) {
    try {
      stateData = JSON.parse(atob(state));
    } catch {
      // ignore
    }
  }

  try {
    // Get org SSO config from config service
    const ssoConfigRes = await fetch(
      `${CONFIG_SERVICE_URL}/api/v1/admin/orgs/${stateData.org_id}/sso-config/public`
    );
    
    if (!ssoConfigRes.ok) {
      return NextResponse.redirect(new URL('/?error=sso_not_configured', request.url));
    }
    
    const ssoConfig = await ssoConfigRes.json();
    
    if (!ssoConfig.enabled) {
      return NextResponse.redirect(new URL('/?error=sso_disabled', request.url));
    }

    // Build token endpoint URL
    let tokenUrl: string;
    const redirectUri = `${request.nextUrl.origin}/api/auth/callback`;

    if (ssoConfig.provider_type === 'google') {
      tokenUrl = 'https://oauth2.googleapis.com/token';
    } else if (ssoConfig.provider_type === 'azure') {
      const tenant = ssoConfig.tenant_id || 'common';
      tokenUrl = `https://login.microsoftonline.com/${tenant}/oauth2/v2.0/token`;
    } else {
      tokenUrl = `${ssoConfig.issuer?.replace(/\/$/, '')}/token`;
    }

    // Exchange code for token
    // Note: We need the client_secret which is only available server-side
    // For now, we'll call a config service endpoint to do this exchange
    const exchangeRes = await fetch(
      `${CONFIG_SERVICE_URL}/api/v1/auth/sso/exchange`,
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          org_id: stateData.org_id,
          code,
          redirect_uri: redirectUri,
        }),
      }
    );

    if (!exchangeRes.ok) {
      const err = await exchangeRes.json().catch(() => ({}));
      console.error('Token exchange failed:', err);
      return NextResponse.redirect(new URL(`/?error=exchange_failed&detail=${encodeURIComponent(err.detail || '')}`, request.url));
    }

    const exchangeData = await exchangeRes.json();

    // Set session cookie with the session token
    const cookieStore = await cookies();
    cookieStore.set('incidentfox_session_token', exchangeData.session_token, {
      httpOnly: true,
      secure: process.env.NODE_ENV === 'production',
      sameSite: 'lax',
      path: '/',
      maxAge: 60 * 60 * 24 * 7, // 7 days
    });

    // Redirect to destination
    return NextResponse.redirect(new URL(stateData.returnTo || '/', request.url));

  } catch (err) {
    console.error('SSO callback error:', err);
    return NextResponse.redirect(new URL('/?error=callback_error', request.url));
  }
}
