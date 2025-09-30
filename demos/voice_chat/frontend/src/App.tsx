import React, { useState, useCallback, useRef, useEffect } from 'react';
import { Layout, message } from 'antd';
import ConfigPanel from './components/ConfigPanel';
import ChatArea from './components/ChatArea';
import ChatHistory from './components/ChatHistory';
// 测试面板已移除，保持UI简洁
import { WebSocketManager } from './utils/websocketUtils';
import { AudioManager } from './utils/audioUtils';
import {
  SessionConfig,
  SessionStatus,
  ChatMessage,
  WebSocketMessage,
  SessionStartRequest,
  SessionStopRequest
} from './types';

const { Sider, Content } = Layout;

const App: React.FC = () => {
  const [sessionStatus, setSessionStatus] = useState<SessionStatus>('idle');
  const [sessionConfig, setSessionConfig] = useState<SessionConfig>({
    asrProvider: 'modelstudio',
    asrLanguage: 'zh-CN',
    enableTool: false,
    ttsProvider: 'modelstudio',
    ttsVoice: 'longcheng_v2'
  });
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [currentUserMessage, setCurrentUserMessage] = useState<string>('');
  const [currentAssistantMessage, setCurrentAssistantMessage] = useState<string>('');
  const [currentUserTimestamp, setCurrentUserTimestamp] = useState<string>('');
  const [currentAssistantTimestamp, setCurrentAssistantTimestamp] = useState<string>('');
  const [currentToolCalls, setCurrentToolCalls] = useState<ChatMessage['tool_calls']>(undefined);
  const [accumulatedToolArgsByIndex, setAccumulatedToolArgsByIndex] = useState<Record<number, string>>({});
  const [accumulatedToolNameByIndex, setAccumulatedToolNameByIndex] = useState<Record<number, string>>({});
  const [accumulatedToolIdByIndex, setAccumulatedToolIdByIndex] = useState<Record<number, string>>({});
  const [accumulatedToolIndexByIndex, setAccumulatedToolIndexByIndex] = useState<Record<number, number>>({});

  // 检测页面刷新并清除对话记录
  useEffect(() => {
    // 检查是否是页面刷新
    const isPageRefresh = performance.navigation.type === 1 ||
                         (window.performance && window.performance.getEntriesByType &&
                          window.performance.getEntriesByType('navigation').length > 0 &&
                          (window.performance.getEntriesByType('navigation')[0] as PerformanceNavigationTiming).type === 'reload');

    // 检查页面可见性变化（页面刷新时会触发）
    const handleVisibilityChange = () => {
      if (document.visibilityState === 'visible') {
        // 页面重新变为可见时，清除对话记录
        setMessages([]);
        setCurrentUserMessage('');
        setCurrentAssistantMessage('');
        setCurrentUserTimestamp('');
        setCurrentAssistantTimestamp('');
        setCurrentToolCalls(undefined);
        setAccumulatedToolArgsByIndex({});
        setAccumulatedToolNameByIndex({});
        setAccumulatedToolIdByIndex({});
        setAccumulatedToolIndexByIndex({});
        console.log('🔄 页面刷新检测：已清除对话记录');
      }
    };

    // 监听页面可见性变化
    document.addEventListener('visibilitychange', handleVisibilityChange);

          // 如果是页面刷新，立即清除对话记录
      if (isPageRefresh) {
        setMessages([]);
        setCurrentUserMessage('');
        setCurrentAssistantMessage('');
        setCurrentUserTimestamp('');
        setCurrentAssistantTimestamp('');
        setCurrentToolCalls(undefined);
        setAccumulatedToolArgsByIndex({});
        setAccumulatedToolNameByIndex({});
        setAccumulatedToolIdByIndex({});
        setAccumulatedToolIndexByIndex({});
        console.log('🔄 页面刷新检测：已清除对话记录');
      }

    // 使用 sessionStorage 来检测页面刷新
    const isRefreshed = sessionStorage.getItem('pageRefreshed');
    if (!isRefreshed) {
      // 第一次加载，设置标记
      sessionStorage.setItem('pageRefreshed', 'true');
    } else {
      // 页面刷新，清除对话记录
      setMessages([]);
      setCurrentUserMessage('');
      setCurrentAssistantMessage('');
      setCurrentUserTimestamp('');
      setCurrentAssistantTimestamp('');
      setCurrentToolCalls(undefined);
      setAccumulatedToolArgsByIndex({});
      setAccumulatedToolNameByIndex({});
      setAccumulatedToolIdByIndex({});
      setAccumulatedToolIndexByIndex({});
      console.log('🔄 页面刷新检测：已清除对话记录');
    }

    return () => {
      document.removeEventListener('visibilitychange', handleVisibilityChange);
    };
  }, []);

  // 工具类实例
  const wsManagerRef = useRef<WebSocketManager>();
  if (!wsManagerRef.current) {
    wsManagerRef.current = new WebSocketManager('ws://127.0.0.1:8000/api');
  }
  const wsManager = wsManagerRef.current;

  const audioManagerRef = useRef<AudioManager>();
  if (!audioManagerRef.current) {
    audioManagerRef.current = new AudioManager(16000); // 强制采样率
  }
  const audioManager = audioManagerRef.current;

  // 设置AudioManager到WebSocketManager，用于播放音频
  wsManager.setAudioManager(audioManager);

  // 音频采集缓冲区（已不再使用，保留用于兼容性）
  // eslint-disable-next-line @typescript-eslint/no-unused-vars
  const audioBufferRef = useRef<Int16Array[]>([]);

  // 用于跟踪disconnecting状态
  const disconnectingRef = useRef(false);

  // 处理WebSocket消息
  const handleWebSocketMessage = useCallback((wsMessage: WebSocketMessage) => {
    console.log('🔄 处理消息:', wsMessage.event);
    switch (wsMessage.event) {
      case 'SessionStarted':
        message.success('会话已开启');
        setSessionStatus('connected');
        console.log('✅ 会话已开启，开始音频采集');

        // 启动音频采集
        audioManager.startRecordingRecorder((audioData: Int16Array) => {
          // 静默发送音频数据，不输出日志
          wsManager.sendAudioData(audioData);
        }).then(() => {
          console.log('✅ 音频录制已开始');
        }).catch((error) => {
          console.error('❌ 启动音频录制失败:', error);
          message.error('启动音频录制失败');
        });
        break;
      case 'SessionStopped':
        message.success('会话已关闭');
        setSessionStatus('idle');
        setCurrentUserMessage('');
        setCurrentAssistantMessage('');
        setCurrentUserTimestamp('');
        setCurrentAssistantTimestamp('');
        setCurrentToolCalls(undefined);
        setAccumulatedToolArgsByIndex({});
        setAccumulatedToolNameByIndex({});
        setAccumulatedToolIdByIndex({});
        setAccumulatedToolIndexByIndex({});
        // 只有在还在录音时才停止，避免重复停止
        if (audioManager.getRecordingStatus()) {
          audioManager.stopRecording();
          console.log('🛑 会话已关闭，音频录制已停止');
        } else {
          console.log('🛑 会话已关闭，音频录制已停止（之前已停止）');
        }

        // 断开WebSocket连接
        wsManager.disconnect();
        console.log('🛑 WebSocket连接已断开');

        // 重置disconnecting状态
        disconnectingRef.current = false;
        break;
      case 'AudioTranscript':
        if (wsMessage.payload.finished) {
          setCurrentUserMessage(prevMessage => {
            if (prevMessage.trim()) {
              const newMessage: ChatMessage = {
                timestamp: currentUserTimestamp || new Date().toISOString(),
                speaker: 'User',
                content: prevMessage
              };
              // 检查是否已经存在相同的消息，避免重复添加
              setMessages(prev => {
                const lastMessage = prev[prev.length - 1];
                if (lastMessage &&
                    lastMessage.speaker === 'User' &&
                    lastMessage.content === prevMessage) {
                  return prev; // 如果最后一条消息相同，不重复添加
                }
                return [...prev, newMessage];
              });
            }
            return '';
          });
          setCurrentUserTimestamp(''); // 重置时间戳
        } else {
          // 流式文本累积显示，不清除之前的文本
          setCurrentUserMessage(prevMessage => {
            // 如果是第一次收到文本，设置初始时间戳并直接使用新文本
            if (!prevMessage) {
              setCurrentUserTimestamp(new Date().toISOString());
              return wsMessage.payload.text;
            }
            // 否则追加新文本到现有文本
            return prevMessage + wsMessage.payload.text;
          });
        }
        break;
      case 'ResponseText':
        if (wsMessage.payload.finished) {
          // 确定最终的 tool_calls（如果当前帧为空则回退到最近一次的 non-empty）
          const finalToolCallsRaw = (wsMessage as any).payload.tool_calls && (wsMessage as any).payload.tool_calls.length > 0
            ? (wsMessage as any).payload.tool_calls
            : currentToolCalls;

          // 将累计的arguments和name合并回tool_calls
          const finalToolCalls = Array.isArray(finalToolCallsRaw)
            ? finalToolCallsRaw.map((tc: any) => {
                const accArgs = accumulatedToolArgsByIndex[tc.index];
                const accName = accumulatedToolNameByIndex[tc.index];
                const accId = accumulatedToolIdByIndex[tc.index];
                const accIdx = accumulatedToolIndexByIndex[tc.index];
                return {
                  ...tc,
                  id: accId ? accId : tc.id,
                  index: typeof accIdx === 'number' ? accIdx : tc.index,
                  function: {
                    ...tc.function,
                    arguments: accArgs && typeof tc.function?.arguments === 'string' ? accArgs : tc.function?.arguments,
                    name: accName && (tc.function?.name == null || typeof tc.function?.name === 'string') ? accName : tc.function?.name
                  }
                };
              })
            : finalToolCallsRaw;

          setCurrentAssistantMessage(prevMessage => {
            const hasContent = prevMessage.trim().length > 0;
            const hasToolCalls = Array.isArray(finalToolCalls) && finalToolCalls.length > 0;
            if (hasContent || hasToolCalls) {
              const newMessage: ChatMessage = {
                timestamp: currentAssistantTimestamp || new Date().toISOString(),
                speaker: 'Assistant',
                content: prevMessage,
                tool_calls: finalToolCalls
              };
              // 检查是否已经存在相同的消息，避免重复添加
              setMessages(prev => {
                const lastMessage = prev[prev.length - 1];
                if (lastMessage &&
                    lastMessage.speaker === 'Assistant' &&
                    lastMessage.content === prevMessage) {
                  return prev; // 如果最后一条消息相同，不重复添加
                }
                return [...prev, newMessage];
              });
            }
            return '';
          });
          setCurrentAssistantTimestamp(''); // 重置时间戳
          setCurrentToolCalls(undefined); // 重置tool_calls
          setAccumulatedToolArgsByIndex({}); // 重置累计
          setAccumulatedToolNameByIndex({}); // 重置累计
          setAccumulatedToolIdByIndex({}); // 重置累计
          setAccumulatedToolIndexByIndex({}); // 重置累计
        } else {
          // 流式文本累积显示，不清除之前的文本
          setCurrentAssistantMessage(prevMessage => {
            // 如果是第一次收到文本或仅收到 tool_calls，设置初始时间戳
            if (!prevMessage) {
              setCurrentAssistantTimestamp(new Date().toISOString());
            }
            return prevMessage + (((wsMessage as any).payload.text) || '');
          });

          const frameToolCalls = (wsMessage as any).payload.tool_calls as any[] | undefined;
          if (Array.isArray(frameToolCalls)) {
            // 基于当前累计，计算下一帧累计结果
            const nextArgsByIndex: Record<number, string> = { ...accumulatedToolArgsByIndex };
            const nextNameByIndex: Record<number, string> = { ...accumulatedToolNameByIndex };
            const nextIdByIndex: Record<number, string> = { ...accumulatedToolIdByIndex };
            const nextIndexByIndex: Record<number, number> = { ...accumulatedToolIndexByIndex };

            for (const tc of frameToolCalls) {
              const idx = tc.index;
              const argsChunk = typeof tc.function?.arguments === 'string' ? tc.function.arguments : '';
              if (argsChunk) {
                nextArgsByIndex[idx] = (nextArgsByIndex[idx] || '') + argsChunk;
              }
              const nameChunk = typeof tc.function?.name === 'string' ? tc.function.name : '';
              if (nameChunk) {
                nextNameByIndex[idx] = (nextNameByIndex[idx] || '') + nameChunk;
              }
              const idChunk = typeof tc.id === 'string' ? tc.id : '';
              if (idChunk) {
                nextIdByIndex[idx] = (nextIdByIndex[idx] || '') + idChunk;
              }
              if (typeof tc.index === 'number') {
                nextIndexByIndex[idx] = tc.index; // 记录最后一次的数值 index
              }
            }

            // 写回累计状态
            setAccumulatedToolArgsByIndex(nextArgsByIndex);
            setAccumulatedToolNameByIndex(nextNameByIndex);
            setAccumulatedToolIdByIndex(nextIdByIndex);
            setAccumulatedToolIndexByIndex(nextIndexByIndex);

            // 基于累计结果生成合并后的tool_calls，确保UI每帧都显示完整内容
            const merged = frameToolCalls.map(tc => {
              const accArgs = nextArgsByIndex[tc.index];
              const accName = nextNameByIndex[tc.index];
              const accId = nextIdByIndex[tc.index];
              const accIdx = nextIndexByIndex[tc.index];
              const combinedArgs = accArgs ? accArgs : (typeof tc.function?.arguments === 'string' ? tc.function.arguments : '');
              const combinedName = accName ? accName : (typeof tc.function?.name === 'string' ? tc.function.name : tc.function?.name ?? null);
              const combinedId = accId ? accId : (typeof tc.id === 'string' ? tc.id : '');
              const combinedIndex = typeof accIdx === 'number' ? accIdx : tc.index;
              return {
                ...tc,
                id: combinedId,
                index: combinedIndex,
                function: {
                  ...tc.function,
                  arguments: combinedArgs,
                  name: combinedName
                }
              };
            });
            setCurrentToolCalls(merged);
          }
        }
        break;
      case 'ResponseAudioStarted':
        console.log('🎵 开始播放语音回复');
        break;
      case 'ResponseAudioEnded':
        console.log('🎵 语音回复播放完成');
        break;
      default:
        console.log('❓ 未知消息类型:', (wsMessage as any).event);
    }
  }, [audioManager, wsManager, currentUserTimestamp, currentAssistantTimestamp, currentToolCalls, accumulatedToolArgsByIndex, accumulatedToolNameByIndex, accumulatedToolIdByIndex, accumulatedToolIndexByIndex]);

  // 音频流式采集与发送逻辑已内联到handleWebSocketMessage中

  // 切换会话状态
  const handleToggleSession = async () => {
    try {
      if (sessionStatus === 'idle') {
        setSessionStatus('connecting');
        // 清空对话记录
        setMessages([]);
        setCurrentUserMessage('');
        setCurrentAssistantMessage('');
        setCurrentUserTimestamp('');
        setCurrentAssistantTimestamp('');
        setCurrentToolCalls(undefined);
        setAccumulatedToolArgsByIndex({});
        setAccumulatedToolNameByIndex({});
        setAccumulatedToolIdByIndex({});
        setAccumulatedToolIndexByIndex({});

        const hasPermission = await audioManager.checkAudioPermission();
        if (!hasPermission) {
          message.error('需要麦克风权限才能开始对话');
          setSessionStatus('idle');
          return;
        }
        await wsManager.connect();
        const startRequest: SessionStartRequest = {
          directive: 'SessionStart',
          payload: {
            upstream: {
              asr_vendor: sessionConfig.asrProvider,
              asr_options: {
                language: sessionConfig.asrLanguage
              }
            },
            downstream: {
              tts_vendor: sessionConfig.ttsProvider,
              tts_options: {
                voice: sessionConfig.ttsVoice
              }
            },
            parameters: {
              enable_tool_call: sessionConfig.enableTool
            }
          }
        };
        wsManager.sendMessage(startRequest);
        // 不要在这里startRecording，等SessionStarted
      } else if (sessionStatus === 'connected') {
        setSessionStatus('disconnecting');
        console.log('🔄 用户请求停止会话，发送SessionStop消息');

        // 先停止音频录制
        if (audioManager.getRecordingStatus()) {
          audioManager.stopRecording();
          console.log('🛑 用户停止：音频录制已停止');
        }

        const stopRequest: SessionStopRequest = {
          directive: 'SessionStop',
          payload: {}
        };
        wsManager.sendMessage(stopRequest);

        // 等待服务端确认后再断开连接，避免过早断开
        // 连接会在收到SessionStopped消息后断开
        // 设置超时，如果5秒内没有收到SessionStopped，则强制断开
        disconnectingRef.current = true;
        setTimeout(() => {
          if (disconnectingRef.current) {
            console.log('⏰ 超时：未收到SessionStopped确认，强制断开连接');
            wsManager.disconnect();
            setSessionStatus('idle');
            setCurrentUserMessage('');
            setCurrentAssistantMessage('');
            setCurrentUserTimestamp('');
            setCurrentAssistantTimestamp('');
            setCurrentToolCalls(undefined);
            setAccumulatedToolArgsByIndex({});
            setAccumulatedToolNameByIndex({});
            setAccumulatedToolIdByIndex({});
            setAccumulatedToolIndexByIndex({});
            disconnectingRef.current = false;
          }
        }, 5000);
      }
    } catch (error) {
      console.error('会话操作失败:', error);
      message.error('操作失败，请重试');
      setSessionStatus('error');
    }
  };

  // 设置WebSocket事件处理器
  React.useEffect(() => {
    wsManager.addMessageHandler(handleWebSocketMessage);
    wsManager.setErrorHandler((error) => {
      console.error('WebSocket错误:', error);
      message.error('连接出错，请重试');
      setSessionStatus('error');
    });
    return () => {
      wsManager.removeMessageHandler(handleWebSocketMessage);
    };
  }, [wsManager, handleWebSocketMessage]);

  return (
    <Layout style={{ height: '100vh' }}>
      <Sider width="20%" style={{ background: '#fff', padding: '1rem' }}>
        <ConfigPanel
          config={sessionConfig}
          onConfigChange={setSessionConfig}
        />
        {/* 开发模式下的测试面板已移除，保持UI简洁 */}
      </Sider>
      <Content style={{ padding: '1rem' }}>
        <Layout style={{ height: '100%' }}>
          <Content style={{ marginRight: '1rem', flex: '0 0 45%' }}>
            <ChatArea
              status={sessionStatus}
              onToggleSession={handleToggleSession}
            />
          </Content>
          <Sider width="calc(55% - 1rem)" style={{ background: '#fff' }}>
            <ChatHistory
              messages={messages}
              currentUserMessage={currentUserMessage}
              currentAssistantMessage={currentAssistantMessage}
              currentUserTimestamp={currentUserTimestamp}
              currentAssistantTimestamp={currentAssistantTimestamp}
              currentToolCalls={currentToolCalls}
            />
          </Sider>
        </Layout>
      </Content>
    </Layout>
  );
};

export default App;