import React, { useState } from 'react';
import { Card, Button, Typography, Space } from 'antd';
import { AudioOutlined, AudioMutedOutlined } from '@ant-design/icons';
import { AudioManager } from '../utils/audioUtils';

const { Text } = Typography;

const AudioTest: React.FC = () => {
  const [isRecording, setIsRecording] = useState(false);
  const [audioStats, setAudioStats] = useState({
    totalPackets: 0,
    totalBytes: 0,
    lastPacketSize: 0
  });

  const audioManager = new AudioManager();

  const handleStartRecording = async () => {
    try {
      await audioManager.startRecordingRecorder((audioData: Int16Array) => {
        setAudioStats(prev => ({
          totalPackets: prev.totalPackets + 1,
          totalBytes: prev.totalBytes + audioData.buffer.byteLength,
          lastPacketSize: audioData.buffer.byteLength
        }));
      });
      setIsRecording(true);
    } catch (error) {
      console.error('启动音频录制失败:', error);
    }
  };

  const handleStopRecording = () => {
    audioManager.stopRecording();
    setIsRecording(false);
  };

  return (
    <Card title="音频采集测试" style={{ marginTop: 16 }}>
      <Space direction="vertical" style={{ width: '100%' }}>
        <div>
          <Text>录音状态: </Text>
          <Text type={isRecording ? 'success' : 'danger'}>
            {isRecording ? '正在录音' : '未录音'}
          </Text>
        </div>

        <Space>
          <Button
            type="primary"
            icon={isRecording ? <AudioMutedOutlined /> : <AudioOutlined />}
            onClick={isRecording ? handleStopRecording : handleStartRecording}
          >
            {isRecording ? '停止录音' : '开始录音'}
          </Button>
        </Space>

        {audioStats.totalPackets > 0 && (
          <div>
            <Text>音频统计:</Text>
            <div>总数据包: {audioStats.totalPackets}</div>
            <div>总字节数: {audioStats.totalBytes}</div>
            <div>最后数据包大小: {audioStats.lastPacketSize} 字节</div>
          </div>
        )}
      </Space>
    </Card>
  );
};

export default AudioTest;