import React, { useState } from 'react';
import Sidebar from './Sidebar';
import { Menu, X } from 'lucide-react';

interface LayoutProps {
    children: React.ReactNode;
    currentView: string;
    onNavigate: (view: any) => void;
}

export default function Layout({ children, currentView, onNavigate }: LayoutProps) {
    const [isMobileMenuOpen, setIsMobileMenuOpen] = useState(false);

    const handleNavigate = (view: any) => {
        onNavigate(view);
        setIsMobileMenuOpen(false);
    }

    return (
        <div className="flex h-screen bg-background text-white font-sans overflow-hidden relative">
            {/* Aurora Background */}
            <div className="fixed inset-0 aurora-gradient opacity-30 pointer-events-none z-0"></div>
            <div className="fixed inset-0 bg-[url('/grid.svg')] bg-center [mask-image:linear-gradient(180deg,white,rgba(255,255,255,0))] opacity-10 pointer-events-none z-0"></div>

            {/* Mobile Header */}
            <div className="md:hidden fixed top-0 left-0 right-0 h-16 bg-surface/80 backdrop-blur-md border-b border-white/5 z-50 flex items-center justify-between px-4">
                <div className="flex items-center gap-2">
                    <img src="/logo.png" className="w-8 h-8" onError={(e) => e.currentTarget.style.display = 'none'} />
                    <span className="font-bold text-lg">Aura</span>
                </div>
                <button onClick={() => setIsMobileMenuOpen(!isMobileMenuOpen)} className="p-2 text-white">
                    {isMobileMenuOpen ? <X /> : <Menu />}
                </button>
            </div>

            {/* Sidebar */}
            <div className={`
                fixed left-0 z-40 w-72 transform transition-transform duration-300 ease-in-out md:relative md:translate-x-0
                top-16 bottom-0 md:top-0 md:bottom-0
                ${isMobileMenuOpen ? 'translate-x-0' : '-translate-x-full'}
            `}>
                <Sidebar currentView={currentView} onNavigate={handleNavigate} />
            </div>

            {/* Overlay for mobile */}
            {isMobileMenuOpen && (
                <div
                    className="fixed inset-0 bg-black/50 z-30 md:hidden backdrop-blur-sm touch-none overscroll-contain"
                    onClick={() => setIsMobileMenuOpen(false)}
                    onTouchMove={(e) => e.preventDefault()}
                />
            )}

            {/* Main Content Area */}
            <main className="flex-1 min-h-0 overflow-y-auto relative z-10 scroll-smooth pt-16 md:pt-0 pb-24 flex flex-col [-webkit-overflow-scrolling:touch]">
                <div className="container mx-auto px-4 py-8 md:px-12 md:py-10 max-w-7xl flex-1 min-h-0 flex flex-col">
                    {children}
                </div>
            </main>
        </div>
    );
}
