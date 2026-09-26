import { Injectable } from '@angular/core';
import { AuthConfig, OAuthService } from 'angular-oauth2-oidc';

import { environment } from '../../environments/environment';

export const CALLBACK_PATH = '/auth/callback';

function authConfig(): AuthConfig {
  const origin = window.location.origin;
  return {
    issuer: environment.auth.issuer,
    clientId: environment.auth.clientId,
    responseType: 'code', // authorization code + PKCE
    scope: 'openid profile email',
    redirectUri: origin + CALLBACK_PATH,
    postLogoutRedirectUri: origin + '/',
    requireHttps: 'remoteOnly',
    useSilentRefresh: false, // refresh tokens instead of hidden iframes
    sessionChecksEnabled: false,
    clearHashAfterLogin: true,
  };
}

/**
 * Login through the identity provider (Keycloak locally). The app never sees
 * passwords: it redirects to the provider and gets tokens back.
 */
@Injectable({ providedIn: 'root' })
export class AuthService {
  /** false when the identity provider couldn't be reached at startup */
  available = false;

  constructor(private oauth: OAuthService) {}

  /** Runs once before the app starts (APP_INITIALIZER). */
  async init(): Promise<void> {
    this.oauth.configure(authConfig());
    try {
      await this.oauth.loadDiscoveryDocumentAndTryLogin();
      this.oauth.setupAutomaticSilentRefresh();
      this.available = true;
    } catch (e) {
      console.error('Identity provider unreachable', e);
      this.available = false;
    }
  }

  get isLoggedIn(): boolean {
    return this.oauth.hasValidAccessToken();
  }

  get email(): string | null {
    const claims = this.oauth.getIdentityClaims() as Record<string, string> | null;
    return claims?.['email'] ?? null;
  }

  get displayName(): string | null {
    const claims = this.oauth.getIdentityClaims() as Record<string, string> | null;
    return claims?.['name'] ?? claims?.['email'] ?? null;
  }

  /**
   * Where to go after the provider sends the user back. The library carries
   * it in the OAuth `state` (it encodes it itself — don't pre-encode).
   * Only in-app paths are accepted.
   */
  get returnUrl(): string {
    let url = this.oauth.state ?? '';
    try {
      url = decodeURIComponent(url);
    } catch {
      url = '';
    }
    return url.startsWith('/') && !url.startsWith('//') ? url : '/dashboards';
  }

  login(returnUrl = '/dashboards'): void {
    this.oauth.initCodeFlow(returnUrl);
  }

  register(returnUrl = '/dashboards'): void {
    // OIDC "prompt=create": the provider opens its sign-up form directly
    this.oauth.initCodeFlow(returnUrl, { prompt: 'create' });
  }

  logout(): void {
    this.oauth.logOut();
  }
}
