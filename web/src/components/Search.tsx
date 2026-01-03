import React, { useState, useEffect, useRef } from 'react';
import { Search as SearchIcon, Download, Clock, User, Disc, Music, Youtube, LayoutList, Loader2, ArrowUpRight } from 'lucide-react';

import { apiClient, endpoints, type SearchResult, type Suggestion } from '../api';

interface SearchProps {
    onDownload: (url: string) => void;
    onView: (url: string) => void;
    savedState: {
        query: string;
        results: SearchResult[];
        searched: boolean;
        activeFilter: 'all' | 'spotify' | 'youtube' | 'soundcloud';
    };
    onStateChange: (updates: any) => void;
}

export default function Search({ onDownload, onView, savedState, onStateChange }: SearchProps) {
    // Destructure from savedState
    const { query, results, searched, activeFilter } = savedState;

    const [isLoading, setIsLoading] = useState(false);
    const [suggestions, setSuggestions] = useState<Suggestion[]>([]);
    const [showSuggestions, setShowSuggestions] = useState(false);
    const [viewAllSection, setViewAllSection] = useState<string | null>(null);
    const wrapperRef = useRef<HTMLDivElement>(null);

    // Helpers to update parent state
    const setQuery = (q: string) => onStateChange({ query: q });
    const setResults = (r: SearchResult[]) => onStateChange({ results: r });
    const setSearched = (s: boolean) => onStateChange({ searched: s });
    const setActiveFilter = (f: any) => onStateChange({ activeFilter: f });

    // Suggestion Debounce
    useEffect(() => {
        const timeoutId = setTimeout(async () => {
            if (query.trim().length >= 2 && !searched) {
                try {
                    const res = await apiClient.get(endpoints.suggestions(), { params: { q: query } });
                    setSuggestions(res.data || []);
                    setShowSuggestions(true);
                } catch (e) {
                    setSuggestions([]);
                }
            } else {
                setSuggestions([]);
                // Ensure the dropdown doesn't linger over the results view.
                setShowSuggestions(false);
            }
        }, 300); // 300ms debounce
        return () => clearTimeout(timeoutId);
    }, [query, searched]);

    // If a search has been executed, always hide the suggestions overlay.
    useEffect(() => {
        if (!searched) return;
        setShowSuggestions(false);
        setSuggestions([]);
    }, [searched]);

    // Click outside to close suggestions
    useEffect(() => {
        function handleClickOutside(event: MouseEvent) {
            if (wrapperRef.current && !wrapperRef.current.contains(event.target as Node)) {
                setShowSuggestions(false);
            }
        }
        document.addEventListener("mousedown", handleClickOutside);
        return () => document.removeEventListener("mousedown", handleClickOutside);
    }, [wrapperRef]);

    const handleSearch = async (e?: React.FormEvent, overrideQuery?: string) => {
        e?.preventDefault();
        const q = overrideQuery || query;
        if (!q.trim()) return;

        // Always close suggestions when the user submits a search.
        setShowSuggestions(false);
        setSuggestions([]);
        setViewAllSection(null);

        // If URL, direct action
        if (q.startsWith("http")) {
            onView(q);
            return;
        }

        setIsLoading(true);
        setSearched(true);

        // Update query if overridden (clicked suggestion)
        if (overrideQuery) setQuery(overrideQuery);

        try {
            const res = await apiClient.post(endpoints.search(), {
                query: q,
                providers: ['spotify', 'youtube', 'soundcloud']
            }, { timeout: 15000 });
            setResults(res.data || []);
        } catch (err) {
            console.error("Search failed", err);
            // setResults([]); // Optional: clear or keep old?
        } finally {
            setIsLoading(false);
        }
    };

    const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
        setQuery(e.target.value);
        setSearched(false);
        setShowSuggestions(true);
    };

    const handleSuggestionClick = (s: Suggestion) => {
        if (s.type === 'text' || s.action === 'search') {
            handleSearch(undefined, s.value); // Text search
            setShowSuggestions(false);
            return;
        }

        // Provider URLs: decide whether to preview (container) or download (track)
        if (s.action === 'download' || s.kind === 'track' || s.kind === 'video') {
            onDownload(s.value);
        } else {
            onView(s.value);
        }
        setShowSuggestions(false);
    };

    const formatDuration = (seconds: number) => {
        if (!seconds) return '';
        const mins = Math.floor(seconds / 60);
        const secs = Math.floor(seconds % 60);
        return `${mins}:${secs.toString().padStart(2, '0')}`;
    };

    const getIcon = (type: string) => {
        switch (type) {
            case 'album': return <Disc size={16} />;
            case 'playlist': return <LayoutList size={16} />;
            case 'video': return <Youtube size={16} />;
            default: return <Music size={16} />;
        }
    };

    const getSourceColor = (source: string) => {
        switch (source) {
            case 'spotify': return 'text-[#1DB954]';
            case 'youtube': return 'text-[#FF0000]';
            case 'soundcloud': return 'text-[#FF5500]';
            default: return 'text-slate-400';
        }
    };

    const filteredResults = results.filter(r => activeFilter === 'all' || r.source === activeFilter);

    const groupByType = (type: string) => filteredResults.filter(r => r.type === type);
    const tracks = groupByType('track');
    const albums = groupByType('album');
    const playlists = groupByType('playlist');
    const videos = groupByType('video');

    const renderCard = (item: SearchResult, i: number) => {
        const isContainer = item.type === 'album' || item.type === 'playlist';
        const handleClick = () => isContainer ? onView(item.url) : onDownload(item.url);

        return (
            <div key={i} onClick={handleClick} className="group bg-surface border border-slate-700/50 rounded-xl overflow-hidden hover:border-primary/50 transition-all hover:bg-slate-800/50 cursor-pointer flex flex-col h-full shadow-lg hover:shadow-primary/5">
                {/* Thumbnail */}
                <div className="aspect-square relative overflow-hidden bg-black/20">
                    {item.thumbnail ? (
                        <img src={item.thumbnail} alt={item.title} className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-500" />
                    ) : (
                        <div className="w-full h-full flex items-center justify-center text-slate-700">
                            {getIcon(item.type)}
                        </div>
                    )}

                    {/* Action Overlay */}
                    <div className="absolute inset-0 bg-black/40 opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center backdrop-blur-[1px]">
                        <div className={`p-3 rounded-full ${isContainer ? 'bg-white text-black' : 'bg-primary text-white'} transform scale-90 group-hover:scale-100 transition-transform shadow-xl`}>
                            {isContainer ? <LayoutList size={24} /> : <Download size={24} />}
                        </div>
                    </div>

                    {/* Duration Badge */}
                    {item.duration > 0 && (
                        <div className="absolute bottom-2 right-2 px-1.5 py-0.5 rounded bg-black/80 text-[10px] font-medium text-white flex items-center gap-1 backdrop-blur-sm">
                            <Clock size={10} />
                            {formatDuration(item.duration)}
                        </div>
                    )}
                </div>

                {/* Content */}
                <div className="p-3 flex-1 flex flex-col gap-2">
                    <div className="flex justify-between items-start gap-2">
                        <h3 className="font-semibold text-white text-sm line-clamp-2 leading-snug group-hover:text-primary transition-colors" title={item.title}>
                            {item.title}
                        </h3>
                    </div>

                    <div className="mt-auto space-y-1">
                        <div className="flex items-center gap-1 text-xs text-slate-400">
                            <User size={12} />
                            <span className="truncate">{item.uploader}</span>
                        </div>
                        <div className={`text-[10px] font-medium flex items-center gap-1 ${getSourceColor(item.source)}`}>
                            <div className="w-1.5 h-1.5 rounded-full bg-current"></div>
                            {item.source.toUpperCase()}
                        </div>
                    </div>
                </div>
            </div>
        );
    };

    const renderSection = (title: string, items: SearchResult[], icon: React.ReactNode, typeKey: string) => {
        if (items.length === 0) return null;

        const isExpanded = viewAllSection === typeKey;
        const visibleItems = isExpanded ? items : items.slice(0, 6);

        return (
            <section className="space-y-4">
                <div className="flex items-center justify-between px-2">
                    <div className="flex items-center gap-2 text-xl font-bold text-white/90">
                        {icon}
                        <h2>{title}</h2>
                        <span className="text-sm font-normal text-slate-500 ml-2">({items.length})</span>
                    </div>
                    {items.length > 6 && (
                        <button
                            onClick={() => setViewAllSection(isExpanded ? null : typeKey)}
                            className="text-primary text-sm font-bold hover:text-white transition-colors uppercase tracking-wider"
                        >
                            {isExpanded ? 'Show Less' : 'View All'}
                        </button>
                    )}
                </div>

                <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-4">
                    {visibleItems.map((item, i) => renderCard(item, i))}
                </div>
            </section>
        );
    };


    return (
        <div className="container mx-auto px-4 py-8 max-w-7xl animate-fade-in" ref={wrapperRef}>
            {/* Header + Search Input */}
            <div className="flex flex-col items-center gap-6 mb-12">
                <div className="text-center space-y-2">
                    <h1 className="text-4xl font-bold bg-clip-text text-transparent bg-linear-to-r from-white to-slate-400">
                        Find & Download
                    </h1>
                    <p className="text-slate-400 text-sm">
                        Search across Spotify, YouTube, and SoundCloud
                    </p>
                </div>

                <div className="relative w-full max-w-2xl z-50">
                    <form onSubmit={handleSearch} className="relative group">
                        <div className={`absolute inset-0 bg-linear-to-r from-primary/20 to-accent/20 rounded-2xl blur-lg transition-opacity duration-500 ${isLoading ? 'opacity-100' : 'opacity-0 group-hover:opacity-50'}`}></div>
                        <div className="relative flex items-center bg-surface border border-slate-700/50 rounded-2xl shadow-2xl focus-within:border-primary/50 focus-within:ring-4 focus-within:ring-primary/10 transition-all overflow-visible">
                            <SearchIcon className={`ml-4 ${isLoading ? 'text-primary animate-pulse' : 'text-slate-400'}`} size={20} />

                            <input
                                type="text"
                                value={query}
                                onChange={handleInputChange}
                                placeholder="Paste URL or search keywords..."
                                className="w-full bg-transparent border-none focus:ring-0 text-white placeholder-slate-500 h-14 px-4 text-base font-medium"
                                // Disable standard autocomplete to show ours
                                autoComplete="off"
                            />

                            <div className="pr-2 flex items-center gap-2">
                                {isLoading && <Loader2 className="animate-spin text-primary mr-2" size={20} />}
                                <button
                                    type="submit"
                                    disabled={isLoading}
                                    className="px-6 py-2 bg-white text-black font-bold rounded-xl hover:scale-105 active:scale-95 transition-all text-sm disabled:opacity-50 disabled:hover:scale-100"
                                >
                                    Search
                                </button>
                            </div>
                        </div>

                        {/* Suggestions Dropdown */}
                        {showSuggestions && suggestions.length > 0 && (
                            <div className="absolute top-full left-0 right-0 mt-2 bg-surface/95 backdrop-blur-xl border border-slate-700/50 rounded-xl shadow-2xl overflow-hidden animate-slide-up-fade">
                                <ul className="py-1">
                                    {suggestions.map((s, i) => (
                                        <li key={i}>
                                            <button
                                                type="button"
                                                onClick={() => handleSuggestionClick(s)}
                                                className="w-full text-left px-4 py-3 hover:bg-white/5 transition-colors flex items-center justify-between group"
                                            >
                                                <div className="flex items-center gap-3">
                                                    {s.type === 'spotify' ? (
                                                        <Disc size={16} className="text-[#1DB954]" />
                                                    ) : s.type === 'youtube' ? (
                                                        <Youtube size={16} className="text-[#FF0000]" />
                                                    ) : s.type === 'soundcloud' ? (
                                                        <Music size={16} className="text-[#FF5500]" />
                                                    ) : (
                                                        <SearchIcon size={16} className="text-slate-400" />
                                                    )}
                                                    <span className={`text-sm font-medium ${s.type === 'spotify' ? 'text-white' : 'text-slate-300 group-hover:text-white'}`}>
                                                        {s.label}
                                                    </span>
                                                </div>
                                                {s.type !== 'text' && (
                                                    <span className={`text-xs px-2 py-0.5 rounded-full flex items-center gap-1 ${
                                                        s.type === 'spotify'
                                                            ? 'text-[#1DB954] bg-[#1DB954]/10'
                                                            : s.type === 'youtube'
                                                                ? 'text-[#FF0000] bg-[#FF0000]/10'
                                                                : 'text-[#FF5500] bg-[#FF5500]/10'
                                                        }`}
                                                    >
                                                        {s.action === 'download' ? 'Download' : 'Open'} <ArrowUpRight size={10} />
                                                    </span>
                                                )}
                                            </button>
                                        </li>
                                    ))}
                                </ul>
                            </div>
                        )}
                    </form>
                </div>

                {/* Filters */}
                {results.length > 0 && (
                    <div className="flex gap-2 p-1 bg-surface/50 border border-slate-700/30 rounded-full backdrop-blur-md">
                        <FilterButton label="All Results" active={activeFilter === 'all'} onClick={() => setActiveFilter('all')} />
                        <FilterButton label="Spotify" active={activeFilter === 'spotify'} onClick={() => setActiveFilter('spotify')} icon={<div className="w-2 h-2 rounded-full bg-[#1DB954]"></div>} />
                        <FilterButton label="YouTube" active={activeFilter === 'youtube'} onClick={() => setActiveFilter('youtube')} icon={<div className="w-2 h-2 rounded-full bg-[#FF0000]"></div>} />
                        <FilterButton label="SoundCloud" active={activeFilter === 'soundcloud'} onClick={() => setActiveFilter('soundcloud')} icon={<div className="w-2 h-2 rounded-full bg-[#FF5500]"></div>} />
                    </div>
                )}
            </div>

            {/* Results Grid */}
            <div className="space-y-12">
                {results.length === 0 && searched && !isLoading && (
                    <div className="text-center py-20 animate-fade-in">
                        <div className="inline-flex items-center justify-center w-16 h-16 rounded-full bg-slate-800/50 mb-4 text-slate-500">
                            <SearchIcon size={32} />
                        </div>
                        <h3 className="text-xl font-bold text-white mb-2">No results found</h3>
                        <p className="text-slate-400 max-w-md mx-auto">
                            Try simpler keywords or paste a direct Spotify/YouTube URL.
                        </p>
                    </div>
                )}

                {renderSection('Top Tracks', tracks, <Music size={24} className="text-primary" />, 'track')}
                {renderSection('Albums', albums, <Disc size={24} className="text-secondary" />, 'album')}
                {renderSection('Playlists', playlists, <LayoutList size={24} className="text-accent" />, 'playlist')}
                {renderSection('Videos', videos, <Youtube size={24} className="text-red-500" />, 'video')}
            </div>
        </div>
    );
}

function FilterButton({ label, active, onClick, icon }: any) {
    return (
        <button
            onClick={onClick}
            className={`px-4 py-1.5 rounded-full text-sm font-medium transition-all flex items-center gap-2
                ${active ? 'bg-white text-black shadow-lg' : 'text-slate-400 hover:text-white hover:bg-white/5'}`}
        >
            {icon}
            {label}
        </button>
    );
}
