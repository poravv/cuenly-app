import { Injectable } from '@angular/core';
import { Query } from '@datorama/akita';
import { SessionStore, SessionState } from './session.store';

@Injectable({ providedIn: 'root' })
export class SessionQuery extends Query<SessionState> {
    isLoggedIn$ = this.select(state => !!state.token);
    selectUser$ = this.select(state => state.user);
    selectIsLoading$ = this.select(state => state.isLoading);

    constructor(protected override store: SessionStore) {
        super(store);
    }
}
