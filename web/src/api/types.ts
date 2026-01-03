export type TaskStatus =
  | 'pending'
  | 'preparing'
  | 'ready'
  | 'queued'
  | 'downloading'
  | 'zipping'
  | 'completed'
  | 'cancelled'
  | 'error';

export type TrackStatus = 'pending' | 'queued' | 'downloading' | 'completed' | 'error';

export interface Track {
  id: string;
  title?: string;
  artist?: string;
  status?: TrackStatus;
  progress?: number;
  url?: string;
}

export interface PlaylistInfo {
  title?: string;
  provider?: string;
  track_count?: number;
  cover_url?: string;
  thumbnail?: string;
  tracks?: Track[];
  url?: string;
}

export interface Task {
  id: string;
  title?: string;
  progress: number;
  status: TaskStatus;
  message?: string;
  zip_path?: string;
  updated_at?: string;
  status_updated_at?: string;
  thumbnail?: string;
  provider?: string;
  track_count?: number;
  playlist?: PlaylistInfo;
}

export interface HistoryItem {
  task_id: string;
  title?: string;
  provider?: string;
  track_count?: number;
  zip_path?: string | null;
  timestamp?: string;
}

export interface SearchResult {
  title: string;
  uploader: string;
  duration: number;
  url: string;
  thumbnail: string;
  type: 'track' | 'album' | 'playlist' | 'video';
  source: 'spotify' | 'youtube' | 'soundcloud';
  meta?: string;
}

export interface Suggestion {
  label: string;
  value: string;
  type: 'text' | 'spotify' | 'youtube' | 'soundcloud';
  action?: 'search' | 'view' | 'download';
  kind?: 'track' | 'album' | 'playlist' | 'video';
}
