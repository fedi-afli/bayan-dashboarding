import { CommonModule } from '@angular/common';
import { Component, OnInit } from '@angular/core';
import { HttpErrorResponse } from '@angular/common/http';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';

import { CreditPack, CreditsOverview, LedgerEntry } from '../../models/models';
import { AccountService } from '../../services/account.service';
import { apiErrorMessage } from '../../services/pipeline.service';

type Banner = { tone: 'success' | 'info' | 'error'; text: string } | null;

const BANNERS: Record<string, Banner> = {
  credited: { tone: 'success', text: 'Payment received — your credits have been added.' },
  already_credited: { tone: 'success', text: 'Payment received — your credits have been added.' },
  pending: { tone: 'info', text: 'The payment wasn’t completed. Nothing was charged — you can try again.' },
  mismatch: { tone: 'error', text: 'We couldn’t match this payment to your order. Contact us with the reference below.' },
  unknown: { tone: 'error', text: 'We couldn’t find this payment. Contact us if you were charged.' },
  error: { tone: 'error', text: 'We couldn’t confirm the payment with the payment service. It will be credited as soon as it is confirmed.' },
};

@Component({
  selector: 'app-credits',
  standalone: true,
  imports: [CommonModule, RouterLink],
  templateUrl: './credits.component.html',
})
export class CreditsComponent implements OnInit {
  data: CreditsOverview | null = null;
  error: string | null = null;
  buying: string | null = null;
  banner: Banner = null;
  paymentRef: string | null = null;

  constructor(private account: AccountService, private route: ActivatedRoute, private router: Router) {}

  ngOnInit(): void {
    const q = this.route.snapshot.queryParamMap;
    const status = q.get('status');
    if (status) {
      this.banner = BANNERS[status] ?? null;
      this.paymentRef = q.get('payment');
      // keep the URL clean so a refresh doesn't re-show the banner
      this.router.navigate([], { queryParams: {}, replaceUrl: true });
    }
    this.load();
  }

  load(): void {
    this.account.credits().subscribe({
      next: (d) => (this.data = d),
      error: (err: HttpErrorResponse) => (this.error = apiErrorMessage(err, 'Couldn’t load your credits.')),
    });
  }

  buy(pack: CreditPack): void {
    if (this.buying) return;
    this.buying = pack.code;
    this.error = null;
    this.account.checkout(pack.code).subscribe({
      next: (r) => window.location.assign(r.checkout_url),
      error: (err: HttpErrorResponse) => {
        this.buying = null;
        this.error = apiErrorMessage(err, 'Couldn’t start the payment. Please try again.');
      },
    });
  }

  perCredit(p: CreditPack): string {
    return (p.price_tnd / p.credits).toFixed(2);
  }

  isBestValue(p: CreditPack): boolean {
    const packs = this.data?.packs ?? [];
    return packs.length > 1 && p.code === packs[Math.floor(packs.length / 2)].code;
  }

  /** How many dashboards like the "A year of sales" example the balance covers. */
  typicalDashboardsLeft(): { count: number; label: string } | null {
    const example = this.data?.pricing.examples[1];
    if (!this.data || !example) return null;
    return { count: Math.floor(this.data.balance / example.credits), label: example.label.toLowerCase() };
  }

  trackEntry(_: number, e: LedgerEntry): number {
    return e.id;
  }
}
