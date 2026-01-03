import { useState } from 'react';
import { Save, Volume2, FileText } from 'lucide-react';

export interface AppSettings {
    format: 'mp3' | 'flac' | 'm4a' | 'wav';
    quality: 'best' | 'good';
    filenameTemplate: string;
}

export const DEFAULT_SETTINGS: AppSettings = {
    format: 'mp3',
    quality: 'best',
    filenameTemplate: '{title}'
};

interface SettingsProps {
    settings: AppSettings;
    onSave: (newSettings: AppSettings) => void;
}

export default function Settings({ settings, onSave }: SettingsProps) {
    const [localSettings, setLocalSettings] = useState<AppSettings>(settings);
    const [isSaved, setIsSaved] = useState(false);

    const handleChange = (key: keyof AppSettings, value: any) => {
        setLocalSettings(prev => ({ ...prev, [key]: value }));
        setIsSaved(false);
    };

    const handleSave = () => {
        onSave(localSettings);
        setIsSaved(true);
        setTimeout(() => setIsSaved(false), 2000);
    };

    return (
        <div className="max-w-4xl mx-auto space-y-8 animate-fade-in pb-20">
            <h1 className="text-3xl font-bold bg-clip-text text-transparent bg-gradient-to-r from-white to-slate-400">Settings</h1>

            {/* Audio Preferences */}
            <section className="bg-surface border border-slate-700/50 rounded-2xl p-6 space-y-6">
                <div className="flex items-center gap-3 border-b border-slate-700/50 pb-4">
                    <Volume2 className="text-primary" />
                    <h2 className="text-xl font-semibold">Audio Preferences</h2>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
                    <div className="space-y-3">
                        <label className="text-sm text-slate-400">Audio Format</label>
                        <div className="grid grid-cols-2 gap-3">
                            {['mp3', 'flac', 'm4a', 'wav'].map(fmt => (
                                <button
                                    key={fmt}
                                    onClick={() => handleChange('format', fmt)}
                                    className={`py-2 px-4 rounded-xl border transition-all ${localSettings.format === fmt
                                        ? 'bg-primary/20 border-primary text-white font-medium'
                                        : 'bg-slate-800/50 border-slate-700 text-slate-400 hover:bg-slate-800'
                                        }`}
                                >
                                    {fmt.toUpperCase()}
                                </button>
                            ))}
                        </div>
                    </div>

                    <div className="space-y-3">
                        <label className="text-sm text-slate-400">Quality Strategy</label>
                        <select
                            value={localSettings.quality}
                            onChange={(e) => handleChange('quality', e.target.value)}
                            className="w-full bg-slate-800/50 border border-slate-700 rounded-xl px-4 py-2 text-white focus:outline-none focus:border-primary"
                        >
                            <option value="best">Best Available (320kbps/Lossless)</option>
                            <option value="good">Standard (192kbps)</option>
                        </select>
                    </div>
                </div>
            </section>

            {/* Filename Template */}
            <section className="bg-surface border border-slate-700/50 rounded-2xl p-6 space-y-6">
                <div className="flex items-center gap-3 border-b border-slate-700/50 pb-4">
                    <FileText className="text-primary" />
                    <h2 className="text-xl font-semibold">File Naming</h2>
                </div>
                <div className="space-y-3">
                    <div className="flex items-center gap-2 text-slate-400">
                        <label className="text-sm">Filename Template</label>
                    </div>
                    <div className="flex gap-2">
                        <input
                            type="text"
                            value={localSettings.filenameTemplate || ""}
                            onChange={(e) => handleChange('filenameTemplate', e.target.value)}
                            className="flex-1 bg-slate-800/50 border border-slate-700 rounded-xl px-4 py-2 text-white font-mono text-sm focus:outline-none focus:border-primary"
                            placeholder="{artist} - {title}"
                        />
                    </div>
                    <div className="flex gap-2 flex-wrap">
                        {['{artist}', '{title}', '{album}', '{track_number}', '{year}'].map(tag => (
                            <button
                                key={tag}
                                onClick={() => handleChange('filenameTemplate', (localSettings.filenameTemplate || "") + tag)}
                                className="px-2 py-1 bg-slate-800 rounded-md text-xs text-primary hover:bg-slate-700 border border-slate-700 transition"
                            >
                                {tag}
                            </button>
                        ))}
                    </div>
                    <p className="text-xs text-slate-500">
                        Default: <span className="font-mono text-slate-400">{`{title}`}</span>
                    </p>
                </div>
            </section>

            {/* Save Action */}
            <div className="flex justify-end pt-4">
                <button
                    onClick={handleSave}
                    className="flex items-center gap-2 px-8 py-3 bg-primary hover:bg-sky-400 text-white rounded-xl font-bold shadow-lg shadow-primary/20 transition-all active:scale-95"
                >
                    <Save size={20} />
                    {isSaved ? 'Saved!' : 'Save Changes'}
                </button>
            </div>
        </div>
    );
}
