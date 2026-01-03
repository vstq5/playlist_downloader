import React, { useState } from 'react';
import { Link, Loader2, PlayCircle, Music, Youtube } from 'lucide-react';

interface HeroProps {
    onSearch: (url: string) => void;
    isLoading?: boolean;
    loadingMessage?: string;
}

export default function Hero({ onSearch, isLoading, loadingMessage }: HeroProps) {
    const [url, setUrl] = useState('');

    const handleSubmit = (e: React.FormEvent) => {
        e.preventDefault();
        if (url.trim() && !isLoading) {
            onSearch(url.trim());
        }
    };

    return (
        <div className="flex flex-col items-center justify-center min-h-[70vh] text-center space-y-8 animate-fade-in">
            {/* Header Text */}
            <div className="space-y-4 max-w-3xl">
                <h1 className="text-5xl md:text-6xl font-bold tracking-tight">
                    Download Playlists from <br />
                    <span className="bg-linear-to-r from-primary via-accent to-secondary bg-clip-text text-transparent">
                        Spotify, YouTube, & SoundCloud
                    </span>
                </h1>
                <p className="text-slate-400 text-lg md:text-xl max-w-2xl mx-auto">
                    Simply paste the playlist URL below and let us handle the rest.
                    Quick, easy, and efficient.
                </p>
            </div>

            {/* Input Area */}
            <div className="w-full max-w-2xl mx-auto relative group">
                <div className="absolute inset-0 bg-linear-to-r from-primary to-secondary rounded-2xl blur-xl opacity-20 group-hover:opacity-30 transition-opacity duration-500"></div>
                <form onSubmit={handleSubmit} className="relative flex items-center bg-surface border border-slate-700/50 rounded-2xl p-2 shadow-2xl">
                    <div className="pl-4 text-slate-500">
                        <Link size={24} />
                    </div>
                    <input
                        type="text"
                        placeholder="Paste your link here..."
                        className="flex-1 bg-transparent border-none text-white text-lg px-4 py-3 focus:ring-0 placeholder:text-slate-600"
                        value={url}
                        onChange={(e) => setUrl(e.target.value)}
                    />
                    <button
                        type="submit"
                        disabled={!!isLoading}
                        className={`bg-primary text-white px-8 py-3 rounded-xl font-semibold transition-all shadow-lg shadow-primary/20 flex items-center gap-2 ${isLoading ? 'opacity-60 cursor-not-allowed' : 'hover:bg-sky-400'}`}
                    >
                        {isLoading ? (
                            <>
                                <Loader2 size={18} className="animate-spin" />
                                Loading
                            </>
                        ) : (
                            'Download'
                        )}
                    </button>
                </form>

                {isLoading && (
                    <div className="mt-3 text-sm text-slate-400 flex items-center justify-center gap-2">
                        <Loader2 size={16} className="animate-spin" />
                        <span>{loadingMessage || 'Fetching metadata...'}</span>
                    </div>
                )}
            </div>

            {/* Platform Badges */}
            <div className="flex flex-wrap justify-center gap-4 pt-8 opacity-90">
                <a
                    href="https://open.spotify.com"
                    target="_blank"
                    rel="noopener noreferrer"
                    className="flex items-center gap-2 px-6 py-3 rounded-full bg-slate-800/50 border border-slate-700/50 text-slate-300 hover:text-white hover:border-[#1DB954]/50 hover:bg-[#1DB954]/10 hover:shadow-[0_0_20px_rgba(29,185,84,0.3)] transition-all duration-300 group"
                >
                    <Music size={20} className="text-[#1DB954] group-hover:scale-110 transition-transform" />
                    <span className="font-medium">Spotify</span>
                </a>

                <a
                    href="https://www.youtube.com"
                    target="_blank"
                    rel="noopener noreferrer"
                    className="flex items-center gap-2 px-6 py-3 rounded-full bg-slate-800/50 border border-slate-700/50 text-slate-300 hover:text-white hover:border-[#FF0000]/50 hover:bg-[#FF0000]/10 hover:shadow-[0_0_20px_rgba(255,0,0,0.3)] transition-all duration-300 group"
                >
                    <Youtube size={20} className="text-[#FF0000] group-hover:scale-110 transition-transform" />
                    <span className="font-medium">YouTube</span>
                </a>

                <a
                    href="https://soundcloud.com"
                    target="_blank"
                    rel="noopener noreferrer"
                    className="flex items-center gap-2 px-6 py-3 rounded-full bg-slate-800/50 border border-slate-700/50 text-slate-300 hover:text-white hover:border-[#FF5500]/50 hover:bg-[#FF5500]/10 hover:shadow-[0_0_20px_rgba(255,85,0,0.3)] transition-all duration-300 group"
                >
                    <PlayCircle size={20} className="text-[#FF5500] group-hover:scale-110 transition-transform" />
                    <span className="font-medium">SoundCloud</span>
                </a>
            </div>
        </div>
    );
}
