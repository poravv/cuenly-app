import { Injectable } from '@angular/core';
import { BehaviorSubject } from 'rxjs';

@Injectable({
    providedIn: 'root'
})
export class FileTransferService {
    private filesSource = new BehaviorSubject<File[]>([]);
    files$ = this.filesSource.asObservable();

    constructor() { }

    setFiles(files: File[]): void {
        this.filesSource.next(files);
    }

    getFiles(): File[] {
        const files = this.filesSource.getValue();
        this.clearFiles(); // Clear after retrieving to avoid stale data
        return files;
    }

    clearFiles(): void {
        this.filesSource.next([]);
    }

    hasFiles(): boolean {
        return this.filesSource.getValue().length > 0;
    }
}
