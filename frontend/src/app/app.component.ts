import { CommonModule } from '@angular/common';
import { Component, HostListener, OnInit } from '@angular/core';
import { RouterLink, RouterLinkActive, RouterOutlet } from '@angular/router';

import { AuthService } from './auth/auth.service';
import { AccountService } from './services/account.service';

@Component({
  selector: 'app-root',
  standalone: true,
  imports: [CommonModule, RouterOutlet, RouterLink, RouterLinkActive],
  templateUrl: './app.component.html',
})
export class AppComponent implements OnInit {
  title = 'bayan.com.tn';
  currentYear = new Date().getFullYear();
  menuOpen = false;

  constructor(public auth: AuthService, public account: AccountService) {}

  ngOnInit(): void {
    if (this.auth.isLoggedIn) {
      this.account.refresh().subscribe({ error: () => undefined });
    }
  }

  get initial(): string {
    return (this.auth.displayName ?? '?').trim().charAt(0).toUpperCase();
  }

  @HostListener('document:keydown.escape')
  closeMenu(): void {
    this.menuOpen = false;
  }
}
