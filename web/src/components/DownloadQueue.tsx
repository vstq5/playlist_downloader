import { useState, useMemo } from 'react';
import { Download, AlertCircle, CheckCircle, Trash2, RefreshCw, Play, ChevronDown, ChevronUp } from 'lucide-react';
import { Virtuoso } from 'react-virtuoso';
import { isIOS, isMobile } from '../utils/device';


interface Track {
    id: string;
    title?: string;
    artist?: string;
    status?: 'pending' | 'queued' | 'downloading' | 'completed' | 'error';
    progress?: number;
    url?: string;
    error?: string;
}

interface PlaylistInfo {
    title?: string;
    provider?: string;
    track_count?: number;
    cover_url?: string;
    thumbnail?: string;
    tracks?: Track[];
    url?: string;
}


interface Task {
    id: string;
    title?: string;
    progress: number;
    status: 'pending' | 'preparing' | 'ready' | 'queued' | 'downloading' | 'zipping' | 'completed' | 'cancelled' | 'error';
    message?: string;
    zip_path?: string;
    updated_at?: string;
    status_updated_at?: string;
    thumbnail?: string;
    provider?: string;
    track_count?: number;
    playlist?: PlaylistInfo;
}

interface DownloadQueueProps {
    tasks: Task[];
    onStart: (id: string) => void;
    onCancel: (id: string) => void;
    onGetDownloadUrl: (id: string) => Promise<string>;
    onDelete: (id: string) => void;
    onPlay: (task: Task) => void;
}

export default function DownloadQueue({ tasks, onStart, onCancel, onGetDownloadUrl, onDelete, onPlay }: DownloadQueueProps) {
    const [activeTab, setActiveTab] = useState<'all' | 'downloading' | 'completed'>('all');
    const [expanded, setExpanded] = useState<Set<string>>(() => new Set());

    const mobile = isMobile();
    const ios = isIOS();

    const toggleExpanded = (id: string) => {
        setExpanded(prev => {
            const next = new Set(prev);
            if (next.has(id)) next.delete(id);
            else next.add(id);
            return next;
        });
    };

    const filteredTasks = useMemo(() => {
        return tasks.filter(t => {
            if (activeTab === 'all') return true;
            if (activeTab === 'downloading') return ['pending', 'preparing', 'ready', 'queued', 'downloading', 'zipping'].includes(t.status);
            if (activeTab === 'completed') return t.status === 'completed';
            return true;
        });
    }, [tasks, activeTab]);

    const stats = useMemo(() => {
        const total = tasks.length;
        const completed = tasks.filter(t => t.status === 'completed').length;
        const downloading = tasks.filter(t => ['pending', 'preparing', 'ready', 'queued', 'downloading', 'zipping'].includes(t.status)).length;
        return { total, completed, downloading };
    }, [tasks]);

    return (
        <div className="max-w-4xl mx-auto w-full space-y-6 flex flex-col flex-1 min-h-0">
            {/* Header */}
            <div className="flex flex-col md:flex-row gap-4 items-center justify-between">
                <h2 className="text-3xl font-bold">Downloads</h2>

                {/* Tabs */}
                <div className="flex p-1 bg-white/5 rounded-xl border border-white/10">
                    {(['all', 'downloading', 'completed'] as const).map(tab => (
                        <button
                            key={tab}
                            onClick={() => setActiveTab(tab)}
                            className={`px-4 py-2 rounded-lg text-sm font-medium transition-all ${activeTab === tab
                                ? 'bg-white text-black shadow-lg'
                                : 'text-white/50 hover:text-white'
                                }`}
                        >
                            {tab.charAt(0).toUpperCase() + tab.slice(1)} ({
                                tab === 'all' ? stats.total : tab === 'downloading' ? stats.downloading : stats.completed
                            })
                        </button>
                    ))}
                </div>
            </div>

            {/* List Container (Virtuoso needs height) */}
            <div className="flex-1 min-h-[500px] border border-white/5 rounded-2xl bg-black/20 overflow-hidden backdrop-blur-sm">
                {filteredTasks.length === 0 ? (
                    <div className="flex flex-col items-center justify-center h-full text-white/30 space-y-4">
                        <Download size={48} />
                        <p>No downloads found</p>
                    </div>
                ) : (
                    <div className="h-full custom-scrollbar">
                        <Virtuoso
                            style={{ height: '100%' }}
                            data={filteredTasks}
                            itemContent={(_, task) => (
                                <div className="p-2">
                                    <div key={task.id} className="p-4 border-b border-white/5 hover:bg-white/5 transition-colors rounded-xl bg-surface/50">
                                        <TaskItem
                                            task={task}
                                            mobile={mobile}
                                            ios={ios}
                                            isExpanded={expanded.has(task.id)}
                                            onToggleExpanded={() => toggleExpanded(task.id)}
                                            onStart={onStart}
                                            onCancel={onCancel}
                                            onGetDownloadUrl={onGetDownloadUrl}
                                            onDelete={onDelete}
                                            onPlay={onPlay}
                                        />
                                    </div>
                                </div>
                            )}
                        />
                    </div>
                )}
            </div>
        </div>
    );
}

