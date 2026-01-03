import { useEffect, useState } from 'react';
import { Library as LibraryIcon, Music, Folder } from 'lucide-react';

import { apiClient, endpoints, type HistoryItem } from '../api';

export default function Library() {
    const [history, setHistory] = useState<HistoryItem[]>([]);
    const [isLoading, setIsLoading] = useState(true);

    useEffect(() => {
        const fetchHistory = async () => {
            try {
                const res = await apiClient.get(endpoints.history());
                if (Array.isArray(res.data)) {
                    setHistory(res.data.reverse());
                } else {
                    setHistory([]);
                }
            } catch (err) {
                console.error("Failed to fetch history", err);
                setHistory([]); // Reset on error
            } finally {
                setIsLoading(false);
            }
        };
        fetchHistory();
    }, []);

    const getIcon = (item: HistoryItem) => {
        if ((item.track_count || 0) > 1) return <Folder size={24} className="text-accent" />;
        return <Music size={24} className="text-primary" />;
    };

    if (isLoading) {
        return (
            <div className="flex items-center justify-center min-h-[60vh] text-slate-500">
                <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary"></div>
            </div>
        );
    }

    if (history.length === 0) {
        return (
            <div className="flex flex-col items-center justify-center min-h-[60vh] text-slate-500 space-y-4">
                <div className="p-6 rounded-full bg-slate-800/50">
                    <LibraryIcon size={48} className="opacity-50" />
                </div>
                <h2 className="text-2xl font-bold text-slate-300">Your Library is Empty</h2>
                <p>Downloaded playlists will appear here.</p>
            </div>
        );
    }

    return (
        <div className="max-w-5xl mx-auto space-y-8 animate-fade-in pb-20">
            <div className="flex items-center gap-4">
                <div className="p-3 bg-slate-800 rounded-xl">
                    <LibraryIcon size={24} className="text-white" />
                </div>
                <div>
                    <h2 className="text-2xl font-bold text-white">Your Library</h2>
                    <p className="text-slate-400 text-sm">{history.length} items downloaded</p>
                </div>
            </div>

            <div className="grid gap-4">
                {history.map((item, i) => (
                    <div key={i} className="bg-surface border border-slate-700/50 p-4 rounded-xl flex items-center gap-4 hover:border-slate-600 transition-colors group">
                        <div className="w-12 h-12 rounded-lg bg-slate-800 flex items-center justify-center shrink-0">
                            {getIcon(item)}
                        </div>

                        <div className="flex-1 min-w-0">
                            <h3 className="font-semibold text-white truncate">{item.title || 'Unknown'}</h3>
                            <div className="flex items-center gap-4 text-xs text-slate-400 mt-1">
                                <span className="flex items-center gap-1">
                                    <div className={`w-1.5 h-1.5 rounded-full ${item.provider === 'spotify' ? 'bg-[#1DB954]' : item.provider === 'youtube' ? 'bg-[#FF0000]' : 'bg-slate-500'}`}></div>
                                    {(item.provider || 'unknown').toUpperCase()}
                                </span>
                                <span>•</span>
                                <span>{item.track_count ?? 0} {(item.track_count ?? 0) === 1 ? 'Track' : 'Tracks'}</span>
                            </div>
                        </div>

                        {/* Local File Action (Mock) - Browsers generally blocks local file links not served by web server */}
                        {/* But we can simulate "Show in Folder" if strict local app, or just show path */}
                        {item.zip_path ? (
                            <div className="text-right hidden sm:block">
                                <div className="text-xs text-slate-500 font-mono bg-slate-900/50 px-2 py-1 rounded truncate max-w-[200px]" title={String(item.zip_path)}>
                                    {String(item.zip_path).split('\\').pop()?.split('/').pop()}
                                </div>
                            </div>
                        ) : null}
                    </div>
                ))}
            </div>
        </div>
    );
}
