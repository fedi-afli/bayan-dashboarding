import { Routes } from '@angular/router';

import { PipelineComponent } from './components/pipeline/pipeline.component';

export const routes: Routes = [
  { path: 'pipeline', component: PipelineComponent },
  { path: '', pathMatch: 'full', redirectTo: 'pipeline' },
  { path: '**', redirectTo: 'pipeline' },
];