function TaskItem({
    task,
    mobile,
    ios,
    isExpanded,
    onToggleExpanded,
    onStart,
    onCancel,
    onGetDownloadUrl,
    onDelete,
    onPlay
}: {
    task: Task;
    mobile: boolean;
    ios: boolean;
    isExpanded: boolean;
    onToggleExpanded: () => void;
    onStart: (id: string) => void;
    onCancel: (id: string) => void;
    onGetDownloadUrl: (id: string) => Promise<string>;
    onDelete: (id: string) => void;
    onPlay: (t: Task) => void;
}) {
    const isDownloading = ['preparing', 'queued', 'downloading', 'zipping'].includes(task.status);
    const tracks = task.playlist?.tracks;
    const hasTracks = Array.isArray(tracks) && tracks.length > 0;
    const showTracksToggle = (task.track_count ?? task.playlist?.track_count ?? 0) > 1 || hasTracks;

    const canStart = task.status === 'pending' || task.status === 'ready';

    const isCancelling = task.status === 'cancelled' && (task.message || '').toLowerCase().startsWith('cancelling');

    const statusUpdatedAt = task.status_updated_at ? new Date(task.status_updated_at).getTime() : undefined;
    const now = Date.now();
    const READY_STALE_MS = 2 * 60 * 1000;
    const ACTIVE_STALE_MS = 10 * 60 * 1000;
    const isReadyStale = task.status === 'ready' && statusUpdatedAt !== undefined && (now - statusUpdatedAt) > READY_STALE_MS;
    const isActiveStale = ['queued', 'downloading', 'zipping'].includes(task.status) && statusUpdatedAt !== undefined && (now - statusUpdatedAt) > ACTIVE_STALE_MS;

    const helperMessage = (() => {
        if (!mobile) return task.message;
        if (task.status === 'ready') return 'Ready — tap Play to start the download.';
        if (task.status === 'completed') return ios ? 'Completed — tap Save to download (opens a new tab).' : 'Completed — tap Save to download.';
        return task.message;
    })();

    const saveLabel = (() => {
        if (!mobile) return 'Save';
        if (ios) return 'Save (opens new tab)';
        return 'Save file';
    })();

    const handleSave = async () => {
        const url = await onGetDownloadUrl(task.id);
        // iOS Safari is more reliable with a new tab.
        if (mobile && ios) window.open(url, '_blank', 'noopener,noreferrer');
        else window.location.assign(url);
    };

    const handleRetry = async () => {
        onCancel(task.id);
        // Give the cancel flag a moment to persist before re-start.
        window.setTimeout(() => onStart(task.id), 600);
    };

    return (
        <div className="space-y-3">
            <div className="flex items-center gap-4">
            {/* Icon Status */}
            <div className={`w-12 h-12 rounded-xl flex items-center justify-center shrink-0 ${task.status === 'completed' ? 'bg-green-500/20 text-green-500' :
                task.status === 'error' ? 'bg-red-500/20 text-red-500' :
                    'bg-blue-500/20 text-blue-500'
                }`}>
                {task.status === 'completed' ? <CheckCircle size={24} /> :
                    task.status === 'error' ? <AlertCircle size={24} /> :
                        <Download size={24} className={isDownloading ? 'animate-bounce' : ''} />}
            </div>

            {/* Content */}
            <div className="flex-1 min-w-0">
                <div className="flex justify-between mb-1">
                    <h4 className="font-semibold truncate pr-4">{task.title}</h4>
                    <span className="text-xs text-white/50 capitalize">{task.status}</span>
                </div>

                {/* Progress Bar */}
                <div className="h-2 bg-white/10 rounded-full overflow-hidden">
                    <div
                        className={`h-full transition-all duration-500 ${task.status === 'completed' ? 'bg-green-500' :
                            task.status === 'error' ? 'bg-red-500' : 'bg-blue-500'
                            }`}
                        style={{ width: `${task.progress}%` }}
                    />
                </div>
                <p className="text-xs text-white/40 mt-1 truncate">{helperMessage}</p>
            </div>

            {/* Actions */}
            <div className="flex items-center gap-2">
                {task.status === 'completed' && (
                    <>
                        <button
                            onClick={() => onPlay(task)}
                            className="p-2 hover:bg-white/10 rounded-lg text-green-400 transition"
                            title="Preview"
                        >
                            <Play size={18} />
                        </button>
                        <button
                            onClick={handleSave}
                            className="p-2 bg-white/10 hover:bg-white/20 rounded-lg text-sm font-medium transition"
                            title={mobile && ios ? 'Opens in a new tab' : 'Download file'}
                        >
                            {saveLabel}
                        </button>
                    </>
                )}

                {canStart && (
                    <button
                        onClick={() => onStart(task.id)}
                        className="p-2 hover:bg-white/10 rounded-lg text-blue-400"
                        title={task.status === 'ready' ? 'Start download' : 'Start task'}
                    >
                        <Play size={18} />
                    </button>
                )}

                {task.status === 'error' && (
                    <button onClick={() => onStart(task.id)} className="p-2 hover:bg-white/10 rounded-lg text-yellow-400">
                        <RefreshCw size={18} />
                    </button>
                )}

                {task.status === 'cancelled' && !isCancelling && (
                    <button onClick={() => onStart(task.id)} className="p-2 hover:bg-white/10 rounded-lg text-yellow-400" title="Retry">
                        <RefreshCw size={18} />
                    </button>
                )}

                {showTracksToggle && (
                    <button
                        onClick={onToggleExpanded}
                        className="p-2 hover:bg-white/10 rounded-lg text-white/50 hover:text-white transition"
                        title={isExpanded ? 'Hide tracks' : 'View tracks'}
                    >
                        {isExpanded ? <ChevronUp size={18} /> : <ChevronDown size={18} />}
                    </button>
                )}

                <button onClick={() => onDelete(task.id)} className="p-2 hover:bg-red-500/20 rounded-lg text-white/30 hover:text-red-500 transition">
                    <Trash2 size={18} />
                </button>
            </div>
        </div>

            {(isReadyStale || isActiveStale) && (
                <div className="rounded-xl border border-yellow-500/20 bg-yellow-500/10 px-3 py-2 text-xs text-yellow-200 flex items-center justify-between gap-3">
                    <span className="truncate">
                        {isReadyStale
                            ? 'This download has been ready for a while.'
                            : 'This download is taking longer than expected.'}
                    </span>
                    <div className="flex items-center gap-2 shrink-0">
                        {isReadyStale && canStart && (
                            <button onClick={() => onStart(task.id)} className="px-2 py-1 rounded-lg bg-white/10 hover:bg-white/20 transition">
                                Start
                            </button>
                        )}
                        {isActiveStale && (
                            <>
                                <button onClick={handleRetry} className="px-2 py-1 rounded-lg bg-white/10 hover:bg-white/20 transition">
                                    Retry
                                </button>
                                <button onClick={() => onCancel(task.id)} className="px-2 py-1 rounded-lg bg-red-500/20 hover:bg-red-500/30 text-red-200 transition">
                                    Cancel
                                </button>
                            </>
                        )}
                    </div>
                </div>
            )}

            {isExpanded && (
                <div className="mt-2 rounded-xl border border-white/10 bg-black/20">
                    <div className="px-4 py-3 border-b border-white/10 flex items-center justify-between">
                        <span className="text-sm font-medium text-white/80">Tracks</span>
                        <span className="text-xs text-white/40">
                            {hasTracks ? `${tracks!.length} shown` : 'Loading…'}
                        </span>
                    </div>

                    {hasTracks ? (
                        <div className="max-h-64 overflow-auto custom-scrollbar">
                            {tracks!.map((t, idx) => {
                                const s = t.status || 'pending';
                                const color = s === 'completed'
                                    ? 'text-green-400'
                                    : s === 'error'
                                        ? 'text-red-400'
                                        : s === 'downloading'
                                            ? 'text-blue-400'
                                            : 'text-white/50';
                                return (
                                    <div key={t.id ?? String(idx)} className="px-4 py-2 border-t border-white/5 flex items-center gap-3">
                                        <span className={`text-xs w-20 capitalize ${color}`}>{s}</span>
                                        <div className="min-w-0 flex-1">
                                            <div className="flex items-center gap-2">
                                                <div className="text-sm truncate text-white/90">{t.title || 'Unknown'}</div>
                                                {typeof t.progress === 'number' && t.progress >= 0 && t.progress < 100 && (
                                                    <span className="text-xs text-blue-400">{Math.round(t.progress)}%</span>
                                                )}
                                            </div>
                                            <div className="text-xs truncate text-white/40">{t.artist || ''}</div>
                                            {s === 'error' && t.error && (
                                                <div className="text-xs text-red-300/80 line-clamp-2">{t.error}</div>
                                            )}
                                            {typeof t.progress === 'number' && t.progress >= 0 && t.progress < 100 && (
                                                <div className="h-1 mt-1 bg-white/10 rounded-full overflow-hidden">
                                                    <div
                                                        className="h-full bg-blue-500 transition-all duration-500"
                                                        style={{ width: `${t.progress}%` }}
                                                    />
                                                </div>
                                            )}
                                        </div>
                                    </div>
                                );
                            })}
                        </div>
                    ) : (
                        <div className="px-4 py-4 text-sm text-white/40">
                            Track list will appear once metadata is ready.
                        </div>
                    )}
                </div>
            )}
        </div>
    );
}
