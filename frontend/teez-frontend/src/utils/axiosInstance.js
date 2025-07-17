// src/utils/axiosInstance.js
import axios from 'axios';
import dayjs from 'dayjs';
import { jwtDecode } from 'jwt-decode'; // Убедитесь, что jwt-decode установлен и импортируется так
import { API_BASE_URL } from './config'; // Путь к вашему файлу конфигурации

// Создаем экземпляр axios БЕЗ глобального Authorization header здесь.
// Он будет добавляться динамически в request interceptor.
const axiosInstance = axios.create({
  baseURL: API_BASE_URL,
});

let isRefreshing = false;
let failedQueue = [];

const processQueue = (error, token = null) => {
  failedQueue.forEach(prom => {
    if (error) {
      prom.reject(error);
    } else {
      prom.resolve(token);
    }
  });
  failedQueue = [];
};

const handleRefreshToken = async () => {
  const currentRefreshToken = localStorage.getItem('refreshToken');
  if (!currentRefreshToken) {
    // Нет refresh token, не можем обновить, очищаем все и выходим
    console.log('No refresh token available for refresh.');
    localStorage.removeItem('accessToken');
    localStorage.removeItem('refreshToken');
    localStorage.removeItem('user'); // Также очищаем данные пользователя
    window.location.href = '/login'; // Перенаправляем на страницу логина
    return Promise.reject(new Error('No refresh token'));
  }

  try {
    // Используем новый экземпляр axios для запроса на обновление, чтобы избежать цикла интерсепторов
    const response = await axios.post(`${API_BASE_URL}/api/token/refresh/`, {
      refresh: currentRefreshToken,
    });

    const newAccessToken = response.data.access;
    const newRefreshToken = response.data.refresh; // Django Simple JWT может вернуть новый refresh token

    localStorage.setItem('accessToken', newAccessToken);
    if (newRefreshToken) { // Если сервер вернул новый refresh token
        localStorage.setItem('refreshToken', newRefreshToken);
    }
    
    // Устанавливаем новый токен как заголовок по умолчанию для будущих запросов через этот axiosInstance
    // Это полезно, если вы где-то используете axiosInstance.defaults
    axiosInstance.defaults.headers.common['Authorization'] = `Bearer ${newAccessToken}`;

    return newAccessToken;
  } catch (err) {
    console.error('Error refreshing token:', err);
    // Если refresh token тоже истек или невалиден
    localStorage.removeItem('accessToken');
    localStorage.removeItem('refreshToken');
    localStorage.removeItem('user');
    window.location.href = '/login'; // Перенаправляем на страницу логина
    return Promise.reject(err);
  }
};

axiosInstance.interceptors.request.use(
  async (config) => {
    let accessToken = localStorage.getItem('accessToken');
    const refreshToken = localStorage.getItem('refreshToken'); // Получаем refreshToken для проверки возможности обновления

    if (accessToken) {
      try {
        const decodedToken = jwtDecode(accessToken);
        // Проверяем, истекает ли токен в ближайшие 5 минут (300 секунд) или уже истек
        const isExpired = dayjs.unix(decodedToken.exp).diff(dayjs(), 'second') < 300;

        if (isExpired && refreshToken) { // Если токен истек/истекает И есть refreshToken
          if (!isRefreshing) {
            isRefreshing = true;
            try {
              const newAccessToken = await handleRefreshToken();
              accessToken = newAccessToken; // Используем новый токен для текущего запроса
              config.headers['Authorization'] = `Bearer ${newAccessToken}`;
              processQueue(null, newAccessToken);
            } catch (error) {
              processQueue(error, null);
              // Если handleRefreshToken выбросил ошибку (и уже сделал редирект),
              // здесь мы просто прерываем текущий запрос.
              return Promise.reject(error);
            } finally {
              isRefreshing = false;
            }
          } else {
            // Если уже идет процесс обновления, добавляем запрос в очередь
            return new Promise((resolve, reject) => {
              failedQueue.push({ resolve, reject });
            })
            .then(tokenFromQueue => { // tokenFromQueue это newAccessToken из успешного handleRefreshToken
              config.headers['Authorization'] = `Bearer ${tokenFromQueue}`;
              return config;
            })
            .catch(err => {
              return Promise.reject(err); // Ошибка из processQueue если handleRefreshToken не удался
            });
          }
        } else if (!isExpired) {
            // Токен действителен и не требует обновления
            config.headers['Authorization'] = `Bearer ${accessToken}`;
        } else if (isExpired && !refreshToken) {
            // Токен истек, но нет refresh token для обновления
            console.log('Access token expired, no refresh token available.');
            localStorage.removeItem('accessToken');
            localStorage.removeItem('user');
            window.location.href = '/login';
            return Promise.reject(new Error('Access token expired, no refresh token.'));
        }
      } catch (e) {
        // Ошибка декодирования (например, токен невалидный или отсутствует)
        console.error('Invalid token or error decoding token:', e);
        localStorage.removeItem('accessToken');
        localStorage.removeItem('refreshToken');
        localStorage.removeItem('user');
        window.location.href = '/login';
        return Promise.reject(new Error('Invalid token'));
      }
    }
    // Если accessToken отсутствует, заголовок Authorization не будет добавлен (для публичных эндпоинтов)
    return config;
  },
  (error) => {
    return Promise.reject(error);
  }
);

axiosInstance.interceptors.response.use(
  (response) => {
    return response;
  },
  async (error) => {
    const originalRequest = error.config;

    // Проверяем, что ошибка 401 и это не повторный запрос после обновления токена
    // Также проверяем, что это не ошибка от самого эндпоинта обновления токена
    if (error.response && error.response.status === 401 && originalRequest.url !== `${API_BASE_URL}/api/token/refresh/` && !originalRequest._retry) {
      originalRequest._retry = true; // Помечаем запрос как повторный

      if (!isRefreshing) {
        isRefreshing = true;
        try {
          const newAccessToken = await handleRefreshToken();
          // Обновляем хедер для оригинального запроса
          originalRequest.headers['Authorization'] = `Bearer ${newAccessToken}`;
          processQueue(null, newAccessToken);
          return axiosInstance(originalRequest); // Повторяем оригинальный запрос
        } catch (refreshError) {
          processQueue(refreshError, null);
          // handleRefreshToken уже должен был сделать редирект, если это необходимо
          return Promise.reject(refreshError);
        } finally {
          isRefreshing = false;
        }
      } else {
        // Если уже идет процесс обновления, добавляем запрос в очередь
        return new Promise((resolve, reject) => {
          failedQueue.push({ resolve, reject });
        })
        .then(tokenFromQueue => {
          originalRequest.headers['Authorization'] = `Bearer ${tokenFromQueue}`;
          return axiosInstance(originalRequest);
        })
        .catch(err => {
          return Promise.reject(err);
        });
      }
    }
    return Promise.reject(error);
  }
);

export default axiosInstance;