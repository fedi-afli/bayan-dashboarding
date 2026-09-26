import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { BehaviorSubject, Observable, tap } from 'rxjs';

import { environment } from '../../environments/environment';
import { CreditsOverview, Me } from '../models/models';

/** The logged-in user's account: identity + credit balance, shared across the app. */
@Injectable({ providedIn: 'root' })
export class AccountService {
  private readonly baseUrl = environment.apiUrl;
  readonly me$ = new BehaviorSubject<Me | null>(null);

  constructor(private http: HttpClient) {}

  refresh(): Observable<Me> {
    return this.http.get<Me>(`${this.baseUrl}/me`).pipe(tap((me) => this.me$.next(me)));
  }

  /** Update the shown balance without a round trip (e.g. from a confirm response). */
  setBalance(balance: number): void {
    const me = this.me$.value;
    if (me) this.me$.next({ ...me, account: { ...me.account, credit_balance: balance } });
  }

  credits(): Observable<CreditsOverview> {
    return this.http
      .get<CreditsOverview>(`${this.baseUrl}/credits`)
      .pipe(tap((c) => this.setBalance(c.balance)));
  }

  checkout(pack: string): Observable<{ payment_id: string; checkout_url: string }> {
    return this.http.post<{ payment_id: string; checkout_url: string }>(`${this.baseUrl}/credits/checkout`, { pack });
  }
}
