import React, { useState, useEffect, useRef } from 'react';
import { Layout, Input, Button, message, Typography, Modal } from 'antd';
import Sidebar from '../../components/Layout/Sidebar'; // Убедитесь, что путь к Sidebar корректен
import axios from 'axios';
import { API_BASE_URL } from '../../utils/config'; // Убедитесь, что путь к API_BASE_URL корректен

const { Content } = Layout;
const { Title } = Typography;

// ЗАМЕНИТЕ ЭТИ СТРОКИ НА РЕАЛЬНЫЕ BASE64 ЗВУКИ ИЗ ВАШЕГО ПРОЕКТА
const defaultCorrectSound = 'data:audio/wav;base64,UklGRk...'; // Пример: короткий позитивный звук
const defaultIncorrectSound = 'data:audio/wav;base64,UklGRl...'; // Пример: короткий негативный звук

const ProcessNoPhotoPage = ({ darkMode, setDarkMode }) => {
  const [barcode, setBarcode] = useState('');
  const [loading, setLoading] = useState(false);
  const [isModalVisible, setIsModalVisible] = useState(false);

  const correctSoundRef = useRef(null);
  const incorrectSoundRef = useRef(null);

  useEffect(() => {
    // Инициализация аудио-объектов (берём из localStorage, если есть, иначе дефолтные)
    const storedCorrectSound = localStorage.getItem('correctSound') || defaultCorrectSound;
    const storedIncorrectSound = localStorage.getItem('incorrectSound') || defaultIncorrectSound;
    
    correctSoundRef.current = new Audio(storedCorrectSound);
    incorrectSoundRef.current = new Audio(storedIncorrectSound);
    
    document.title = "Пометка 'Без фото'";
  }, []);

  const playCorrectSound = () => {
    if (correctSoundRef.current) {
      correctSoundRef.current.pause();
      correctSoundRef.current.currentTime = 0;
      correctSoundRef.current.play().catch(err => console.error('Ошибка воспроизведения correctSound:', err));
    }
  };

  const playIncorrectSound = () => {
    if (incorrectSoundRef.current) {
      incorrectSoundRef.current.pause();
      incorrectSoundRef.current.currentTime = 0;
      incorrectSoundRef.current.play().catch(err => console.error('Ошибка воспроизведения incorrectSound:', err));
    }
  };

  useEffect(() => {
    let inputBuffer = '';
    let lastKeyTime = 0;

    const handleKeyDown = (e) => {
      if (loading) { // Если идет запрос, не обрабатываем новые штрихкоды
        e.preventDefault();
        return;
      }

      // Игнорируем ввод, если фокус на каком-либо поле ввода (кроме случаев, когда это наш компонент)
      const activeElement = document.activeElement;
      if (activeElement && activeElement.tagName !== 'BODY' && 
          (activeElement.tagName === 'INPUT' || activeElement.tagName === 'TEXTAREA')) {
          // Если на странице есть другие поля ввода, и фокус на них, то не обрабатываем "глобальное" сканирование
          // Это предотвращает перехват, если пользователь печатает, например, в поиске сайдбара
          return; 
      }

      const now = Date.now();
      if (now - lastKeyTime > 100) { // Интервал между символами (для сканера обычно маленький)
        inputBuffer = ''; // Сбрасываем буфер, если пауза слишком большая (начало нового ввода)
      }
      lastKeyTime = now;

      if (/^[0-9]$/.test(e.key)) {
        inputBuffer += e.key;
      } else if (e.key === 'Enter') {
        e.preventDefault(); // Предотвращаем стандартное поведение Enter
        if (inputBuffer.length === 13) { // Предполагаем стандартную длину EAN-13
          setBarcode(inputBuffer);
          setIsModalVisible(true);
        } else if (inputBuffer.length > 0) { // Если что-то введено, но неверной длины
          message.error('Неверная длина штрихкода. Ожидается 13 цифр.');
          playIncorrectSound();
        }
        inputBuffer = ''; // Очищаем буфер
      } else {
        // Если это не цифра и не Enter, это может быть случайный символ или конец ввода без Enter
        // Для большинства сканеров Enter является суффиксом. Если нет, эту логику нужно адаптировать.
        // Если приходят не цифровые символы, буфер лучше сбросить, чтобы избежать "123abc456"
        if (e.key.length === 1 && !e.ctrlKey && !e.altKey && !e.metaKey) {
             inputBuffer = '';
        }
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => {
      window.removeEventListener('keydown', handleKeyDown);
    };
  }, [loading]); // Пересоздаем обработчик, если loading изменился

  const handleProcessNoPhoto = async () => {
    if (!barcode) return;

    setLoading(true);
    const token = localStorage.getItem('accessToken');

    if (!token) {
      message.error('Ошибка аутентификации: токен не найден.');
      playIncorrectSound();
      setLoading(false);
      setIsModalVisible(false);
      setBarcode('');
      return;
    }

    try {
      const response = await axios.post(
        `${API_BASE_URL}/ph/st-requests/product/${barcode}/nofoto/`,
        {}, // Тело запроса пустое, так как штрихкод передается в URL
        {
          headers: {
            Authorization: `Bearer ${token}`,
          },
        }
      );
      message.success(response.data.message || `Товар ${barcode} успешно помечен как 'Без фото'.`);
      playCorrectSound();
    } catch (error) {
      const errMsg = error.response?.data?.error || error.response?.data?.message || `Не удалось обработать товар ${barcode}.`;
      message.error(errMsg);
      playIncorrectSound();
    } finally {
      setLoading(false);
      setIsModalVisible(false);
      setBarcode(''); // Очищаем штрихкод для следующего сканирования
    }
  };

  const handleModalCancel = () => {
    setIsModalVisible(false);
    setBarcode(''); // Очищаем штрихкод, если пользователь отменил действие
  };

  return (
    <Layout style={{ minHeight: '100vh' }}>
      <Sidebar darkMode={darkMode} setDarkMode={setDarkMode} />
      <Layout>
        <Content
          style={{
            padding: 24,
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            justifyContent: 'center',
            // backgroundColor: darkMode ? '#141414' : '#fff', // Пример фона контента
          }}
        >
          <Title level={2} style={{ marginBottom: 30, color: darkMode ? 'white' : 'black' }}>
            Пометка товара "Без фото"
          </Title>
          <Input
            placeholder="Ожидание сканирования штрихкода..."
            value={barcode}
            disabled // Нередактируемое поле
            style={{
              width: 350,
              textAlign: 'center',
              fontSize: '1.3em',
              padding: '10px',
              marginBottom: 20,
              // Стили для Input в зависимости от темы можно добавить здесь или через CSS классы
              backgroundColor: darkMode ? '#262626' : '#f5f5f5',
              color: darkMode ? '#e8e8e8' : 'black',
              borderColor: darkMode ? '#434343' : '#d9d9d9',
            }}
          />
          {/* Кнопка для ручного вызова не нужна, так как все через сканер и модальное окно */}
        </Content>
      </Layout>

      <Modal
        title="Подтверждение действия"
        visible={isModalVisible}
        onOk={handleProcessNoPhoto}
        onCancel={handleModalCancel}
        confirmLoading={loading}
        okText="Да, поставить 'Без фото'"
        cancelText="Нет"
        destroyOnClose // Очищает Modal при закрытии
        centered // Центрирует модальное окно
      >
        <p style={{ fontSize: '1.1em' }}>
          Действительно пометить товар со штрихкодом <strong style={{ color: '#1890ff' }}>{barcode}</strong> как "Без фото"?
        </p>
      </Modal>
    </Layout>
  );
};

export default ProcessNoPhotoPage;