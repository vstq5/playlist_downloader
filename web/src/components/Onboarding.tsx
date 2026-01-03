import React from 'react';
import { Copy, Clipboard, Download } from 'lucide-react';

export default function Onboarding() {
    return (
        <section className="grid grid-cols-1 md:grid-cols-3 gap-6 py-12 animate-fade-in-up delay-100">
            <Step
                icon={<Copy size={32} />}
                step="1"
                title="Find your link"
                desc="Copy the URL of the playlist or track you want to download from Spotify, YouTube, or SoundCloud."
            />
            <Step
                icon={<Clipboard size={32} />}
                step="2"
                title="Paste & Customise"
                desc="Paste the link in the input field above. Typically we'll fetch the details automatically."
            />
            <Step
                icon={<Download size={32} />}
                step="3"
                title="Download"
                desc="Save your favorite music and playlists directly to your device as high-quality MP3s."
            />
        </section>
    );
}

function Step({ icon, step, title, desc }: { icon: React.ReactNode, step: string, title: string, desc: string }) {
    return (
        <div className="bg-surface/50 border border-slate-700/30 p-8 rounded-2xl relative overflow-hidden group hover:bg-surface/80 transition-all duration-300">
            <div className="absolute top-0 right-0 p-32 bg-primary/5 rounded-full blur-3xl -translate-y-1/2 translate-x-1/2 group-hover:bg-primary/10 transition-colors"></div>

            <div className="relative z-10">
                <div className="w-16 h-16 rounded-2xl bg-slate-800 border border-slate-700 mb-6 flex items-center justify-center text-white group-hover:scale-110 transition-transform duration-300 group-hover:border-primary/50 group-hover:shadow-lg group-hover:shadow-primary/20">
                    {icon}
                </div>

                <h3 className="text-xl font-bold text-white mb-2">
                    <span className="text-primary mr-2">{step}.</span>
                    {title}
                </h3>
                <p className="text-slate-400 leading-relaxed">
                    {desc}
                </p>
            </div>
        </div>
    );
}
