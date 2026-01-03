export const isMobile = (): boolean => {
    if (typeof window === 'undefined') return false;
    return /Android|webOS|iPhone|iPad|iPod|BlackBerry|IEMobile|Opera Mini/i.test(navigator.userAgent);
};

export const isIOS = (): boolean => {
    if (typeof window === 'undefined') return false;
    return /iPhone|iPad|iPod/i.test(navigator.userAgent);
};

export const getDeviceId = () => {
    let id = localStorage.getItem('aura_device_id');
    if (!id) {
        id = crypto.randomUUID();
        localStorage.setItem('aura_device_id', id);
    }
    return id;
};
