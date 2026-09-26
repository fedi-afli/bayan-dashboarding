import { Component, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterLink } from '@angular/router';

@Component({
  selector: 'app-landing-page',
  standalone: true,
  imports: [CommonModule, RouterLink],
  templateUrl: './landing-page.component.html',
})
export class LandingPageComponent implements OnInit {
  loaded = false;

  ngOnInit(): void {
    // Small delay so the fade-in / bar-grow transitions actually trigger on load.
    setTimeout(() => (this.loaded = true), 50);
  }
}
