import Recorder from 'recorder-core';
import 'recorder-core/src/extensions/waveview';

export class AudioManager {
  private mediaStream: MediaStream | null = null;
  private audioContext: AudioContext | null = null;
  private sourceNode: MediaStreamAudioSourceNode | null = null;
  private processorNode: ScriptProcessorNode | null = null;
  private onAudioData: ((data: Int16Array) => void) | null = null;
  private isRecording = false;

  private readonly sampleRate: number;
  private readonly bufferSize = 4096;

  // Recorder.js相关
  private recorder: any = null;
  private sendPcmBufferRef = new Int16Array(0);
  private sendChunkRef: any = null;
  private sendLastFrameRef: Int16Array | null = null;

  constructor(sampleRate: number = 16000) {
    this.sampleRate = sampleRate;
    this.audioContext = new (window.AudioContext || (window as any).webkitAudioContext)({
      sampleRate: this.sampleRate
    });
  }

  // 使用Recorder.js的方法
  async startRecordingRecorder(onData: (data: Int16Array) => void): Promise<void> {
    try {
      this.mediaStream = await navigator.mediaDevices.getUserMedia({
        audio: {
          sampleRate: this.sampleRate,
          channelCount: 1,
          echoCancellation: true,
          noiseSuppression: true,
          autoGainControl: true,
        },
      });

      this.onAudioData = onData;
      this.isRecording = true;

      // 重置缓冲区
      this.handleReset();

      const recorder = Recorder({
        type: 'unknown',
        onProcess: (
          buffers: (Int16Array | null)[],
          powerLevel: unknown,
          bufferDuration: unknown,
          bufferSampleRate: number,
          newBufferIdx: number,
        ) => {
          // 静默处理音频数据，不输出日志
          this.handleProcess(buffers, bufferSampleRate, false);
        },
      });

      recorder.open(
        () => {
          recorder.start();
        },
        (msg: string, isUserNotAllow: boolean) => {
          console.error('❌ 无法录音:', msg, isUserNotAllow);
          throw new Error(`无法录音: ${msg}`);
        },
      );

      this.recorder = recorder;

    } catch (error) {
      console.error('❌ 启动音频录制失败:', error);
      throw error;
    }
  }

  private handleReset() {
    this.sendPcmBufferRef = new Int16Array(0);
    this.sendChunkRef = null;
    this.sendLastFrameRef = null;
  }

  private handleSend(pcmFrame: Int16Array, isClose: boolean) {
    if (isClose && pcmFrame.length === 0) {
      const len = this.sendLastFrameRef
        ? this.sendLastFrameRef.length
        : Math.round((this.sampleRate / 1000) * 50);
      pcmFrame = new Int16Array(len);
    }
    this.sendLastFrameRef = pcmFrame;

    if (this.onAudioData) {
      // 静默发送音频数据，不输出日志
      this.onAudioData(pcmFrame);
    }
  }

  private handleProcess(
    buffers: (Int16Array | null)[],
    bufferSampleRate: number,
    isClose: boolean,
  ) {
    let pcm = new Int16Array(0);
    if (buffers.length > 0) {
      // 把 pcm列表（二维数组）展开成一维
      const chunk = Recorder.SampleData(
        buffers,
        bufferSampleRate,
        this.sampleRate,
        this.sendChunkRef,
      );
      this.sendChunkRef = chunk;

      pcm = chunk.data;
      // 静默处理音频数据，不输出日志
    }

    let pcmBuffer = this.sendPcmBufferRef;
    const tmp = new Int16Array(pcmBuffer.length + pcm.length);
    tmp.set(pcmBuffer, 0);
    tmp.set(pcm, pcmBuffer.length);
    pcmBuffer = tmp;

    // 计算100ms对应的采样点数
    const chunkSize = Math.floor(this.sampleRate * 0.1); // 1600个采样点

    // 按 timeSlice 切分
    while (true) {
      if (pcmBuffer.length >= chunkSize) {
        const frame = new Int16Array(pcmBuffer.subarray(0, chunkSize));
        pcmBuffer = new Int16Array(pcmBuffer.subarray(chunkSize));

        let closeVal = false;
        if (isClose && pcmBuffer.length === 0) {
          closeVal = true;
        }
        this.handleSend(frame, closeVal);
        if (!closeVal) continue;
      } else if (isClose) {
        const frame = new Int16Array(chunkSize);
        frame.set(pcmBuffer);
        pcmBuffer = new Int16Array(0);
        this.handleSend(frame, true);
      }
      break;
    }
    this.sendPcmBufferRef = pcmBuffer;
  }

  stopRecording(): void {
    this.isRecording = false;

    if (this.recorder) {
      console.log('AudioManager.stopRecording: 停止Recorder录音');
      this.recorder.close();
      this.handleProcess([], 0, true);
      this.recorder = null;
    }

    if (this.processorNode) {
      this.processorNode.disconnect();
      this.processorNode = null;
    }
    if (this.sourceNode) {
      this.sourceNode.disconnect();
      this.sourceNode = null;
    }
    if (this.mediaStream) {
      this.mediaStream.getTracks().forEach(track => track.stop());
      this.mediaStream = null;
    }
    console.log('音频录制已停止');
  }

