import { useEffect, useState, useRef } from 'react';

import { apiClient } from '../api/client';

const API_URL = '/api';

interface QueueItem {
    id: string; // The backend task ID
    originalUrl: string;
    title: string;
    status: 'pending' | 'preparing' | 'ready' | 'downloading' | 'completed' | 'error';
    progress: number;
    downloadUrl?: string;
}

interface BackendTask {
    id: string;
    status: string;
    title?: string;
    message?: string;
    progress?: number;
    playlist?: {
        title: string;
    };
    [key: string]: unknown;
}

async function getDownloadUrl(taskId: string): Promise<string> {
    const res = await apiClient.get<{ token: string }>(`/download_token/${taskId}`);
    const token = res.data?.token;
    if (!token) throw new Error('Missing download token');
    return `${API_URL}/download_file/${taskId}?token=${encodeURIComponent(token)}`;
}

export function useMobileQueue() {
    const [queue, setQueue] = useState<QueueItem[]>([]);
    const [isProcessing, setIsProcessing] = useState(false);
    const [currentIdx, setCurrentIdx] = useState(0);
    const processingRef = useRef(false);

    // Start processing only after React has applied the new queue state.
    useEffect(() => {
        if (!isProcessing) return;
        if (processingRef.current) return;
        if (queue.length === 0) return;
        startQueue();
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [isProcessing, queue.length]);

    const addToQueue = (items: { url: string; title: string }[]) => {
        // Prevent duplicate processing
        if (processingRef.current) return;

        const newItems: QueueItem[] = items.map(i => ({
            id: `temp_${Math.random().toString(36).substr(2, 9)}`,
            originalUrl: i.url,
            title: i.title,
            status: 'pending',
            progress: 0
        }));
        setQueue(newItems);
        setCurrentIdx(0);
        setIsProcessing(true); // Show overlay immediately
    };

    const startQueue = () => {
        if (processingRef.current) return;
        processingRef.current = true;
        processNext();
    };

    const processNext = async () => {
        setQueue(prev => {
            const idx = prev.findIndex(item => item.status === 'pending');
            // Check if ANY are still running? No, we run sequential.
            if (idx === -1) {
                // All done
                setTimeout(() => {
                    alert("Downloads Complete!");
                    setIsProcessing(false);
                    processingRef.current = false;
                    setQueue([]); // Clear queue? Or keep for review? keep safely clearing for now
                }, 2000);
                return prev;
            }

            // Found next item
            setCurrentIdx(idx);
            // Must execute processItem outside of reducer
            setTimeout(() => processItem(idx, prev[idx]), 0);
            return prev;
        });
    };

    const processItem = async (idx: number, item: QueueItem) => {
        try {
            // 1. Prepare
            updateStatus(idx, 'preparing', 10);

            // Artificial delay for UX
            await new Promise(r => setTimeout(r, 500));

            // Check if valid URL
            if (!item.originalUrl) throw new Error("Invalid URL");

            const prepRes = await apiClient.post<{ task_id: string }>(`/prepare`, {
                url: item.originalUrl,
                options: { format: 'mp3' }
            });
            const taskId = prepRes.data.task_id;

            // Update local ID
            // We need to use functional update to ensure we don't overwrite other state changes
            setQueue(prev => {
                const newQ = [...prev];
                newQ[idx] = { ...newQ[idx], id: taskId };
                return newQ;
            });

            // 2. Start Download
            updateStatus(idx, 'preparing', 30);
            await apiClient.post(`/start/${taskId}`);

            // 3. Poll
            updateStatus(idx, 'downloading', 50);

            let attempts = 0;
            const poll = setInterval(async () => {
                attempts++;
                if (attempts > 300) { // 5 minutes timeout
                    clearInterval(poll);
                    updateStatus(idx, 'error', 0);
                    processNext();
                    return;
                }

                try {
                    const res = await apiClient.get<BackendTask[]>(`/tasks`);
                    const task = res.data.find((t) => t.id === taskId);

                    if (task) {
                        updateStatus(idx, 'downloading', 50 + (task.progress || 0) / 2.5); // 50-90%

                        if (task.status === 'completed') {
                            clearInterval(poll);
                            // Safari/iOS blocks programmatic downloads not initiated by a user gesture.
                            // Mark as ready and require an explicit user tap to start the download.
                            // Also: browser downloads cannot attach custom headers, so we use a signed token.

                            let downloadUrl: string | undefined;
                            try {
                                downloadUrl = await getDownloadUrl(taskId);
                            } catch {
                                // We'll retry fetching a token on user tap.
                                downloadUrl = undefined;
                            }

                            setQueue(prev => {
                                const newQ = [...prev];
                                if (!newQ[idx]) return prev;
                                newQ[idx] = {
                                    ...newQ[idx],
                                    status: 'ready',
                                    progress: 100,
                                    downloadUrl
                                };
                                return newQ;
                            });
                        } else if (task.status === 'error') {
                            clearInterval(poll);
                            updateStatus(idx, 'error', 0);
                            setTimeout(processNext, 1000);
                        }
                    } else {
                        // Task lost?
                        // Keep polling...
                    }
                } catch {
                    // ignore poll error
                }
            }, 1000);

        } catch (e) {
            console.error(e);
            updateStatus(idx, 'error', 0);
            setTimeout(processNext, 1000);
        }
    };

    const updateStatus = (idx: number, status: QueueItem['status'], progress: number) => {
        setQueue(prev => {
            const newQ = [...prev];
            if (!newQ[idx]) return prev; // Safety
            newQ[idx] = { ...newQ[idx], status, progress };
            return newQ;
        });
    };

    const downloadCurrent = async () => {
        const idx = currentIdx;
        const item = queue[idx];
        if (!item || item.status !== 'ready') return;

        let url = item.downloadUrl;
        try {
            // Token may have expired; always fetch a fresh one.
            url = await getDownloadUrl(item.id);
        } catch (e) {
            console.error('Failed to fetch download token', e);
            return;
        }
        try {
            window.open(url, '_blank', 'noopener,noreferrer');
        } catch {
            // Last-resort fallback
            window.location.href = url;
        }

        // Move on (we can't reliably detect download completion in the browser)
        setQueue(prev => {
            const newQ = [...prev];
            if (!newQ[idx]) return prev;
            newQ[idx] = { ...newQ[idx], status: 'completed', progress: 100 };
            return newQ;
        });
        setTimeout(processNext, 500);
    };

    return {
        queue,
        isProcessing,
        addToQueue,
        currentIdx,
        downloadCurrent
    };
}
