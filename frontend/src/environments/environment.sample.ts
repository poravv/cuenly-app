import { Environment } from './environment.interface';

export const environment: Environment = {
  production: false,
  apiUrl: '',
  frontendApiKey: 'cuenly-frontend-dev-key-2025',
  firebase: {
    apiKey: "<API_KEY>",
    authDomain: "<PROJECT>.firebaseapp.com",
    projectId: "<PROJECT>",
    storageBucket: "<PROJECT>.firebasestorage.app",
    messagingSenderId: "<SENDER_ID>",
    appId: "<APP_ID>",
    measurementId: "<MEASUREMENT_ID>"
  }
};
