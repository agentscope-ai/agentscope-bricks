import { WebSocketMessage, SessionStartRequest, SessionStopRequest } from '../types';

export class WebSocketManager {
  private ws: WebSocket | null = null;
  private url: string;
  private headers: Record<string, string>;
  private messageHandlers: ((message: WebSocketMessage) => void)[] = [];
  private onOpen: (() => void) | null = null;
  private onClose: (() => void) | null = null;
  private onError: ((error: Event) => void) | null = null;
  private audioManager: any = null; // 用于播放音频

  constructor(url: string, headers: Record<string, string> = {}) {
    this.url = url;
    this.headers = headers;
  }

  connect(): Promise<void> {
    return new Promise((resolve, reject) => {
      try {
        this.ws = new WebSocket(this.url);

        this.ws.onopen = () => {
          console.log('WebSocket连接已建立');
          if (this.onOpen) this.onOpen();
          resolve();
        };

        this.ws.onmessage = (event) => {
          try {
            if (typeof event.data === 'string') {
              // JSON消息
              const message: WebSocketMessage = JSON.parse(event.data);
              console.log('📨 收到JSON消息:', message.event, (message.payload as any)?.text?.substring(0, 50) || '');
              // 调用所有注册的消息处理器
              this.messageHandlers.forEach((handler, index) => {
                handler(message);
              });
            } else {
              // 二进制消息（音频数据）
              console.log('🎵 收到音频数据:', event.data.byteLength, '字节');
              event.data.arrayBuffer().then((buffer: ArrayBuffer) => {
                console.log('🎵 音频数据转换完成:', buffer.byteLength, '字节');
                // 处理音频数据
                this.handleAudioData(buffer);
              }).catch((error: any) => {
                console.error('❌ 音频数据处理失败:', error);
              });
            }
          } catch (error) {
            console.error('❌ 消息解析失败:', error);
          }
        };

        this.ws.onclose = () => {
          console.log('WebSocket连接已关闭');
          if (this.onClose) this.onClose();
        };

        this.ws.onerror = (error) => {
          console.error('WebSocket连接错误:', error);
          if (this.onError) this.onError(error);
          reject(error);
        };
      } catch (error) {
        reject(error);
      }
    });
  }

  disconnect(): void {
    if (this.ws) {
      this.ws.close();
      this.ws = null;
    }
  }

  sendMessage(message: SessionStartRequest | SessionStopRequest): void {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      const messageStr = JSON.stringify(message);
      console.log('发送WebSocket消息:', messageStr);
      this.ws.send(messageStr);
    } else {
      console.error('WebSocket未连接，无法发送消息');
    }
  }

  sendAudioData(audioData: Int16Array): void {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      // 静默发送音频数据，不输出日志
      this.ws.send(audioData.buffer);
    } else {
      console.error('WebSocket未连接，无法发送音频数据');
    }
  }

  addMessageHandler(handler: (message: WebSocketMessage) => void): void {
    this.messageHandlers.push(handler);
    console.log(`添加消息处理器，当前处理器数量: ${this.messageHandlers.length}`);
  }

  removeMessageHandler(handler: (message: WebSocketMessage) => void): void {
    const index = this.messageHandlers.indexOf(handler);
    if (index > -1) {
      this.messageHandlers.splice(index, 1);
    }
  }

  setMessageHandler(handler: (message: WebSocketMessage) => void): void {
    // 为了向后兼容，保留这个方法
    this.messageHandlers = [handler];
  }

  setOpenHandler(handler: () => void): void {
    this.onOpen = handler;
  }

  setCloseHandler(handler: () => void): void {
    this.onClose = handler;
  }

  setErrorHandler(handler: (error: Event) => void): void {
    this.onError = handler;
  }

  isConnected(): boolean {
    return this.ws !== null && this.ws.readyState === WebSocket.OPEN;
  }

  setAudioManager(audioManager: any) {
    this.audioManager = audioManager;
  }

  private handleAudioData(audioBuffer: ArrayBuffer) {
    if (this.audioManager) {
      this.audioManager.playAudioData(audioBuffer);
    } else {
      console.error('❌ AudioManager未设置，无法播放音频');
    }
  }
}