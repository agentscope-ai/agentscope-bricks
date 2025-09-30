// WebSocket消息类型定义
export interface SessionStartRequest {
  directive: 'SessionStart';
  payload: {
    upstream: Record<string, any>;
    downstream: Record<string, any>;
    parameters: Record<string, any>;
  };
}

export interface SessionStopRequest {
  directive: 'SessionStop';
  payload: Record<string, any>;
}

export interface SessionStartedResponse {
  event: 'SessionStarted';
  payload: {
    session_id: string;
  };
}

export interface SessionStoppedResponse {
  event: 'SessionStopped';
  payload: {
    session_id: string;
  };
}

export interface AudioTranscriptResponse {
  event: 'AudioTranscript';
  payload: {
    session_id: string;
    text: string;
    finished: boolean;
  };
}

export interface ResponseTextResponse {
  event: 'ResponseText';
  payload: {
    session_id: string;
    text: string | null;
    tool_calls?: Array<{
      index: number;
      id: string;
      function: {
        arguments: string;
        name: string | null;
      };
      type: string;
    }>;
    finished: boolean;
  };
}

export interface ResponseAudioStartedResponse {
  event: 'ResponseAudioStarted';
  payload: {
    session_id: string;
  };
}

export interface ResponseAudioEndedResponse {
  event: 'ResponseAudioEnded';
  payload: {
    session_id: string;
  };
}

export type WebSocketMessage =
  | SessionStartedResponse
  | SessionStoppedResponse
  | AudioTranscriptResponse
  | ResponseTextResponse
  | ResponseAudioStartedResponse
  | ResponseAudioEndedResponse;

// 对话记录类型
export interface ChatMessage {
  timestamp: string;
  speaker: 'User' | 'Assistant';
  content: string;
  isStreaming?: boolean;
  tool_calls?: Array<{
    index: number;
    id: string;
    function: {
      arguments: string;
      name: string | null;
    };
    type: string;
  }>;
}

// 会话状态类型
export interface SessionConfig {
  asrProvider: string;
  asrLanguage: string;
  enableTool: boolean;
  ttsProvider: string;
  ttsVoice: string;
}

export type SessionStatus = 'idle' | 'connecting' | 'connected' | 'disconnecting' | 'error';