import { Component, OnDestroy, OnInit } from '@angular/core';
import { Subscription } from 'rxjs';
import { AuthService } from './services/auth.service';

@Component({
  selector: 'app-root',
  templateUrl: './app.component.html',
  styleUrls: ['./app.component.scss']
})
export class AppComponent implements OnInit, OnDestroy {
  title = 'CuenlyApp';
  authReady = false;
  private sub = new Subscription();

  constructor(private auth: AuthService) {}

  ngOnInit(): void {
    this.sub.add(this.auth.ready$.subscribe(r => this.authReady = r));
  }

  ngOnDestroy(): void {
    this.sub.unsubscribe();
  }
}
