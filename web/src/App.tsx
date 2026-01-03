import React, { useState, useEffect, useRef } from 'react';
import { Helmet } from 'react-helmet-async';
import Layout from './components/Layout';
import Hero from './components/Hero';
import RecentActivity from './components/RecentActivity';
import Onboarding from './components/Onboarding';
import PlaylistView from './components/PlaylistView';
import DownloadQueue from './components/DownloadQueue';
import Search from './components/Search';
import Library from './components/Library';

import Legal from './components/Legal';
import Settings, { DEFAULT_SETTINGS } from './components/Settings';
import type { AppSettings } from './components/Settings';
import Player from './components/Player';
import { isMobile } from './utils/device';

import { apiClient, endpoints, type Task } from './api';

function App() {
  const [view, setView] = useState<'home' | 'preview' | 'downloads' | 'library' | 'search' | 'settings' | 'legal'>('home');

  // --- Settings State ---
  const [settings, setSettings] = useState<AppSettings>(() => {
    const saved = localStorage.getItem('appSettings');
    return saved ? JSON.parse(saved) : DEFAULT_SETTINGS;
  });

  const updateSettings = (newSettings: AppSettings) => {
    setSettings(newSettings);
    localStorage.setItem('appSettings', JSON.stringify(newSettings));
  };

  // Active View State
  const [activeTaskId, setActiveTaskId] = useState<string | null>(null);
  const [activePlaylist, setActivePlaylist] = useState<any>(null); // TODO: type with PlaylistInfo
  const [isLoading, setIsLoading] = useState(false);
  const [loadingMessage, setLoadingMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  // Global Download State
  const [allTasks, setAllTasks] = useState<Task[]>([]);
  const handledCompletions = useRef<Set<string>>(new Set());
  const [isFirstLoad, setIsFirstLoad] = useState(true);

  // Player State
  const [activeTrack, setActiveTrack] = useState<{ id: string; title: string; artist: string; url: string; coverUrl?: string } | null>(null);

  const [toast, setToast] = useState<{ message: string, type: 'success' | 'error' } | null>(null);
  const [isSyncing, setIsSyncing] = useState(false);
  const syncOnNextPoll = useRef(false);

  // Search State
  const [searchState, setSearchState] = useState<{
    query: string;
    results: any[];
    searched: boolean;
    activeFilter: 'all' | 'spotify' | 'youtube' | 'soundcloud';
  }>({
    query: '',
    results: [],
    searched: false,
    activeFilter: 'all'
  });

  const updateSearchState = (updates: Partial<typeof searchState>) => {
    setSearchState(prev => ({ ...prev, ...updates }));
  };

  const showToast = (message: string, type: 'success' | 'error' = 'success') => {
    setToast({ message, type });
    setTimeout(() => setToast(null), 3000);
  };

  const getDownloadUrl = async (taskId: string) => {
    const res = await apiClient.get(endpoints.downloadToken(taskId));
    const token = res.data?.token as string | undefined;
    if (!token) throw new Error('Missing download token');
    return `/api${endpoints.downloadFile(taskId)}?token=${encodeURIComponent(token)}`;
  };

  // --- Handlers ---

  const handleSearch = async (url: string) => {
    setError(null);
    setIsLoading(true);
    setLoadingMessage(null);
    setActivePlaylist(null);

    try {
      const options = {
        format: settings.format,
        quality: settings.quality,
        filename_template: settings.filenameTemplate,
      };

      const res = await apiClient.post(endpoints.prepare(), { url, options });
      setActiveTaskId(res.data.task_id);
      showToast("Fetching metadata...", 'success');
    } catch (err) {
      console.error(err);
      setError('Failed to fetch playlist. Please check the URL.');
      showToast("Failed to fetch metadata", 'error');
      setIsLoading(false);
      setLoadingMessage(null);
    }
  };

  const handleDownload = async (selectedIndices?: number[]) => {
    if (!activeTaskId) return;
    setIsLoading(true);
    try {
      await apiClient.post(endpoints.start(activeTaskId), { selected_indices: selectedIndices });
      setView('downloads');
      showToast("Download started", 'success');
      setIsLoading(false);
    } catch (err) {
      console.error(err);
      setError('Failed to start download.');
      showToast("Failed to start download", 'error');
      setIsLoading(false);
    }
  };

  const handleQuickDownload = async (url: string) => {
    setIsLoading(true);
    setError(null);
    showToast("Starting download...", 'success');
    setActiveTaskId(null);

    try {
      const options = {
        format: settings.format,
        quality: settings.quality,
        filename_template: settings.filenameTemplate,
      };
      const res = await apiClient.post(endpoints.prepare(), { url, options });
      const newTaskId = res.data.task_id;
      await apiClient.post(endpoints.start(newTaskId));

      showToast("Download added to queue", 'success');
      setView('downloads');
    } catch (err) {
      console.error("Quick download failed", err);
      showToast("Failed to download", 'error');
      setError('Failed to start download. Please check the URL.');
    } finally {
      setIsLoading(false);
    }
  };

  const handleStartTask = async (id: string) => {
    try {
      showToast("Starting task...", 'success');
      await apiClient.post(endpoints.start(id));
    } catch (e) {
      console.error(e);
      showToast("Failed to start", 'error');
    }
  };

  const handleDeleteTask = async (id: string) => {
    try {
      await apiClient.delete(endpoints.delete(id));
      showToast("Task deleted", 'success');
      setAllTasks(prev => prev.filter(t => t.id !== id));
    } catch (e) {
      console.error(e);
      showToast("Failed to delete", 'error');
    }
  };

  const handlePlay = async (task: any) => {
    try {
      const url = await getDownloadUrl(task.id);
      setActiveTrack({
        id: task.id,
        title: task.title || 'Unknown Track',
        artist: 'Local File',
        url,
        coverUrl: task.thumbnail
      });
    } catch (e) {
      console.error(e);
      showToast('Failed to load preview', 'error');
    }
  };

  const handleCancelTask = async (id: string) => {
    // Optimistic UI: show cancelled immediately; next poll reconciles actual state.
    setAllTasks(prev => prev.map(t => (t.id === id ? { ...t, status: 'cancelled', message: 'Cancelling…' } : t)));
    try {
      showToast('Cancelling…', 'success');
      await apiClient.post(endpoints.cancel(id));
    } catch (e) {
      console.error(e);
      // Revert optimistic status on failure; next poll will also correct this.
      setAllTasks(prev => prev.map(t => (t.id === id ? { ...t, message: 'Cancel failed' } : t)));
      showToast('Failed to cancel', 'error');
    }
  };

  // --- Effects ---

  useEffect(() => {
    let mounted = true;
    let interval: number | undefined;
    const poll = async () => {
      const shouldShowSync = syncOnNextPoll.current;
      if (shouldShowSync) setIsSyncing(true);
      try {
        const res = await apiClient.get(endpoints.tasks());
        const newTasks: Task[] = res.data;

        if (!mounted) return;

        setAllTasks(prev => {
          // Optimized Diffing: Don't JSON.stringify the world
          if (prev.length !== newTasks.length) return newTasks;

          // Check for relevant changes in visible fields (id, status, progress, message)
          const hasChanges = newTasks.some((t: any, i: number) => {
            const p = prev[i];
            return p.id !== t.id || p.status !== t.status || p.progress !== t.progress || p.message !== t.message;
          });

          return hasChanges ? newTasks : prev;
        });

        if (isFirstLoad) {
          newTasks.forEach((t: any) => {
            if (t.status === 'completed') handledCompletions.current.add(t.id);
          });
          setIsFirstLoad(false);
          // Request Permission
          if ('Notification' in window && Notification.permission === 'default') {
            Notification.requestPermission();
          }
          return;
        }

        // Auto Download Check
        newTasks.forEach((t: any) => {
          if (t.status === 'completed' && !handledCompletions.current.has(t.id)) {
            handledCompletions.current.add(t.id);
            const mobile = isMobile();
            showToast(mobile ? `"${t.title}" ready! Open Downloads to save.` : `"${t.title}" ready! Saving...`, 'success');

            // Browser Notification
            if ('Notification' in window && Notification.permission === 'granted') {
              new Notification("Download Ready", {
                body: `${t.title || 'Playlist'} is ready for download.`,
              });
            }

            // Auto-save logic (desktop). Mobile browsers often block programmatic downloads.
            if (!mobile) {
              getDownloadUrl(t.id)
                .then((url) => {
                  const link = document.createElement('a');
                  link.href = url;
                  link.setAttribute('download', '');
                  document.body.appendChild(link);
                  link.click();
                  document.body.removeChild(link);
                })
                .catch((e) => {
                  console.error(e);
                  showToast('Auto-save failed', 'error');
                });
            }
          }
        });

        // Sync Active Playlist
        if (activeTaskId) {
          const active = newTasks.find((t: any) => t.id === activeTaskId);
          if (active) {
            if (active.status === 'pending' || active.status === 'preparing') {
              setIsLoading(true);
              setLoadingMessage(active.message || (active.status === 'pending' ? 'Queued...' : 'Fetching metadata...'));
            }
            if (active.status === 'ready' && view !== 'preview' && view !== 'downloads' && active.playlist) {
              setActivePlaylist(active.playlist);
              setView('preview');
              setIsLoading(false);
              setLoadingMessage(null);
            }
            if (active.playlist && view === 'preview') {
              setActivePlaylist((curr: any) => {
                if (JSON.stringify(curr) !== JSON.stringify(active.playlist)) return active.playlist;
                return curr;
              });
            }
            if (active.status === 'error') {
              setError(active.message || 'Task failed');
              showToast(active.message || 'Task failed', 'error');
              setIsLoading(false);
              setLoadingMessage(null);
              setActiveTaskId(null);
            }
          }
        }

      } catch (_err) {
        // ignore poll errors
      } finally {
        if (syncOnNextPoll.current) {
          syncOnNextPoll.current = false;
          setIsSyncing(false);
        }
      }
    };

    const stopPolling = () => {
      if (interval !== undefined) {
        clearInterval(interval);
        interval = undefined;
      }
    };

    const startPolling = () => {
      if (interval !== undefined) return;
      // Refresh immediately on resume so the UI doesn't look frozen.
      poll();
      interval = window.setInterval(poll, 3000);
    };

    const onVisibilityChange = () => {
      if (document.hidden) stopPolling();
      else {
        syncOnNextPoll.current = true;
        startPolling();
      }
    };

    document.addEventListener('visibilitychange', onVisibilityChange);

    // Initial: only start polling if we're visible.
    if (!document.hidden) startPolling();
    return () => {
      mounted = false;
      stopPolling();
      document.removeEventListener('visibilitychange', onVisibilityChange);
    };
  }, [activeTaskId, view, isFirstLoad]);

  // --- DnD Handler ---
  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    const text = e.dataTransfer.getData('text/plain');
    if (text && text.startsWith('http')) {
      handleSearch(text);
    }
  };
  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
  };


  return (
    <div
      className="bg-background text-white min-h-screen font-sans"
      onDrop={handleDrop}
      onDragOver={handleDragOver}
    >
      <Helmet>
        <title>
          {view === 'home' ? 'Aura Playlist Downloader' :
            view === 'downloads' ? 'My Downloads | Aura' :
              view === 'search' ? 'Search Music | Aura' :
                view === 'settings' ? 'Settings | Aura' :
                  'Aura Playlist Downloader'}
        </title>
      </Helmet>
      <Layout currentView={view} onNavigate={(v) => setView(v)}>

        {isSyncing && (
          <div className="fixed top-4 left-1/2 -translate-x-1/2 z-50 px-4 py-2 rounded-xl shadow-2xl backdrop-blur-md border animate-fade-in flex items-center gap-3 bg-white/10 border-white/15 text-white/80">
            <span className="text-sm font-medium">Syncing…</span>
          </div>
        )}

        {toast && (
          <div className={`fixed top-4 right-4 z-50 px-6 py-3 rounded-xl shadow-2xl backdrop-blur-md border animate-fade-in flex items-center gap-3 ${toast.type === 'success' ? 'bg-green-500/10 border-green-500/20 text-green-400' : 'bg-red-500/10 border-red-500/20 text-red-400'
            }`}>
            <div className={`w-2 h-2 rounded-full ${toast.type === 'success' ? 'bg-green-500' : 'bg-red-500'}`}></div>
            <span className="font-medium">{toast.message}</span>
          </div>
        )}

        {(view === 'home') && (
          <div className="space-y-12">
            <Hero onSearch={handleSearch} isLoading={isLoading} loadingMessage={loadingMessage || undefined} />
            {error && (
              <div className="p-4 bg-red-500/10 border border-red-500/20 text-red-500 rounded-xl text-center">
                {error}
              </div>
            )}
            <RecentActivity />
            <Onboarding />
          </div>
        )}

        {view === 'search' && (
          <Search
            onDownload={handleQuickDownload}
            onView={(url) => {
              handleSearch(url);
            }}
            savedState={searchState}
            onStateChange={updateSearchState}
          />
        )}

        {view === 'preview' && activePlaylist && (
          <PlaylistView
            playlist={activePlaylist}
            onDownload={handleDownload}
            onBack={() => setView('home')}
            isLoading={isLoading}
          />
        )}

        {view === 'downloads' && (
          <DownloadQueue
            tasks={allTasks}
            onStart={handleStartTask}
            onCancel={handleCancelTask}
            onGetDownloadUrl={getDownloadUrl}
            onDelete={handleDeleteTask}
            onPlay={handlePlay}
          />
        )}

        {view === 'library' && (
          <Library />
        )}

        {view === 'settings' && (
          <Settings settings={settings} onSave={updateSettings} />
        )}

        {view === 'legal' && (
          <Legal />
        )}

        {/* Persistent Player */}
        <Player track={activeTrack} onClose={() => setActiveTrack(null)} />

      </Layout>
    </div>
  );
}

export default App;
