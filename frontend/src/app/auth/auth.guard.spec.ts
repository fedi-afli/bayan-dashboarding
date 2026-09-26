import { TestBed } from '@angular/core/testing';
import { ActivatedRouteSnapshot, RouterStateSnapshot } from '@angular/router';

import { authGuard } from './auth.guard';
import { AuthService } from './auth.service';

describe('authGuard', () => {
  function run(loggedIn: boolean) {
    const auth = { isLoggedIn: loggedIn, login: jasmine.createSpy('login') };
    TestBed.configureTestingModule({ providers: [{ provide: AuthService, useValue: auth }] });
    const result = TestBed.runInInjectionContext(() =>
      authGuard({} as ActivatedRouteSnapshot, { url: '/credits' } as RouterStateSnapshot)
    );
    return { result, auth };
  }

  it('lets logged-in users through', () => {
    expect(run(true).result).toBeTrue();
  });

  it('sends everyone else to login, remembering where they were going', () => {
    const { result, auth } = run(false);
    expect(result).toBeFalse();
    expect(auth.login).toHaveBeenCalledWith('/credits');
  });
});
