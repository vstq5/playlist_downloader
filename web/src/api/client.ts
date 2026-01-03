import axios from 'axios';
import { getDeviceId } from '../utils/device';

export const apiClient = axios.create({
  baseURL: '/api',
  headers: {
    'X-Device-ID': getDeviceId(),
  },
});
