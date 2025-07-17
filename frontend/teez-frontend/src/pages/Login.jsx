// src/pages/Login.jsx
import React from 'react';
import { Form, Input, Button, Typography, message } from 'antd';
import axios from 'axios'; // Оставляем для первоначального запроса логина
import { API_BASE_URL } from '../utils/config';
import axiosInstance from '../utils/axiosInstance'; // Используем для запросов после логина

// Импортируем JS-файлы, которые экспортируют корректные data-URL
import correctSound from '../assets/correctSound.js';
import incorrectSound from '../assets/incorrectSound.js';

const { Title } = Typography;

const Login = () => {
  const onFinish = (values) => {
    // Первоначальный запрос на логин используем через обычный axios,
    // так как accessToken еще не установлен.
    axios
      .post(`${API_BASE_URL}/api/login/`, values)
      .then((response) => {
        // Сохраняем токены
        localStorage.setItem('accessToken', response.data.access);
        localStorage.setItem('refreshToken', response.data.refresh);
        
        // Запрос для получения данных пользователя теперь через axiosInstance.
        // Заголовок Authorization будет добавлен автоматически перехватчиком.
        axiosInstance
          .get('/ft/user-info/') // Заголовок Authorization будет добавлен автоматически
          .then((res) => {
            localStorage.setItem('user', JSON.stringify(res.data));
            // Сохраняем корректные data-URL уведомлений из JS-файлов
            localStorage.setItem('correctSound', correctSound);
            localStorage.setItem('incorrectSound', incorrectSound);
            message.success('Успешный вход');
            window.location.href = "/"; // Перенаправление на главную страницу
          })
          .catch((err) => {
            // Очищаем токены в случае ошибки получения данных пользователя,
            // так как сессия может быть неполноценной.
            localStorage.removeItem('accessToken');
            localStorage.removeItem('refreshToken');
            message.error('Ошибка получения данных пользователя. Пожалуйста, попробуйте войти снова.');
            console.error('Ошибка получения данных пользователя:', err);
          });
      })
      .catch((error) => {
        let errorMessage = 'Ошибка входа.';
        if (error.response && error.response.data) {
          // Пытаемся извлечь сообщение об ошибке от сервера
          const serverError = error.response.data.detail || error.response.data.error || error.response.data.message;
          if (serverError) {
            errorMessage = serverError;
          }
        }
        message.error(errorMessage);
        console.error('Ошибка входа:', error.response || error);
      });
  };

  return (
    <div style={{ maxWidth: '400px', margin: '100px auto', padding: '20px', boxShadow: '0 4px 8px rgba(0,0,0,0.1)', borderRadius: '8px' }}>
      <Title level={2} style={{ textAlign: 'center', marginBottom: '24px' }}>Вход</Title>
      <Form 
        name="login" 
        onFinish={onFinish}
        layout="vertical"
      >
        <Form.Item
          label="Логин"
          name="username"
          rules={[{ required: true, message: 'Пожалуйста, введите ваш логин!' }]}
        >
          <Input placeholder="Введите логин" />
        </Form.Item>
        <Form.Item
          label="Пароль"
          name="password"
          rules={[{ required: true, message: 'Пожалуйста, введите ваш пароль!' }]}
        >
          <Input.Password placeholder="Введите пароль" />
        </Form.Item>
        <Form.Item style={{ marginBottom: 0 }}>
          <Button type="primary" htmlType="submit" block>
            Войти
          </Button>
        </Form.Item>
      </Form>
    </div>
  );
};

export default Login;