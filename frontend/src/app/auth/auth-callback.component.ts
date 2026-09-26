import { Component, OnInit } from '@angular/core';
import { Router } from '@angular/router';

import { AuthService } from './auth.service';

/** The identity provider redirects here; tokens were already exchanged during app init. */
@Component({
  selector: 'app-auth-callback',
  standalone: true,
  template: `<p class="py-24 text-center text-sm text-slate-500">Signing you in…</p>`,
})
export class AuthCallbackComponent implements OnInit {
  constructor(private auth: AuthService, private router: Router) {}

  ngOnInit(): void {
    this.router.navigateByUrl(this.auth.isLoggedIn ? this.auth.returnUrl : '/', { replaceUrl: true });
  }
}
