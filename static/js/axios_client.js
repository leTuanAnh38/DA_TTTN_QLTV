// ==========================================
// file: static/js/axios_client.js
// ==========================================

const csrfToken = document.querySelector('meta[name="csrf-token"]')?.getAttribute('content') || '';

const apiClient = axios.create({
    baseURL: window.location.origin,
    headers: {
        'Content-Type': 'application/json',
        'X-CSRFToken': csrfToken
    }
});

// Interceptor Request
apiClient.interceptors.request.use(
    (config) => {
        const token = localStorage.getItem('access_token');
        if (token) config.headers['Authorization'] = `Bearer ${token}`;
        return config;
    },
    (error) => Promise.reject(error)
);

// Interceptor Response
apiClient.interceptors.response.use(
    (response) => response,
    async (error) => {
        const originalRequest = error.config;
        if (error.response && error.response.status === 401 && !originalRequest._retry) {
            originalRequest._retry = true;
            try {
                const refreshToken = localStorage.getItem('refresh_token');
                const res = await axios.post('/api/token/refresh/', { refresh: refreshToken });
                localStorage.setItem('access_token', res.data.access);
                originalRequest.headers['Authorization'] = `Bearer ${res.data.access}`;
                return apiClient(originalRequest);
            } catch (err) {
                console.error("Token hết hạn!");
                window.location.href = '/login/'; 
            }
        }
        return Promise.reject(error);
    }
);

// Gán apiClient vào window để các file js khác có thể gọi được
window.apiClient = apiClient;