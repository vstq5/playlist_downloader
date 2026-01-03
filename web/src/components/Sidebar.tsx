import React from 'react';
import { Home, Search, Library, Download, Settings, Shield } from 'lucide-react';

interface SidebarProps {
    currentView: string;
    onNavigate: (view: any) => void;
}

export default function Sidebar({ currentView, onNavigate }: SidebarProps) {
    return (
        <aside className="h-full glass-nav flex flex-col justify-between p-6 overflow-y-auto [-webkit-overflow-scrolling:touch]">
            <div>
                {/* Logo */}
                <div className="flex items-center gap-4 mb-12 px-2 cursor-pointer group" onClick={() => onNavigate('home')}>
                    <div className="relative w-10 h-10">
                        <div className="absolute inset-0 bg-primary/50 blur-lg rounded-full group-hover:bg-primary/80 transition-colors"></div>
                        <img src="/logo.png" alt="Logo" className="relative w-10 h-10 object-contain drop-shadow-[0_0_10px_rgba(139,92,246,0.5)]"
                            onError={(e) => {
                                e.currentTarget.style.display = 'none';
                                e.currentTarget.nextElementSibling?.classList.remove('hidden');
                            }}
                        />
                        <div className="hidden w-10 h-10 rounded-xl bg-linear-to-br from-primary to-accent items-center justify-center shadow-lg shadow-primary/20">
                            <Download className="w-6 h-6 text-white" />
                        </div>
                    </div>
                    <div>
                        <h1 className="font-bold text-2xl tracking-tighter bg-clip-text text-transparent bg-linear-to-r from-white to-primary">Aura</h1>
                        <p className="text-[10px] text-primary uppercase tracking-widest font-semibold">Downloader</p>
                    </div>
                </div>

                {/* Navigation */}
                <nav className="space-y-3">
                    <NavItem
                        icon={<Home size={20} />}
                        label="Home"
                        active={currentView === 'home'}
                        onClick={() => onNavigate('home')}
                    />
                    <NavItem
                        icon={<Search size={20} />}
                        label="Search"
                        active={currentView === 'search'}
                        onClick={() => onNavigate('search')}
                    />
                    <NavItem
                        icon={<Library size={20} />}
                        label="Library"
                        active={currentView === 'library'}
                        onClick={() => onNavigate('library')}
                    />
                </nav>

                <div className="mt-10">
                    <button
                        onClick={() => onNavigate('downloads')}
                        className={`w-full flex items-center gap-3 px-4 py-3 rounded-xl transition-all border group ${currentView === 'downloads'
                            ? 'bg-primary text-white shadow-lg shadow-primary/20 border-primary'
                            : 'bg-surface/50 hover:bg-surface border-white/5 hover:border-white/10 text-slate-300 hover:text-white'
                            }`}
                    >
                        <div className={`p-1.5 rounded-lg transition-colors ${currentView === 'downloads' ? 'bg-primary text-white shadow-lg' : 'bg-slate-800 text-slate-400 group-hover:text-white'
                            }`}>
                            <Download size={18} />
                        </div>
                        <span className="font-semibold text-sm">Downloads</span>
                        {/* Glow Effect */}

                    </button>
                </div>
            </div>

            {/* Footer / Settings */}
            <div className="space-y-2 pt-6 border-t border-white/5">
                <NavItem icon={<Shield size={20} />} label="Legal & Privacy" onClick={() => onNavigate('legal')} />
                <NavItem icon={<Settings size={20} />} label="Settings" onClick={() => onNavigate('settings')} />
            </div>
        </aside>
    );

}

interface NavItemProps {
    icon: React.ReactNode;
    label: string;
    active?: boolean;
    onClick: () => void;
}

function NavItem({ icon, label, active, onClick }: NavItemProps) {
    return (
        <button
            onClick={onClick}
            className={`w-full flex items-center gap-3 px-4 py-3 rounded-xl transition-all duration-300 group
                ${active
                    ? 'bg-linear-to-r from-primary/10 to-transparent text-primary font-semibold border-l-2 border-primary'
                    : 'text-slate-400 hover:text-white hover:bg-white/5'
                }`}
        >
            <span className={`${active ? 'text-primary drop-shadow-[0_0_8px_rgba(139,92,246,0.5)]' : 'text-slate-400 group-hover:text-white group-hover:drop-shadow-[0_0_5px_rgba(255,255,255,0.5)]'} transition-all duration-300`}>
                {icon}
            </span>
            <span>{label}</span>
        </button>
    );
}
