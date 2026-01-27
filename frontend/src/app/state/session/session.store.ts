import { Injectable } from '@angular/core';
import { Store, StoreConfig } from '@datorama/akita';

export interface UserProfile {
    name: string;
    email: string;
    photoUrl?: string;
}

export interface SessionState {
    token: string | null;
    user: UserProfile | null;
    isLoading: boolean;
}

export function createInitialState(): SessionState {
    return {
        token: null,
        user: null,
        isLoading: false
    };
}

@Injectable({ providedIn: 'root' })
@StoreConfig({ name: 'session' })
export class SessionStore extends Store<SessionState> {
    constructor() {
        super(createInitialState());
    }

    login(user: UserProfile, token: string) {
        this.update({ user, token, isLoading: false });
    }

    logout() {
        this.update(createInitialState());
    }
}
