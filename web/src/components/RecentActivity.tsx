import { useEffect, useState } from 'react';
import { PlayCircle, Music, Youtube, MoreVertical } from 'lucide-react';

import { apiClient, endpoints, type HistoryItem } from '../api';

export default function RecentActivity() {
    const [history, setHistory] = useState<HistoryItem[]>([]);

    useEffect(() => {
        // Fetch history
        async function fetchHistory() {
            try {
            const res = await apiClient.get(endpoints.history());
                // Use slice to get last 4 items for the "Recent" view
                setHistory(res.data.slice(0, 4));
            } catch (e) {
                console.error("Failed to load history", e);
            }
        }

        // Initial fetch
        fetchHistory();

        // Real-time polling (every 5 seconds)
        const interval = setInterval(fetchHistory, 5000);
        return () => clearInterval(interval);
    }, []);

    const displayItems = history;

    if (displayItems.length === 0) {
        return (
            <section className="space-y-6 animate-fade-in-up">
                <div className="flex items-center justify-between">
                    <h2 className="text-2xl font-bold">Recent Activity</h2>
                </div>
                <div className="p-8 text-center border border-white/5 rounded-2xl bg-white/5 text-slate-400">
                    <p>No recent downloads yet.</p>
                </div>
            </section>
        );
    }

    return (
        <section className="space-y-6 animate-fade-in-up">
            <div className="flex items-center justify-between">
                <h2 className="text-2xl font-bold">Recent Activity</h2>
                <button className="text-primary hover:text-white transition-colors text-sm font-medium">View All</button>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
                {displayItems.map((item, i) => (
                    <ActivityCard key={i} item={item} />
                ))}
            </div>
        </section>
    );
}

function ActivityCard({ item }: { item: HistoryItem }) {
    // Determine gradient based on provider
    const getGradient = (p: string) => {
        switch (p.toLowerCase()) {
            case 'spotify': return 'from-green-500/20 to-emerald-900/40 border-green-500/20';
            case 'youtube': return 'from-red-500/20 to-rose-900/40 border-red-500/20';
            case 'soundcloud': return 'from-orange-500/20 to-amber-900/40 border-orange-500/20';
            default: return 'from-slate-700/50 to-slate-800/50 border-slate-700';
        }
    };

    const getIcon = (p: string) => {
        switch (p.toLowerCase()) {
            case 'spotify': return <Music size={20} className="text-green-500" />;
            case 'youtube': return <Youtube size={20} className="text-red-500" />;
            case 'soundcloud': return <PlayCircle size={20} className="text-orange-500" />;
            default: return <Music size={20} className="text-slate-400" />;
        }
    };

    const timeAgo = (dateStr: string) => {
        if (!dateStr) return '';
        const date = new Date(dateStr);
        const now = new Date();
        const diffInSeconds = Math.floor((now.getTime() - date.getTime()) / 1000); // UTC to Local handling

        if (diffInSeconds < 60) return 'Just now';
        const minutes = Math.floor(diffInSeconds / 60);
        if (minutes < 60) return `${minutes}m ago`;
        const hours = Math.floor(minutes / 60);
        if (hours < 24) return `${hours}h ago`;
        return date.toLocaleDateString();
    };

    return (
        <div className="group relative bg-surface border border-slate-700/50 rounded-2xl overflow-hidden hover:-translate-y-1 transition-all duration-300 shadow-lg hover:shadow-primary/5">
            {/* Image Placeholder */}
            <div className={`h-40 w-full bg-linear-to-br ${getGradient(item.provider ?? 'unknown')} flex items-center justify-center relative`}>
                <div
                    className="absolute inset-0 opacity-20"
                    style={{
                        backgroundImage:
                            "radial-gradient(rgba(255,255,255,0.10) 1px, transparent 1px)",
                        backgroundSize: "6px 6px",
                    }}
                ></div>
                <div className="bg-surface/30 p-4 rounded-full backdrop-blur-sm border border-white/10 shadow-2xl group-hover:scale-110 transition-transform">
                    {getIcon(item.provider ?? 'unknown')}
                </div>
            </div>

            {/* Content */}
            <div className="p-4 space-y-2">
                <div className="flex justify-between items-start">
                    <h3 className="font-semibold text-white line-clamp-1" title={item.title}>
                        {item.title || "Unknown Playlist"}
                    </h3>
                    <button className="text-slate-500 hover:text-white"><MoreVertical size={16} /></button>
                </div>

                <div className="flex items-center justify-between text-xs text-slate-400">
                    <div className="flex items-center gap-3">
                        <span className="flex items-center gap-1">
                            {item.track_count} tracks
                        </span>
                        <span>•</span>
                        <span className="capitalize">{item.provider ?? 'unknown'}</span>
                    </div>
                    <span>{timeAgo(item.timestamp ?? '')}</span>
                </div>
            </div>
        </div>
    );
}


