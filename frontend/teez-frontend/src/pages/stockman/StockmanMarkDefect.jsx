import React, { useState, useEffect, useRef } from 'react';
import { Layout, Input, Button, Radio, message, Typography } from 'antd';
import Sidebar from '../../components/Layout/Sidebar';
import axios from 'axios';
import { API_BASE_URL } from '../../utils/config';

const { Content } = Layout;
const { Title } = Typography;

// Значения по умолчанию для звуков, если в localStorage их нет
const defaultCorrectSound = 'data:audio/wav;base64,...';
const defaultIncorrectSound = 'data:audio/wav;base64,...';

const StockmanMarkDefect = ({ darkMode, setDarkMode }) => {
  // Состояния для штрихкода, комментария и выбранного типа (Брак / Вскрыто)
  const [barcode, setBarcode] = useState('');
  const [comment, setComment] = useState('');
  const [defectType, setDefectType] = useState('defect'); // 'defect' = Брак, 'opened' = Вскрыто

  // Рефы для звуков
  const correctSoundRef = useRef(null);
  const incorrectSoundRef = useRef(null);
  // Реф для кнопки "Отметить", чтобы убрать фокус
  const markButtonRef = useRef(null);

  // Инициализация аудио-объектов (берём из localStorage, если есть)
  useEffect(() => {
    const storedCorrectSound = localStorage.getItem('correctSound') || defaultCorrectSound;
    const storedIncorrectSound = localStorage.getItem('incorrectSound') || defaultIncorrectSound;
    correctSoundRef.current = new Audio(storedCorrectSound);
    incorrectSoundRef.current = new Audio(storedIncorrectSound);
    document.title = 'Пометить брак/вскрыто';
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

  // Локальный буфер для сканирования штрихкода
  useEffect(() => {
    let inputBuffer = '';
    let lastKeyTime = 0;

    const handleKeyDown = (e) => {
      const now = Date.now();
      if (now - lastKeyTime > 1000) {
        inputBuffer = '';
      }
      lastKeyTime = now;

      if (/^[0-9]$/.test(e.key)) {
        inputBuffer += e.key;
      } else if (e.key === 'Enter') {
        if (inputBuffer.length === 13) {
          setBarcode(inputBuffer);
        } else {
          message.error('Неверная длина штрихкода');
          playIncorrectSound();
        }
        inputBuffer = '';
      } else {
        inputBuffer = '';
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, []);

  // Обработчик изменения радиогруппы
  const handleRadioChange = (e) => {
    setDefectType(e.target.value);
    // Если выбрано "Вскрыто", комментарий не редактируется — очищаем его
    if (e.target.value === 'opened') {
      setComment('');
    }
  };

  // Обработчик нажатия на кнопку "Отметить"
  const handleMark = async () => {
    // Убираем фокус с кнопки, чтобы Enter не срабатывал повторно на ней
    if (markButtonRef.current) {
      markButtonRef.current.blur();
    }
    if (!barcode) {
      message.error('Просканируйте штрихкод');
      playIncorrectSound();
      return;
    }
    const token = localStorage.getItem('accessToken');
    if (defectType === 'defect') {
      // Если выбран "Брак", комментарий обязателен
      if (!comment.trim()) {
        message.error('Комментарий обязателен для пометки брака');
        playIncorrectSound();
        return;
      }
      try {
        await axios.post(
          `${API_BASE_URL}/st/product-mark-defect/${barcode}/`,
          { comment },
          { headers: { Authorization: `Bearer ${token}` } }
        );
        message.success('Продукт помечен как брак');
        playCorrectSound();
        setBarcode('');
        setComment('');
      } catch (error) {
        const errMsg = error.response?.data?.error || 'Ошибка отметки брака';
        message.error(errMsg);
        playIncorrectSound();
      }
    } else if (defectType === 'opened') {
      try {
        await axios.post(
          `${API_BASE_URL}/st/product-mark-opened/${barcode}/`,
          { comment }, // если комментарий пустой, сервер установит "вскрыто"
          { headers: { Authorization: `Bearer ${token}` } }
        );
        message.success('Продукт помечен как вскрыто');
        playCorrectSound();
        setBarcode('');
        setComment('');
      } catch (error) {
        const errMsg = error.response?.data?.error || 'Ошибка отметки вскрыто';
        message.error(errMsg);
        playIncorrectSound();
      }
    }
  };

  return (
    <Layout>
      <Sidebar darkMode={darkMode} setDarkMode={setDarkMode} />
      <Content style={{ 
        padding: 16, 
        display: 'flex', 
        flexDirection: 'column', 
        alignItems: 'center', 
        justifyContent: 'center', 
        minHeight: '100vh' 
      }}>
        <Title level={2}>Пометить брак/вскрыто</Title>
        {/* Нередактируемое поле для штрихкода */}
        <Input 
          placeholder="Штрихкод" 
          value={barcode} 
          disabled 
          style={{ width: 300, textAlign: 'center', marginBottom: 20 }} 
        />
        {/* Радиогруппа для выбора типа */}
        <Radio.Group 
          onChange={handleRadioChange} 
          value={defectType} 
          style={{ marginBottom: 20 }}
        >
          <Radio value="defect">Брак</Radio>
          <Radio value="opened">Вскрыто</Radio>
        </Radio.Group>
        {/* Текстовое поле для комментария (редактируется только при выборе "Брак") */}
        <Input.TextArea 
          placeholder="Комментарий" 
          value={comment} 
          onChange={(e) => setComment(e.target.value)} 
          disabled={defectType !== 'defect'} 
          style={{ width: 300, marginBottom: 20 }} 
        />
        <Button type="primary" onClick={handleMark} ref={markButtonRef}>
          Отметить
        </Button>
      </Content>
    </Layout>
  );
};

export default StockmanMarkDefect;
