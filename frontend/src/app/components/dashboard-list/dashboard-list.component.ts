import { CommonModule } from '@angular/common';
import { Component, OnInit } from '@angular/core';
import { HttpErrorResponse } from '@angular/common/http';
import { RouterLink } from '@angular/router';

import { DatasetSummary } from '../../models/models';
import { PipelineService, apiErrorMessage } from '../../services/pipeline.service';

interface MonthGroup {
  label: string;
  items: DatasetSummary[];
}

/** The account's dashboard history (newest first, by month) + unfinished uploads. */
@Component({
  selector: 'app-dashboard-list',
  standalone: true,
  imports: [CommonModule, RouterLink],
  templateUrl: './dashboard-list.component.html',
})
export class DashboardListComponent implements OnInit {
  groups: MonthGroup[] | null = null;
  drafts: DatasetSummary[] = [];
  total = 0;
  error: string | null = null;

  constructor(private pipeline: PipelineService) {}

  ngOnInit(): void {
    this.load();
  }

  load(): void {
    this.pipeline.listDatasets().subscribe({
      next: (all) => {
        const ready = all.filter((d) => d.status === 'ready');
        this.drafts = all.filter((d) => d.status === 'pending');
        this.total = ready.length;
        this.groups = this.byMonth(ready);
      },
      error: (err: HttpErrorResponse) => (this.error = apiErrorMessage(err, 'Couldn’t load your dashboards.')),
    });
  }

  discard(d: DatasetSummary): void {
    this.pipeline.deleteDataset(d.id).subscribe(() => (this.drafts = this.drafts.filter((x) => x.id !== d.id)));
  }

  private byMonth(items: DatasetSummary[]): MonthGroup[] {
    const groups: MonthGroup[] = [];
    for (const d of items) {
      const label = new Date(d.loaded_at ?? d.created_at).toLocaleDateString('en-GB', { month: 'long', year: 'numeric' });
      const last = groups[groups.length - 1];
      last?.label === label ? last.items.push(d) : groups.push({ label, items: [d] });
    }
    return groups;
  }
}
