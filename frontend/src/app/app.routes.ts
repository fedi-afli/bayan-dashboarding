import { Routes } from '@angular/router';

import { LandingPageComponent } from './components/landing-page/landing-page.component';
import { PipelineComponent } from './components/pipeline/pipeline.component';
import { DashboardListComponent } from './components/dashboard-list/dashboard-list.component';
import { authGuard } from './auth/auth.guard';
import { AuthCallbackComponent } from './auth/auth-callback.component';

export const routes: Routes = [
  { path: '', component: LandingPageComponent, title: 'bayan — dashboards from your sales files' },
  { path: 'auth/callback', component: AuthCallbackComponent, title: 'Signing in · bayan' },
  { path: 'upload', component: PipelineComponent, canActivate: [authGuard], title: 'New dashboard · bayan' },
  { path: 'dashboards', component: DashboardListComponent, canActivate: [authGuard], title: 'Dashboards · bayan' },
  {
    path: 'dashboards/:id',
    canActivate: [authGuard],
    // lazy: keeps ECharts out of the landing page bundle
    loadComponent: () => import('./components/dashboard/dashboard.component').then((m) => m.DashboardComponent),
    title: 'Dashboard · bayan',
  },
  {
    path: 'dashboards/:id/mapping',
    canActivate: [authGuard],
    loadComponent: () => import('./components/mapping-page/mapping-page.component').then((m) => m.MappingPageComponent),
    title: 'Edit columns · bayan',
  },
  {
    path: 'credits',
    canActivate: [authGuard],
    loadComponent: () => import('./components/credits/credits.component').then((m) => m.CreditsComponent),
    title: 'Credits · bayan',
  },
  { path: 'pipeline', redirectTo: 'upload' },
  { path: '**', redirectTo: '' },
];
