import React, { useState, useEffect, useRef } from 'react';
import { Layout, Input, Button, Typography, message, Spin } from 'antd';
import Sidebar from '../../components/Layout/Sidebar';
import JsBarcode from 'jsbarcode';
import axios from 'axios';
import { API_BASE_URL } from '../../utils/config';

const { Content } = Layout;
const { Title, Text } = Typography;

const defaultCorrectSound = 'data:audio/wav;base64,UklGRkIAAABXQVZFZm10IBAAAAABAAEARKwAAIhYAQACABAAZGF0YQAAAAA='; // Placeholder
const defaultIncorrectSound = 'data:audio/wav;base64,UklGRkIAAABXQVZFZm10IBAAAAABAAEARKwAAIhYAQACABAAZGF0YQAAAAA='; // Placeholder

const StockmanPrintBarcode = ({ darkMode, setDarkMode }) => {
  const [manualBarcode, setManualBarcode] = useState(''); // For barcode from manual input
  const [productInfo, setProductInfo] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const svgRef = useRef(null);
  const correctSoundRef = useRef(null);
  const incorrectSoundRef = useRef(null);

  useEffect(() => {
    document.title = 'Печать штрихкода';
    const storedCorrectSound = localStorage.getItem('correctSound') || defaultCorrectSound;
    const storedIncorrectSound = localStorage.getItem('incorrectSound') || defaultIncorrectSound;
    correctSoundRef.current = new Audio(storedCorrectSound);
    incorrectSoundRef.current = new Audio(storedIncorrectSound);
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

  const handleManualBarcodeChange = (e) => {
    const value = e.target.value;
    // Allow only digits and limit to 13 characters
    if (/^\d*$/.test(value) && value.length <= 13) {
      setManualBarcode(value);
      // Clear previous product info and error if barcode is being changed
      if (value.length < 13) {
        setProductInfo(null);
        setError('');
      }
    }
  };

  // Fetch product info when manualBarcode reaches 13 chars
  useEffect(() => {
    const fetchProductInfo = async () => {
      // Ensure loading is false before new request
      if (loading) return;

      setLoading(true);
      setError('');
      setProductInfo(null); 
      const loadingMessage = message.loading('Загрузка информации о товаре...', 0);

      try {
        const token = localStorage.getItem('accessToken');
        const response = await axios.get(
          `${API_BASE_URL}/st/BarcodePrint/${manualBarcode}/`,
          { headers: { Authorization: `Bearer ${token}` } }
        );
        setProductInfo(response.data);
        playCorrectSound();
        message.success('Информация о товаре получена!');
      } catch (err) {
        const errMsg = err.response?.data?.error || 'Ошибка получения информации о товаре';
        message.error(errMsg);
        setError(errMsg);
        playIncorrectSound();
        setProductInfo(null);
      } finally {
        setLoading(false);
        loadingMessage();
      }
    };

    if (manualBarcode.length === 13) {
      fetchProductInfo();
    }
  }, [manualBarcode]); // Dependency on manualBarcode

  // Generate JsBarcode when productInfo is available
  useEffect(() => {
    if (productInfo && productInfo.Barcode && productInfo.Barcode.length === 13 && svgRef.current) {
      try {
        JsBarcode(svgRef.current, productInfo.Barcode, {
          format: 'ean13',
          width: 2,
          height: 60,
          displayValue: true,
          fontSize: 14,
        });
      } catch (err) {
        console.error('Ошибка генерации штрихкода:', err);
        message.error('Не удалось сгенерировать изображение штрихкода.');
      }
    }
  }, [productInfo]);

  const handlePrint = () => {
    if (!productInfo || !productInfo.Barcode || productInfo.Barcode.length !== 13) {
      message.error('Нет данных о штрихкоде для печати или штрихкод невалиден.');
      playIncorrectSound();
      return;
    }
    const printWindow = window.open('', '_blank', 'width=400,height=400');
    if (!printWindow) {
        message.error('Не удалось открыть окно печати. Проверьте настройки блокировщика всплывающих окон.');
        return;
    }

    const svgMarkup = svgRef.current ? svgRef.current.outerHTML : '<p>Ошибка генерации штрихкода</p>';

    printWindow.document.write(`
      <html>
      <head>
        <title>Печать штрихкода: ${productInfo.Barcode}</title>
        <style>
          @page { margin: 0; }
          body {
            margin: 0; display: flex; align-items: center; justify-content: center;
            font-family: sans-serif;
          }
          .print-container {
            text-align: center;
          }
          .barcode-container {
            width: 41mm; height: 25mm; display: flex;
            align-items: center; justify-content: center; margin: 5px auto;
          }
          svg { max-width: 100%; max-height: 100%; }
        </style>
      </head>
      <body>
        <div class="print-container">
          <div class="barcode-container">${svgMarkup}</div>
        </div>
        <script>
          window.onafterprint = function() { setTimeout(function() { window.close(); }, 100); };
          window.focus(); window.print();
        </script>
      </body>
      </html>
    `);
    printWindow.document.close();
  };

  return (
    <Layout>
      <Sidebar darkMode={darkMode} setDarkMode={setDarkMode} />
      <Content
        style={{
          padding: 24,
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          minHeight: '100vh',
          background: darkMode ? '#1f1f1f' : '#f0f2f5',
        }}
      >
        <Title level={2} style={{ color: darkMode ? '#fff' : 'rgba(0, 0, 0, 0.85)', marginBottom: 30 }}>
            Печать штрихкода
        </Title>
        
        <Input
          placeholder="Введите штрихкод (13 цифр)"
          value={manualBarcode}
          onChange={handleManualBarcodeChange}
          maxLength={13} // HTML5 attribute for max length
          style={{ 
            width: 350, 
            textAlign: 'center', 
            marginBottom: 20,
            fontSize: '16px',
            borderColor: error ? 'red' : undefined
          }}
        />

        {loading && manualBarcode.length === 13 && <Spin tip="Загрузка..." style={{ marginBottom: 20 }} />}

        {error && !loading && (
          <Text type="danger" style={{ marginBottom: 20, fontSize: '16px' }}>
            {error}
          </Text>
        )}

        {productInfo && !loading && (
          <div style={{ textAlign: 'center', marginBottom: 30, padding: 15, border: '1px solid #d9d9d9', borderRadius: '8px', background: darkMode ? '#2c2c2c' : '#fff' }}>
            <Title level={4} style={{ color: darkMode ? '#eee' : 'rgba(0,0,0,0.8)'}}>Информация о товаре:</Title>
            <Text strong style={{ fontSize: '16px', display: 'block', color: darkMode ? '#ccc' : 'rgba(0,0,0,0.7)' }}>
              Штрихкод: {productInfo.Barcode}
            </Text>
            <Text strong style={{ fontSize: '16px', display: 'block', color: darkMode ? '#ccc' : 'rgba(0,0,0,0.7)' }}>
              Наименование: {productInfo.name}
            </Text>
            <Text strong style={{ fontSize: '16px', display: 'block', color: darkMode ? '#ccc' : 'rgba(0,0,0,0.7)' }}>
              Статус: {productInfo.move_status}
            </Text>
            
            <div
              style={{
                width: '82mm',
                minHeight: '50mm',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                margin: '20px auto',
                border: darkMode ? '1px solid #444' : '1px solid #ccc',
                background: '#fff', 
                padding: '10px'
              }}
            >
              <svg ref={svgRef} />
            </div>

            <Button 
                type="primary" 
                onClick={handlePrint} 
                disabled={loading || !productInfo} // Button is disabled if still loading or no product info
                size="large"
            >
              Печать
            </Button>
          </div>
        )}
      </Content>
    </Layout>
  );
};

export default StockmanPrintBarcode;