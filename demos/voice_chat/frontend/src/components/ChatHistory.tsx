import React, { useRef, useEffect, useState, useCallback } from 'react';
import { Typography, Space, Tag, Button, Card } from 'antd';
import { UpOutlined, DownOutlined, ToolOutlined } from '@ant-design/icons';
import ReactMarkdown from 'react-markdown';
import { ChatMessage } from '../types';

const { Text } = Typography;

// 工具调用显示组件
const ToolCallsDisplay: React.FC<{ tool_calls: ChatMessage['tool_calls'] }> = ({ tool_calls }) => {
  if (!tool_calls || tool_calls.length === 0) {
    return null;
  }

  const formatJson = (obj: any) => {
    try {
      return JSON.stringify(obj, null, 2);
    } catch (error) {
      return JSON.stringify(obj);
    }
  };

  return (
    <div style={{ marginTop: '8px' }}>
      <Card
        size="small"
        title={
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <ToolOutlined style={{ color: '#1890ff' }} />
            <Text strong style={{ fontSize: '12px' }}>
              工具调用 ({tool_calls.length})
            </Text>
          </div>
        }
        style={{
          backgroundColor: '#f8f9fa',
          border: '1px solid #e8e8e8',
          borderRadius: '6px'
        }}
        bodyStyle={{ padding: '12px' }}
      >
        <Space direction="vertical" size="small" style={{ width: '100%' }}>
          {tool_calls.map((toolCall, index) => (
            <div key={index} style={{
              backgroundColor: '#fff',
              border: '1px solid #d9d9d9',
              borderRadius: '4px',
              padding: '8px',
              marginBottom: '4px'
            }}>
              <div style={{ marginBottom: '4px' }}>
                <Text type="secondary" style={{ fontSize: '11px' }}>
                  调用 #{toolCall.index + 1}
                </Text>
                {toolCall.function?.name && (
                  <Tag color="blue" style={{ marginLeft: '8px', fontSize: '11px' }}>
                    {toolCall.function.name}
                  </Tag>
                )}
              </div>

               <pre style={{
                 backgroundColor: '#f5f5f5',
                 padding: '8px',
                 borderRadius: '4px',
                 fontSize: '11px',
                 margin: 0,
                 overflow: 'auto',
                 maxHeight: '200px',
                 border: '1px solid #e8e8e8',
                 fontFamily: 'Monaco, Menlo, "Ubuntu Mono", monospace',
                 lineHeight: '1.4'
               }}>
                 <code>{formatJson(toolCall)}</code>
               </pre>
            </div>
          ))}
        </Space>
      </Card>
    </div>
  );
};

interface ChatHistoryProps {
  messages: ChatMessage[];
  currentUserMessage?: string;
  currentAssistantMessage?: string;
  currentUserTimestamp?: string;
  currentAssistantTimestamp?: string;
  currentToolCalls?: ChatMessage['tool_calls'];
}

