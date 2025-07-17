import React, { useState, useEffect } from 'react';
import { Card, Alert, Avatar, Divider, Typography, Space, theme } from 'antd';
import { MailOutlined, PhoneOutlined, TeamOutlined, SendOutlined } from '@ant-design/icons';
import axios from 'axios';
import { API_BASE_URL } from '../../utils/config';

const { Meta } = Card;
const { Text, Link } = Typography;

const UserInfoCard = ({ userId }) => {
  const [userData, setUserData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  // --- 1. ПОЛУЧАЕМ ТОКЕНЫ ТЕКУЩЕЙ ТЕМЫ ---
  const { token } = theme.useToken();

  // Стили, которые будут адаптироваться под тему
  const textStyle = { color: token.colorText, fontSize: '14px' };
  const iconStyle = { color: token.colorTextSecondary, fontSize: '16px' };

  useEffect(() => {
    if (!userId) {
      setLoading(false);
      setError("ID пользователя не указан.");
      return;
    }

    const fetchUserData = async () => {
      setLoading(true);
      setError(null);
      setUserData(null);
      try {
        const response = await axios.get(`${API_BASE_URL}/public/userinfo/${userId}/`);
        setUserData(response.data);
      } catch (err) {
        console.error("Ошибка при загрузке данных пользователя:", err);
        setError("Не удалось загрузить информацию о пользователе.");
      } finally {
        setLoading(false);
      }
    };

    fetchUserData();
  }, [userId]);

  if (error) {
    return (
      <Card title="Ошибка" style={{ width: 300 }}>
        <Alert message={error} type="error" />
      </Card>
    );
  }

  return (
    <Card
      style={{ width: 300 }}
      loading={loading}
    >
      {/* Meta теперь содержит только аватара и имя */}
      <Meta
        avatar={
          <Avatar 
            size={50} 
            src={userData?.avatar} // Используем URL из API
          >
            {/* Если аватара нет, показываем первые буквы имени и фамилии */}
            {!userData?.avatar && `${userData?.first_name?.[0] || ''}${userData?.last_name?.[0] || ''}`}
          </Avatar>
        }
        title={userData ? `${userData.first_name || ''} ${userData.last_name || ''}`.trim() : 'Загрузка...'}
      />

      {/* --- 2. ДОБАВЛЕНЫ РАЗДЕЛИТЕЛИ И НОВЫЙ ДИЗАЙН --- */}
      {/* Этот блок рендерится только после загрузки */}
      {!loading && userData && (
        <>
          <Divider style={{ marginTop: 16, marginBottom: 16 }} />
          
          <Space direction="vertical" style={{ width: '100%' }} size="middle">
            <Space align="start">
              <TeamOutlined style={iconStyle} />
              <Text style={textStyle}><strong>Группы:</strong> {userData.groups?.join(', ') || 'Не указаны'}</Text>
            </Space>

            <Space>
              <PhoneOutlined style={iconStyle} />
              <Text style={textStyle}>{userData.phone_number || 'Номер не указан'}</Text>
            </Space>

            <Space>
              <MailOutlined style={iconStyle} />
              <Text style={textStyle}>{userData.email || 'Email не указан'}</Text>
            </Space>

            {userData.telegram_name && (
              <Space>
                <SendOutlined style={iconStyle} />
                <Link href={`https://t.me/${userData.telegram_name}`} target="_blank">
                  @{userData.telegram_name}
                </Link>
              </Space>
            )}
          </Space>
        </>
      )}
    </Card>
  );
};

export default UserInfoCard;