  playAudioData(audioData: ArrayBuffer): void {
    if (!this.audioContext) {
      console.error('❌ AudioContext未初始化，无法播放音频');
      return;
    }

    try {
      // 将 ArrayBuffer 转换为 Int16Array (PCM数据)
      const pcmData = new Int16Array(audioData);

      // 将 16 位整数 PCM 转换为 -1.0 到 1.0 之间的浮点数
      const float32Data = new Float32Array(pcmData.length);
      for (let i = 0; i < pcmData.length; i++) {
        float32Data[i] = pcmData[i] / 32768.0;  // 32768 = 2^15
      }

      // 创建 AudioBuffer
      const audioBuffer = this.audioContext.createBuffer(
        1,                    // 通道数：1 表示单声道
        float32Data.length,   // 采样帧数
        16000                 // 采样率，需要与录音时的采样率匹配
      );

      // 将数据写入 AudioBuffer
      audioBuffer.copyToChannel(float32Data, 0);  // 写入到第一个通道

      const source = this.audioContext.createBufferSource();
      source.buffer = audioBuffer;
      source.connect(this.audioContext.destination);

      source.addEventListener('ended', () => {
        console.log('🎵 音频播放结束');
      });

      source.start(0);
      console.log('🎵 开始播放音频:', audioData.byteLength, '字节');

    } catch (error) {
      console.error('❌ 播放音频失败:', error);
    }
  }

  async checkAudioPermission(): Promise<boolean> {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      stream.getTracks().forEach(track => track.stop());
      return true;
    } catch (error) {
      console.error('音频权限检查失败:', error);
      return false;
    }
  }

  getRecordingStatus(): boolean {
    return this.isRecording;
  }

  // 保留原有的ScriptProcessorNode方法作为备用
  async startRecordingSimple(onData: (data: Int16Array) => void): Promise<void> {
    try {
      console.log('AudioManager.startRecordingSimple: 开始获取麦克风权限...');

      this.mediaStream = await navigator.mediaDevices.getUserMedia({
        audio: {
          sampleRate: this.sampleRate,
          channelCount: 1,
          echoCancellation: true,
          noiseSuppression: true,
          autoGainControl: true,
        },
      });
      console.log('AudioManager.startRecordingSimple: 麦克风权限获取成功');

      this.onAudioData = onData;
      this.isRecording = true;

      // 确保AudioContext处于运行状态
      if (this.audioContext!.state === 'suspended') {
        console.log('AudioManager.startRecordingSimple: 启动AudioContext...');
        await this.audioContext!.resume();
        console.log('AudioManager.startRecordingSimple: AudioContext状态:', this.audioContext!.state);
      }

      // 计算100ms对应的缓冲区大小
      const samplesPer100ms = Math.floor(this.sampleRate * 0.1); // 16000 * 0.1 = 1600
      console.log(`AudioManager.startRecordingSimple: 100ms对应 ${samplesPer100ms} 个采样点`);

      // 创建音频节点，使用1600作为缓冲区大小
      this.sourceNode = this.audioContext!.createMediaStreamSource(this.mediaStream);
      this.processorNode = this.audioContext!.createScriptProcessor(samplesPer100ms, 1, 1);

      console.log('AudioManager.startRecordingSimple: 音频节点创建成功');
      console.log('AudioManager.startRecordingSimple: sourceNode:', this.sourceNode);
      console.log('AudioManager.startRecordingSimple: processorNode:', this.processorNode);

      // 设置回调
      let callbackCount = 0;
      this.processorNode.onaudioprocess = (event) => {
        callbackCount++;
        console.log(`AudioManager.startRecordingSimple.onaudioprocess: 回调 #${callbackCount} 被触发`);

        if (!this.isRecording) {
          console.log('AudioManager.startRecordingSimple.onaudioprocess: 录制已停止，跳过处理');
          return;
        }

        const inputBuffer = event.inputBuffer;
        const inputData = inputBuffer.getChannelData(0);
        console.log(`AudioManager.startRecordingSimple.onaudioprocess: 输入数据长度: ${inputData.length}`);

        // 检查音频信号强度
        let maxAmplitude = 0;
        for (let i = 0; i < inputData.length; i++) {
          maxAmplitude = Math.max(maxAmplitude, Math.abs(inputData[i]));
        }
        console.log(`AudioManager.startRecordingSimple.onaudioprocess: 音频信号最大幅度: ${maxAmplitude.toFixed(4)}`);

        // 如果音频信号太弱，可能是静音
        if (maxAmplitude < 0.01) {
          console.log('AudioManager.startRecordingSimple.onaudioprocess: 检测到静音或音量太小');
        }

        const pcmData = new Int16Array(inputData.length);
        for (let i = 0; i < inputData.length; i++) {
          const sample = Math.max(-1, Math.min(1, inputData[i]));
          pcmData[i] = sample < 0 ? sample * 0x8000 : sample * 0x7FFF;
        }

        if (this.onAudioData) {
          console.log(`AudioManager.startRecordingSimple: 收到音频数据: ${pcmData.length} 个采样点`);
          this.onAudioData(pcmData);
        } else {
          console.log('AudioManager.startRecordingSimple.onaudioprocess: onAudioData回调未设置');
        }
      };

      // 连接节点
      console.log('AudioManager.startRecordingSimple: 连接音频节点...');
      this.sourceNode.connect(this.processorNode);
      console.log('AudioManager.startRecordingSimple: sourceNode连接到processorNode');

      this.processorNode.connect(this.audioContext!.destination);
      console.log('AudioManager.startRecordingSimple: processorNode连接到destination');

      console.log('AudioManager.startRecordingSimple: 音频录制已开始');

      // 监控回调
      setTimeout(() => {
        if (callbackCount === 0) {
          console.log('⚠️ AudioManager.startRecordingSimple: 警告 - 没有收到音频回调');
        } else {
          console.log(`✅ AudioManager.startRecordingSimple: 已收到 ${callbackCount} 个音频回调`);
        }
      }, 3000);

    } catch (error) {
      console.error('AudioManager.startRecordingSimple: 启动音频录制失败:', error);
      throw error;
    }
  }
}