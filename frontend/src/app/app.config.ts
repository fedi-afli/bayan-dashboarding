import { APP_INITIALIZER, ApplicationConfig } from '@angular/core';
import { provideRouter } from '@angular/router';
import { provideHttpClient, withInterceptors, withInterceptorsFromDi } from '@angular/common/http';
import { provideOAuthClient } from 'angular-oauth2-oidc';

import { routes } from './app.routes';
import { environment } from '../environments/environment';
import { AuthService } from './auth/auth.service';
import { unauthorizedInterceptor } from './auth/unauthorized.interceptor';

export const appConfig: ApplicationConfig = {
  providers: [
    // DI interceptors = the OIDC library's "attach the access token to API calls"
    provideHttpClient(withInterceptorsFromDi(), withInterceptors([unauthorizedInterceptor])),
    provideOAuthClient({ resourceServer: { allowedUrls: [environment.apiUrl], sendAccessToken: true } }),
    {
      provide: APP_INITIALIZER,
      multi: true,
      deps: [AuthService],
      useFactory: (auth: AuthService) => () => auth.init(),
    },
    provideRouter(routes),
  ],
};
