import React, { useState } from 'react';
import { Card, Button, Input, Space, Typography, message } from 'antd';
import { WebSocketManager } from '../utils/websocketUtils';
import { SessionStartRequest, SessionStopRequest } from '../types';

const { TextArea } = Input;
const { Text } = Typography;

interface TestPanelProps {
  wsManager: WebSocketManager;
}

const TestPanel: React.FC<TestPanelProps> = ({ wsManager }) => {
  const [isConnected, setIsConnected] = useState(false);
  const [receivedMessages, setReceivedMessages] = useState<string[]>([]);
  const [asrProvider, setAsrProvider] = useState('default');
  const [ttsProvider, setTtsProvider] = useState('default');

  const handleConnect = async () => {
    try {
      await wsManager.connect();
      setIsConnected(true);
      message.success('WebSocket连接成功');
    } catch (error) {
      message.error('WebSocket连接失败');
      console.error(error);
    }
  };

  const handleDisconnect = () => {
    wsManager.disconnect();
    setIsConnected(false);
    message.success('WebSocket已断开');
  };

  const handleStartSession = () => {
    const startRequest: SessionStartRequest = {
      directive: 'SessionStart',
      payload: {
        upstream: {},
        downstream: {},
        parameters: {
          asr_provider: asrProvider,
          tts_provider: ttsProvider
        }
      }
    };
    wsManager.sendMessage(startRequest);
    message.info('已发送SessionStart消息');
  };

  const handleStopSession = () => {
    const stopRequest: SessionStopRequest = {
      directive: 'SessionStop',
      payload: {}
    };
    wsManager.sendMessage(stopRequest);
    message.info('已发送SessionStop消息');
  };

  const handleMessage = (msg: any) => {
    console.log('TestPanel 收到WebSocket消息:', msg);
    setReceivedMessages(prev => [...prev, JSON.stringify(msg, null, 2)]);
  };

  React.useEffect(() => {
    wsManager.addMessageHandler(handleMessage);

    // 清理函数
    return () => {
      wsManager.removeMessageHandler(handleMessage);
    };
  }, [wsManager]);

  return (
    <Card title="WebSocket测试面板" style={{ marginTop: 16 }}>
      <Space direction="vertical" style={{ width: '100%' }}>
        <div>
          <Text>连接状态: </Text>
          <Text type={isConnected ? 'success' : 'danger'}>
            {isConnected ? '已连接' : '未连接'}
          </Text>
        </div>

        <Space>
          <Button
            type="primary"
            onClick={handleConnect}
            disabled={isConnected}
          >
            连接
          </Button>
          <Button
            onClick={handleDisconnect}
            disabled={!isConnected}
          >
            断开
          </Button>
        </Space>

        <div>
          <Text>ASR厂商: </Text>
          <Input
            value={asrProvider}
            onChange={(e) => setAsrProvider(e.target.value)}
            style={{ width: 150 }}
          />
        </div>

        <div>
          <Text>TTS厂商: </Text>
          <Input
            value={ttsProvider}
            onChange={(e) => setTtsProvider(e.target.value)}
            style={{ width: 150 }}
          />
        </div>

        <Space>
          <Button
            onClick={handleStartSession}
            disabled={!isConnected}
          >
            开启会话
          </Button>
          <Button
            onClick={handleStopSession}
            disabled={!isConnected}
          >
            关闭会话
          </Button>
        </Space>

        <div>
          <Text>接收到的消息:</Text>
          <TextArea
            value={receivedMessages.join('\n\n')}
            rows={10}
            readOnly
            style={{ marginTop: 8 }}
          />
        </div>
      </Space>
    </Card>
  );
};

export default TestPanel;