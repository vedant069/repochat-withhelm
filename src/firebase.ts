import { initializeApp, FirebaseApp } from 'firebase/app';
import { getAuth, Auth } from 'firebase/auth';
import { getFirestore, Firestore } from 'firebase/firestore';

const ELB_DOMAIN = 'ae696e9b245be4b62bb210a46310e8b1-2071806289.us-west-2.elb.amazonaws.com';

const firebaseConfig = {
  apiKey: "AIzaSyDXbtijpoiyRzWY6GqFBuZtGsoYJwSq4IM",
  authDomain: "interview-pro-d2bfa.firebaseapp.com", // Use Firebase domain
  projectId: "interview-pro-d2bfa",
  storageBucket: "interview-pro-d2bfa.appspot.com",
  messagingSenderId: "784928195899",
  appId: "1:784928195899:web:a613651ca13a506c64a31e",
  measurementId: "G-8VM6M0XE82"
};

const authorizedDomains = [
  ELB_DOMAIN,
  'localhost',
  '127.0.0.1',
  'interview-pro-d2bfa.firebaseapp.com',
  '192.168.49.2'
].filter(Boolean);

let app: FirebaseApp;
let auth: Auth;
let db: Firestore;

try {
  app = initializeApp(firebaseConfig);
  auth = getAuth(app);
  db = getFirestore(app);
  
  // Set custom auth domain for OAuth redirects
  if (auth.config) {
    auth.config.authDomain = "interview-pro-d2bfa.firebaseapp.com";
  }
} catch (error) {
  console.error('Error initializing Firebase:', error);
  throw error;
}

export { app, auth, db, authorizedDomains };