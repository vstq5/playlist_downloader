import React from 'react';
import ReactDOM from 'react-dom/client';
import App from './App.tsx';
import './index.css';
import { HelmetProvider } from 'react-helmet-async';
import axios from 'axios';
import { getDeviceId } from './utils/device';

// Global Axios Config for Device Isolation
axios.defaults.headers.common['X-Device-ID'] = getDeviceId();

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <HelmetProvider>
      <App />
    </HelmetProvider>
  </React.StrictMode>,
)
