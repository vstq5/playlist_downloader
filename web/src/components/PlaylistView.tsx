import { useState, useEffect } from 'react';
import { Download, CheckCircle, Circle, Loader2 } from 'lucide-react';
import { Virtuoso } from 'react-virtuoso';
import { useMobileQueue } from '../hooks/useMobileQueue';
import { isIOS, isMobile } from '../utils/device';

// Types (should match your API response)
interface Track {
    title: string;
    url: string;
    duration?: string;
    artist?: string;
}

interface PlaylistData {
    title: string;
    provider: string;
    tracks: Track[];
    track_count: number;
    cover_url?: string;
}

interface PlaylistViewProps {
    playlist: PlaylistData;
    onDownload: (selectedIndices: number[]) => void;
    onBack?: () => void;
    isLoading?: boolean;
}

export default function PlaylistView({ playlist, onDownload, isLoading }: PlaylistViewProps) {
    // Selection State
    const [selectedIndices, setSelectedIndices] = useState<Set<number>>(new Set());

    // Mobile Queue State
    const mobileQueue = useMobileQueue();
    const isMobileDevice = isMobile();
    const isIOSDevice = isIOS();

    // Initialize with all selected by default
    useEffect(() => {
        if (playlist?.tracks) {
            const all = new Set(playlist.tracks.map((_, i) => i));
            setSelectedIndices(all);
        }
    }, [playlist]);

    const toggleTrack = (index: number) => {
        const newSet = new Set(selectedIndices);
        if (newSet.has(index)) {
            newSet.delete(index);
        } else {
            newSet.add(index);
        }
        setSelectedIndices(newSet);
    };

    const toggleAll = () => {
        if (selectedIndices.size === playlist.tracks.length) {
            setSelectedIndices(new Set());
        } else {
            const all = new Set(playlist.tracks.map((_, i) => i));
            setSelectedIndices(all);
        }
    };

    const handleZipDownloadClick = () => {
        // Mobile-first: for 1–3 tracks, default to sequential MP3 fallback (iOS-friendly).
        if (isMobileDevice && selectedIndices.size > 0 && selectedIndices.size <= 3) {
            handleSequentialMp3FallbackClick();
            return;
        }

        // All platforms: server-side download (ZIP for multiple tracks, MP3 for a single track)
        onDownload(Array.from(selectedIndices));
    };

    const handleSequentialMp3FallbackClick = () => {
        const tracksToDownload = Array.from(selectedIndices).map(i => ({
            url: playlist.tracks[i].url,
            title: playlist.tracks[i].title
        }));
        mobileQueue.addToQueue(tracksToDownload);
    };

    // Mobile Queue Overlay
    if (mobileQueue.isProcessing) {
        const currentItem = mobileQueue.queue[mobileQueue.currentIdx];
        const total = mobileQueue.queue.length;
        const current = mobileQueue.currentIdx + 1;
        const progress = (current / total) * 100;

        return (
            <div className="fixed inset-0 z-50 bg-black/95 backdrop-blur-md flex items-center justify-center p-6 animate-fade-in touch-none">
                <div className="bg-surface border border-slate-700 p-8 rounded-2xl w-full max-w-md space-y-8 shadow-2xl relative">
                    <div className="text-center space-y-3">
                        <div className="inline-flex p-3 rounded-full bg-primary/10 text-primary mb-2">
                            <Loader2 size={32} className="animate-spin" />
                        </div>
                        <h2 className="text-2xl font-bold text-white">Downloading...</h2>
                        <p className="text-slate-400 text-sm">Please keep this tab open and active.</p>
                    </div>

                    <div className="space-y-4">
                        <div className="flex justify-between text-sm font-medium">
                            <span className="text-white">Track {current} of {total}</span>
                            <span className="text-primary">{Math.round(progress)}%</span>
                        </div>
                        <div className="h-3 bg-slate-800 rounded-full overflow-hidden border border-white/5">
                            <div
                                className="h-full bg-primary transition-all duration-500 ease-out"
                                style={{ width: `${progress}%` }}
                            />
                        </div>

                        {currentItem && (
                            <div className="p-4 bg-slate-800/50 rounded-xl flex items-center gap-3 border border-white/5 shadow-inner">
                                <div className="flex-1 min-w-0">
                                    <h4 className="font-semibold text-white truncate text-sm">{currentItem.title}</h4>
                                    <div className="flex items-center gap-2 mt-1">
                                        <span className={`w-1.5 h-1.5 rounded-full ${currentItem.status === 'error' ? 'bg-red-500' :
                                            currentItem.status === 'completed' ? 'bg-green-500' : 'bg-primary'}`}></span>
                                        <p className="text-xs text-slate-500 capitalize">{currentItem.status}...</p>
                                    </div>
                                </div>
                            </div>
                        )}
                    </div>

                    {currentItem?.status === 'ready' && (
                        <button
                            onClick={() => mobileQueue.downloadCurrent()}
                            className="w-full py-3 rounded-xl bg-primary hover:bg-sky-400 text-white font-bold transition-colors active:scale-[0.98]"
                        >
                            Download track
                        </button>
                    )}

                    <div className="p-4 bg-yellow-500/10 border border-yellow-500/20 rounded-xl text-yellow-500 text-xs text-center leading-relaxed">
                        <p><strong>iOS/Safari:</strong> Downloads require a tap for each track.</p>
                    </div>
                </div>
            </div>
        );
    }

    return (
        <div className="flex flex-col md:flex-row gap-6 md:gap-8 h-[calc(100vh-100px)] md:h-[calc(100vh-140px)] animate-fade-in pb-20 md:pb-0">
            {/* Left Side: Sticky Album Art & Actions */}
            <div className="md:w-80 lg:w-96 shrink-0 flex flex-col gap-6">
                <div className="aspect-square rounded-3xl bg-linear-to-br from-primary via-surface to-surface border border-white/10 shadow-2xl relative overflow-hidden group">
                    {/* Placeholder Art or Image */}
                    {playlist.cover_url ? (
                        <img
                            src={playlist.cover_url}
                            alt={playlist.title}
                            className="absolute inset-0 w-full h-full object-cover"
                        />
                    ) : (
                        <div className="absolute inset-0 flex items-center justify-center bg-surface/50">
                            <span className="text-6xl font-black text-white/5 opacity-50 select-none">
                                {playlist.provider.slice(0, 2).toUpperCase()}
                            </span>
                        </div>
                    )}
                    <div className="absolute inset-0 bg-linear-to-t from-black/90 via-black/40 to-transparent flex flex-col justify-end p-6 md:p-8">
                        <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-primary/20 text-primary text-xs font-medium w-fit mb-3 border border-primary/10">
                            {playlist.provider}
                        </div>
                        <h1 className="text-2xl md:text-3xl lg:text-4xl font-bold leading-tight mb-2 text-white line-clamp-2">
                            {playlist.title}
                        </h1>
                        <p className="text-slate-400 text-sm md:text-base">{playlist.tracks.length} tracks</p>
                    </div>
                </div>

                <div className="p-4 md:p-6 rounded-2xl bg-surface border border-slate-700/50 space-y-4">
                    <button
                        onClick={handleZipDownloadClick}
                        disabled={isLoading || selectedIndices.size === 0}
                        className={`w-full py-3 md:py-4 rounded-xl text-white font-bold text-lg shadow-lg shadow-primary/25 transition-all active:scale-[0.98] flex items-center justify-center gap-2
                            ${isLoading || selectedIndices.size === 0 ? 'bg-primary/50 cursor-not-allowed opacity-50' : 'bg-primary hover:bg-sky-400'}`}
                    >
                        {isLoading ? (
                            <>
                                <div className="animate-spin rounded-full h-5 w-5 border-b-2 border-white"></div>
                                Starting...
                            </>
                        ) : (
                            <>
                                <Download size={20} />
                                {isMobileDevice && selectedIndices.size > 0 && selectedIndices.size <= 3
                                    ? `Download (${selectedIndices.size}) — Sequential`
                                    : `Download (${selectedIndices.size})`}
                            </>
                        )}
                    </button>

                    {isMobileDevice && (
                        <button
                            onClick={handleSequentialMp3FallbackClick}
                            disabled={isLoading || selectedIndices.size === 0}
                            className="w-full py-3 md:py-4 rounded-xl text-slate-200 font-semibold text-base border border-slate-700/70 bg-surface hover:bg-slate-700/30 transition-colors active:scale-[0.98]"
                        >
                            Sequential MP3s (fallback)
                        </button>
                    )}

                    <p className="text-center text-xs text-slate-500">
                        {isMobileDevice
                            ? (selectedIndices.size <= 3
                                ? 'Tip: Sequential MP3s works best for 1–3 tracks.'
                                : 'Default: Download as ZIP (server-side).')
                            : `Estimated size: ~${(selectedIndices.size * 4.5).toFixed(0)}MB`}
                    </p>

                    {isMobileDevice && isIOSDevice && selectedIndices.size > 1 && (
                        <p className="text-center text-xs text-slate-500">
                            Downloads as a .zip — open in Files to extract.
                        </p>
                    )}
                </div>
            </div>

            {/* Right Side: Tracklist */}
            <div className="flex-1 bg-surface/50 border border-slate-700/30 rounded-3xl overflow-hidden flex flex-col min-h-[400px]">
                <div className="p-4 md:p-6 border-b border-slate-700/50 bg-surface/80 backdrop-blur-md sticky top-0 z-10 flex justify-between items-center">
                    <h3 className="font-semibold text-lg">Tracklist</h3>
                    <div className="flex gap-2 text-sm">
                        <button
                            onClick={toggleAll}
                            className="px-3 py-1.5 rounded-lg bg-surface hover:bg-slate-700/50 border border-slate-700 text-slate-300 transition-colors"
                        >
                            {selectedIndices.size === playlist.tracks.length ? 'Deselect All' : 'Select All'}
                        </button>
                    </div>
                </div>

                <div className="flex-1 h-full relative">
                    {/* Explicit Height Container for Virtuoso on Mobile */}
                    <div className="absolute inset-0">
                        <Virtuoso
                            style={{ height: '100%' }}
                            data={playlist.tracks}
                            itemContent={(i, track) => {
                                const isSelected = selectedIndices.has(i);
                                return (
                                    <div className="p-2">
                                        <div
                                            key={i}
                                            onClick={() => toggleTrack(i)}
                                            className={`group flex items-center gap-3 md:gap-4 p-3 rounded-xl transition-colors border cursor-pointer active:scale-[0.99]
                                                ${isSelected ? 'bg-white/10 border-white/10' : 'hover:bg-white/5 border-transparent hover:border-white/5'}`}
                                        >
                                            <div className="w-6 flex items-center justify-center shrink-0">
                                                {isSelected ? (
                                                    <CheckCircle size={20} className="text-primary" />
                                                ) : (
                                                    <Circle size={20} className="text-slate-600 group-hover:text-slate-400" />
                                                )}
                                            </div>

                                            <div className="flex-1 min-w-0">
                                                <div className={`font-medium truncate text-sm md:text-base ${isSelected ? 'text-white' : 'text-slate-300'}`}>
                                                    {track.title}
                                                </div>
                                                <div className="text-xs text-slate-500 truncate">{track.artist}</div>
                                            </div>
                                            <div className="text-xs text-slate-600 font-mono shrink-0">
                                                {track.duration || '--:--'}
                                            </div>
                                        </div>
                                    </div>
                                )
                            }}
                        />
                    </div>
                </div>
            </div>
        </div>
    );
}
