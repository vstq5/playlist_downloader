import { Shield, AlertTriangle, FileText, Lock } from 'lucide-react';

export default function Legal() {
    return (
        <div className="max-w-4xl mx-auto space-y-8 animate-fade-in pb-20">
            <div className="flex items-center gap-4 mb-8">
                <Shield size={40} className="text-primary" />
                <h1 className="text-4xl font-bold bg-clip-text text-transparent bg-gradient-to-r from-primary to-purple-400">
                    Legal & Privacy
                </h1>
            </div>

            {/* Disclaimer */}
            <section className="space-y-4">
                <div className="flex items-center gap-3 text-red-400">
                    <AlertTriangle size={28} />
                    <h2 className="text-2xl font-bold text-white">Disclaimer & Limitation of Liability</h2>
                </div>
                <div className="p-6 bg-red-500/10 border border-red-500/20 rounded-2xl text-slate-300 space-y-4">
                    <p>
                        <strong>Educational Purpose Only:</strong> This software ("Aura") is developed strictly for educational and private use. The developers do not condone piracy or the unauthorized distribution of copyrighted material.
                    </p>
                    <p>
                        <strong>No Affiliation:</strong> Aura is an independent project and is <strong>not</strong> affiliated, associated, authorized, endorsed by, or in any way officially connected with Spotify AB, Google LLC (YouTube), SoundCloud, or any of their subsidiaries or affiliates.
                    </p>
                    <p>
                        <strong>User Responsibility:</strong> By using this software, you agree that you are solely responsible for your actions. The developers accept <strong>no responsibility</strong> for any misuse of this software, copyright infringements, or legal issues arising from your use of this tool. You must ensure you have the right to download any media you access.
                    </p>
                </div>
            </section>

            {/* Privacy Policy */}
            <section className="space-y-4">
                <div className="flex items-center gap-3 text-green-400">
                    <Lock size={28} />
                    <h2 className="text-2xl font-bold text-white">Privacy Policy</h2>
                </div>
                <div className="p-6 bg-surface border border-white/5 rounded-2xl text-slate-300 space-y-4">
                    <p>
                        Your privacy is critical. Here is exactly what we (don't) track:
                    </p>
                    <ul className="list-disc pl-5 space-y-2">
                        <li><strong>No Personal Data Collection:</strong> We do not store your IP address, browser data, or personal information on our servers.</li>
                        <li><strong>No Cookies:</strong> This application does not use tracking cookies.</li>
                        <li><strong>Ephemeral Data:</strong> Download tasks and history are stored temporarily in the database for the functionality of the queue and are cleared upon server restart or manually by you.</li>
                        <li><strong>Third Party Services:</strong> When you paste a link, the backend server contacts Spotify/YouTube APIs directly to fetch metadata. These requests are subject to the privacy policies of those respective platforms.</li>
                    </ul>
                </div>
            </section>

            {/* License */}
            <section className="space-y-4">
                <div className="flex items-center gap-3 text-blue-400">
                    <FileText size={28} />
                    <h2 className="text-2xl font-bold text-white">License</h2>
                </div>
                <div className="p-6 bg-surface border border-white/5 rounded-2xl text-slate-300 space-y-4">
                    <p>
                        This project is open-source. You are free to view, modify, and distribute the code under the terms of the MIT License, provided that the original copyright notice and this permission notice are included in all copies or substantial portions of the Software.
                    </p>
                    <div className="p-4 bg-black/30 rounded-xl font-mono text-xs text-slate-400">
                        THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY.
                    </div>
                </div>
            </section>
        </div>
    );
}
