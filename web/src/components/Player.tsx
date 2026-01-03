import { useEffect, useRef, useState } from 'react';
import WaveSurfer from 'wavesurfer.js';
import { Play, Pause, X, Volume2, SkipBack, SkipForward } from 'lucide-react';

interface PlayerProps {
    track: {
        id: string;
        title: string;
        artist: string;
        url: string; // Stream URL
        coverUrl?: string;
    } | null;
    onClose: () => void;
    onNext?: () => void;
    onPrev?: () => void;
}

export default function Player({ track, onClose, onNext, onPrev }: PlayerProps) {
    const waveformRef = useRef<HTMLDivElement>(null);
    const [wavesurfer, setWavesurfer] = useState<WaveSurfer | null>(null);
    const [isPlaying, setIsPlaying] = useState(false);
    const [duration, setDuration] = useState(0);
    const [currentTime, setCurrentTime] = useState(0);

    useEffect(() => {
        if (!track || !waveformRef.current) return;

        // Destroy previous instance
        if (wavesurfer) wavesurfer.destroy();

        const ws = WaveSurfer.create({
            container: waveformRef.current,
            waveColor: '#4f46e5', // Primary indigo
            progressColor: '#818cf8', // Lighter indigo
            cursorColor: '#fff',
            barWidth: 2,
            barGap: 3,
            height: 40,
            normalize: true,
        });

        ws.load(track.url);

        ws.on('ready', () => {
            setDuration(ws.getDuration());
            ws.play();
            setIsPlaying(true);
        });

        ws.on('audioprocess', () => {
            setCurrentTime(ws.getCurrentTime());
        });

        ws.on('finish', () => {
            setIsPlaying(false);
            if (onNext) onNext();
        });

        ws.on('click', () => {
            ws.play();
            setIsPlaying(true);
        });

        setWavesurfer(ws);

        return () => {
            ws.destroy();
        };
    }, [track]);

    const togglePlay = () => {
        if (wavesurfer) {
            wavesurfer.playPause();
            setIsPlaying(wavesurfer.isPlaying());
        }
    };

    if (!track) return null;

    const formatTime = (time: number) => {
        const min = Math.floor(time / 60);
        const sec = Math.floor(time % 60);
        return `${min}:${sec < 10 ? '0' : ''}${sec}`;
    };

    return (
        <div className="fixed bottom-0 left-0 right-0 bg-slate-900/95 backdrop-blur-xl border-t border-white/10 p-4 z-50 animate-slide-up shadow-2xl">
            <div className="max-w-7xl mx-auto flex items-center gap-6">

                {/* Track Info */}
                <div className="flex items-center gap-4 w-64 flex-shrink-0">
                    {track.coverUrl ? (
                        <img src={track.coverUrl} className="w-12 h-12 rounded-lg object-cover" />
                    ) : (
                        <div className="w-12 h-12 bg-white/10 rounded-lg flex items-center justify-center">
                            <Volume2 size={20} className="text-white/50" />
                        </div>
                    )}
                    <div className="min-w-0">
                        <h3 className="font-bold text-white truncate">{track.title}</h3>
                        <p className="text-sm text-white/50 truncate">{track.artist}</p>
                    </div>
                </div>

                {/* Controls */}
                <div className="flex flex-col items-center gap-1 flex-1">
                    <div className="flex items-center gap-4">
                        <button onClick={onPrev} className="text-white/70 hover:text-white"><SkipBack size={20} /></button>
                        <button
                            onClick={togglePlay}
                            className="w-10 h-10 rounded-full bg-white text-black flex items-center justify-center hover:scale-105 transition active:scale-95"
                        >
                            {isPlaying ? <Pause size={20} fill="black" /> : <Play size={20} fill="black" className="ml-0.5" />}
                        </button>
                        <button onClick={onNext} className="text-white/70 hover:text-white"><SkipForward size={20} /></button>
                    </div>
                    <div className="flex items-center gap-3 w-full max-w-2xl text-xs text-white/50 font-mono">
                        <span>{formatTime(currentTime)}</span>
                        <div ref={waveformRef} className="flex-1 cursor-pointer h-10" />
                        <span>{formatTime(duration)}</span>
                    </div>
                </div>

                {/* Actions */}
                <div className="flex items-center gap-4 w-64 justify-end">
                    <button onClick={onClose} className="p-2 hover:bg-white/10 rounded-full text-white/70 hover:text-white transition">
                        <X size={20} />
                    </button>
                </div>
            </div>
        </div>
    );
}
