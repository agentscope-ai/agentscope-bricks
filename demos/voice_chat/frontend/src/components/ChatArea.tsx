import React from 'react';
import { Card, Button, Typography } from 'antd';
import { AudioOutlined, AudioMutedOutlined } from '@ant-design/icons';
import { SessionStatus } from '../types';

const { Text } = Typography;

interface ChatAreaProps {
  status: SessionStatus;
  onToggleSession: () => void;
}

const ChatArea: React.FC<ChatAreaProps> = ({
  status,
  onToggleSession
}) => {
  const getStatusText = () => {
    switch (status) {
      case 'idle':
        return '点击麦克风开始对话';
      case 'connecting':
        return '正在连接...';
      case 'connected':
        return '正在输入语音...';
      case 'disconnecting':
        return '正在断开连接...';
      case 'error':
        return '连接出错，请重试';
      default:
        return '未知状态';
    }
  };

  const isRecording = status === 'connected';
  const isConnecting = status === 'connecting' || status === 'disconnecting';

  return (
    <Card title="对话框" style={{ height: '100%', display: 'flex', flexDirection: 'column' }}>
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center' }}>
        {/* 头像区域 */}
        <div style={{ marginBottom: '1.5rem' }}>
          <div
            style={{
              width: 'min(200px, 15vw)',
              height: 'min(200px, 15vw)',
              borderRadius: '50%',
              backgroundColor: '#f0f0f0',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              border: '3px solid #1890ff',
              overflow: 'hidden',
              backgroundImage: 'url(/images/avatar.jpg)',
              backgroundSize: 'cover',
              backgroundPosition: 'center',
              backgroundRepeat: 'no-repeat'
            }}
          />
        </div>

        {/* 状态+麦克风整体下移 */}
        <div style={{ marginTop: '20vh', display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
          <div style={{ marginBottom: '2rem', textAlign: 'center' }}>
            <Text type="secondary" style={{ fontSize: '1rem' }}>
              {getStatusText()}
            </Text>
          </div>
          <div>
            <Button
              type="primary"
              shape="circle"
              size="large"
              icon={isRecording ? <AudioMutedOutlined /> : <AudioOutlined />}
              onClick={onToggleSession}
              loading={isConnecting}
              disabled={isConnecting}
              style={{
                width: 'min(80px, 6vw)',
                height: 'min(80px, 6vw)',
                fontSize: 'min(24px, 2vw)',
                backgroundColor: isRecording ? '#ff4d4f' : '#1890ff',
                borderColor: isRecording ? '#ff4d4f' : '#1890ff',
              }}
            />
          </div>
        </div>
      </div>
    </Card>
  );
};

export default ChatArea;