const ChatHistory: React.FC<ChatHistoryProps> = ({
  messages,
  currentUserMessage = '',
  currentAssistantMessage = '',
  currentUserTimestamp,
  currentAssistantTimestamp,
  currentToolCalls
}) => {
  const scrollContainerRef = useRef<HTMLDivElement>(null);
  const [canScrollUp, setCanScrollUp] = useState(false);
  const [canScrollDown, setCanScrollDown] = useState(false);
  const [isAutoScrolling, setIsAutoScrolling] = useState(true);
  const [lastMessageCount, setLastMessageCount] = useState(0);
  const [lastCurrentMessage, setLastCurrentMessage] = useState('');

  const scrollToBottom = useCallback(() => {
    if (scrollContainerRef.current) {
      scrollContainerRef.current.scrollTo({
        top: scrollContainerRef.current.scrollHeight,
        behavior: 'smooth'
      });
    }
  }, []);

  const scrollToTop = useCallback(() => {
    if (scrollContainerRef.current) {
      scrollContainerRef.current.scrollTo({
        top: 0,
        behavior: 'smooth'
      });
    }
  }, []);

  const updateScrollButtons = useCallback(() => {
    if (scrollContainerRef.current) {
      const { scrollTop, scrollHeight, clientHeight } = scrollContainerRef.current;
      const isAtBottom = scrollTop + clientHeight >= scrollHeight - 5; // 减小阈值，提高精度

      setCanScrollUp(scrollTop > 0);
      setCanScrollDown(scrollTop + clientHeight < scrollHeight);
      setIsAutoScrolling(isAtBottom);
    }
  }, []);

  // 检测是否有新消息
  const hasNewMessages = useCallback(() => {
    const totalMessages = messages.length +
      (currentUserMessage ? 1 : 0) +
      (currentAssistantMessage ? 1 : 0);

    return totalMessages > lastMessageCount ||
           currentUserMessage !== lastCurrentMessage ||
           currentAssistantMessage !== lastCurrentMessage;
  }, [messages.length, currentUserMessage, currentAssistantMessage, lastMessageCount, lastCurrentMessage]);

  // 自动滚动逻辑优化
  useEffect(() => {
    const shouldAutoScroll = isAutoScrolling || hasNewMessages();

    if (shouldAutoScroll) {
      // 使用 requestAnimationFrame 确保DOM更新后再滚动
      requestAnimationFrame(() => {
        scrollToBottom();
      });
    }
  }, [messages, currentUserMessage, currentAssistantMessage, isAutoScrolling, hasNewMessages, scrollToBottom]);

  // 更新消息计数
  useEffect(() => {
    const totalMessages = messages.length +
      (currentUserMessage ? 1 : 0) +
      (currentAssistantMessage ? 1 : 0);

    setLastMessageCount(totalMessages);
    setLastCurrentMessage(currentUserMessage + currentAssistantMessage);
  }, [messages.length, currentUserMessage, currentAssistantMessage]);

  useEffect(() => {
    const scrollContainer = scrollContainerRef.current;
    if (scrollContainer) {
      const handleScroll = () => {
        updateScrollButtons();
      };

      scrollContainer.addEventListener('scroll', handleScroll);
      updateScrollButtons();

      return () => {
        scrollContainer.removeEventListener('scroll', handleScroll);
      };
    }
  }, [updateScrollButtons]);

  // 监听内容变化，确保滚动状态正确
  useEffect(() => {
    updateScrollButtons();
  }, [messages, currentUserMessage, currentAssistantMessage, updateScrollButtons]);

  const formatTimestamp = (timestamp: string) => {
    const date = new Date(timestamp);
    const hours = date.getHours().toString().padStart(2, '0');
    const minutes = date.getMinutes().toString().padStart(2, '0');
    const seconds = date.getSeconds().toString().padStart(2, '0');
    const milliseconds = date.getMilliseconds().toString().padStart(3, '0');
    return `${hours}:${minutes}:${seconds}.${milliseconds}`;
  };

  const getSpeakerColor = (speaker: 'User' | 'Assistant') => {
    return speaker === 'User' ? '#1890ff' : '#52c41a';
  };

  return (
    <div style={{
      height: '100%',
      display: 'flex',
      flexDirection: 'column',
      border: '1px solid #d9d9d9',
      borderRadius: '6px',
      backgroundColor: '#fff',
      overflow: 'hidden'
    }}>
      <div style={{
        padding: '16px',
        borderBottom: '1px solid #f0f0f0',
        backgroundColor: '#fafafa',
        fontWeight: 500,
        flexShrink: 0
      }}>
        对话记录
      </div>

      <div
        ref={scrollContainerRef}
        style={{
          flex: 1,
          overflowY: 'auto',
          overflowX: 'hidden',
          padding: '4px 0',
          paddingRight: '3rem',
          position: 'relative',
          scrollBehavior: 'smooth',
          minHeight: 0
        }}
      >
        {messages.length === 0 && !currentUserMessage && !currentAssistantMessage ? (
          <div style={{ textAlign: 'center', color: '#999', marginTop: '2.5rem' }}>
            <Text type="secondary">暂无对话记录</Text>
          </div>
        ) : (
          <Space direction="vertical" size="small" style={{ width: '100%' }}>
            {messages.map((message, index) => (
              <div key={index} style={{
                display: 'flex',
                flexDirection: 'column',
                padding: '6px 16px',
                borderBottom: index < messages.length - 1 ? '1px solid #f0f0f0' : 'none'
              }}>
                <div style={{ display: 'flex', alignItems: 'center', marginBottom: '2px' }}>
                  <Text type="secondary" style={{ fontSize: '12px', marginRight: '8px' }}>
                    [{formatTimestamp(message.timestamp)}]
                  </Text>
                  <Tag color={getSpeakerColor(message.speaker)}>
                    {message.speaker}
                  </Tag>
                </div>
                <div
                  style={{
                    margin: 0,
                    fontSize: '14px',
                    color: message.isStreaming ? '#1890ff' : 'inherit',
                    wordBreak: 'break-word',
                    whiteSpace: 'pre-wrap',
                    overflowWrap: 'break-word',
                    lineHeight: '1.3'
                  }}
                >
                  <ReactMarkdown
                    components={{
                      // 自定义段落样式
                      p: ({ children }) => <p style={{ margin: '4px 0' }}>{children}</p>,
                      // 自定义列表样式
                      ul: ({ children }) => <ul style={{ margin: '4px 0', paddingLeft: '20px' }}>{children}</ul>,
                      ol: ({ children }) => <ol style={{ margin: '4px 0', paddingLeft: '20px' }}>{children}</ol>,
                      li: ({ children }) => <li style={{ margin: '2px 0' }}>{children}</li>,
                      // 自定义标题样式
                      h1: ({ children }) => <h1 style={{ fontSize: '18px', margin: '8px 0 4px 0', fontWeight: 'bold' }}>{children}</h1>,
                      h2: ({ children }) => <h2 style={{ fontSize: '16px', margin: '6px 0 3px 0', fontWeight: 'bold' }}>{children}</h2>,
                      h3: ({ children }) => <h3 style={{ fontSize: '14px', margin: '4px 0 2px 0', fontWeight: 'bold' }}>{children}</h3>,
                      // 自定义强调样式
                      strong: ({ children }) => <strong style={{ fontWeight: 'bold', color: '#333' }}>{children}</strong>,
                      em: ({ children }) => <em style={{ fontStyle: 'italic' }}>{children}</em>,
                      // 自定义代码样式
                      code: ({ children }) => <code style={{ backgroundColor: '#f5f5f5', padding: '2px 4px', borderRadius: '3px', fontFamily: 'monospace' }}>{children}</code>,
                    }}
                  >
                    {message.content || '...'}
                  </ReactMarkdown>
                  <ToolCallsDisplay tool_calls={message.tool_calls} />
                </div>
              </div>
            ))}

            {currentUserMessage && (
              <div style={{
                display: 'flex',
                flexDirection: 'column',
                padding: '6px 16px',
                borderBottom: '1px solid #f0f0f0'
              }}>
                <div style={{ display: 'flex', alignItems: 'center', marginBottom: '2px' }}>
                  <Text type="secondary" style={{ fontSize: '12px', marginRight: '8px' }}>
                    [{formatTimestamp(currentUserTimestamp || new Date().toISOString())}]
                  </Text>
                  <Tag color={getSpeakerColor('User')}>
                    User
                  </Tag>
                </div>
                <div
                  style={{
                    margin: 0,
                    fontSize: '14px',
                    color: '#1890ff',
                    wordBreak: 'break-word',
                    whiteSpace: 'pre-wrap',
                    overflowWrap: 'break-word',
                    lineHeight: '1.3'
                  }}
                >
                  <ReactMarkdown
                    components={{
                      // 自定义段落样式
                      p: ({ children }) => <p style={{ margin: '4px 0' }}>{children}</p>,
                      // 自定义列表样式
                      ul: ({ children }) => <ul style={{ margin: '4px 0', paddingLeft: '20px' }}>{children}</ul>,
                      ol: ({ children }) => <ol style={{ margin: '4px 0', paddingLeft: '20px' }}>{children}</ol>,
                      li: ({ children }) => <li style={{ margin: '2px 0' }}>{children}</li>,
                      // 自定义标题样式
                      h1: ({ children }) => <h1 style={{ fontSize: '18px', margin: '8px 0 4px 0', fontWeight: 'bold' }}>{children}</h1>,
                      h2: ({ children }) => <h2 style={{ fontSize: '16px', margin: '6px 0 3px 0', fontWeight: 'bold' }}>{children}</h2>,
                      h3: ({ children }) => <h3 style={{ fontSize: '14px', margin: '4px 0 2px 0', fontWeight: 'bold' }}>{children}</h3>,
                      // 自定义强调样式
                      strong: ({ children }) => <strong style={{ fontWeight: 'bold', color: '#333' }}>{children}</strong>,
                      em: ({ children }) => <em style={{ fontStyle: 'italic' }}>{children}</em>,
                      // 自定义代码样式
                      code: ({ children }) => <code style={{ backgroundColor: '#f5f5f5', padding: '2px 4px', borderRadius: '3px', fontFamily: 'monospace' }}>{children}</code>,
                    }}
                  >
                    {currentUserMessage}
                  </ReactMarkdown>
                </div>
              </div>
            )}

            {currentAssistantMessage || currentToolCalls ? (
              <div style={{
                display: 'flex',
                flexDirection: 'column',
                padding: '6px 16px',
                borderBottom: '1px solid #f0f0f0'
              }}>
                <div style={{ display: 'flex', alignItems: 'center', marginBottom: '2px' }}>
                  <Text type="secondary" style={{ fontSize: '12px', marginRight: '8px' }}>
                    [{formatTimestamp(currentAssistantTimestamp || new Date().toISOString())}]
                  </Text>
                  <Tag color={getSpeakerColor('Assistant')}>
                    Assistant
                  </Tag>
                </div>
                <div
                  style={{
                    margin: 0,
                    fontSize: '14px',
                    color: '#1890ff',
                    wordBreak: 'break-word',
                    whiteSpace: 'pre-wrap',
                    overflowWrap: 'break-word',
                    lineHeight: '1.3'
                  }}
                >
                  <ReactMarkdown
                    components={{
                      // 自定义段落样式
                      p: ({ children }) => <p style={{ margin: '4px 0' }}>{children}</p>,
                      // 自定义列表样式
                      ul: ({ children }) => <ul style={{ margin: '4px 0', paddingLeft: '20px' }}>{children}</ul>,
                      ol: ({ children }) => <ol style={{ margin: '4px 0', paddingLeft: '20px' }}>{children}</ol>,
                      li: ({ children }) => <li style={{ margin: '2px 0' }}>{children}</li>,
                      // 自定义标题样式
                      h1: ({ children }) => <h1 style={{ fontSize: '18px', margin: '8px 0 4px 0', fontWeight: 'bold' }}>{children}</h1>,
                      h2: ({ children }) => <h2 style={{ fontSize: '16px', margin: '6px 0 3px 0', fontWeight: 'bold' }}>{children}</h2>,
                      h3: ({ children }) => <h3 style={{ fontSize: '14px', margin: '4px 0 2px 0', fontWeight: 'bold' }}>{children}</h3>,
                      // 自定义强调样式
                      strong: ({ children }) => <strong style={{ fontWeight: 'bold', color: '#333' }}>{children}</strong>,
                      em: ({ children }) => <em style={{ fontStyle: 'italic' }}>{children}</em>,
                      // 自定义代码样式
                      code: ({ children }) => <code style={{ backgroundColor: '#f5f5f5', padding: '2px 4px', borderRadius: '3px', fontFamily: 'monospace' }}>{children}</code>,
                    }}
                  >
                    {currentAssistantMessage}
                  </ReactMarkdown>
                  <ToolCallsDisplay tool_calls={currentToolCalls} />
                </div>
              </div>
            ) : null}
          </Space>
        )}
      </div>

      <div style={{
        position: 'absolute',
        right: '8px',
        top: '60px',
        display: 'flex',
        flexDirection: 'column',
        gap: '4px',
        zIndex: 10
      }}>
        <Button
          type="primary"
          size="small"
          icon={<UpOutlined />}
          onClick={scrollToTop}
          disabled={!canScrollUp}
          title="滚动到顶部"
          style={{
            width: '32px',
            height: '32px',
            borderRadius: '50%',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            opacity: canScrollUp ? 1 : 0.5,
            boxShadow: '0 2px 8px rgba(0,0,0,0.15)'
          }}
        />
        <Button
          type="primary"
          size="small"
          icon={<DownOutlined />}
          onClick={scrollToBottom}
          disabled={!canScrollDown}
          title="滚动到底部"
          style={{
            width: '32px',
            height: '32px',
            borderRadius: '50%',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            opacity: canScrollDown ? 1 : 0.5,
            boxShadow: '0 2px 8px rgba(0,0,0,0.15)'
          }}
        />
      </div>
    </div>
  );
};

export default ChatHistory;
