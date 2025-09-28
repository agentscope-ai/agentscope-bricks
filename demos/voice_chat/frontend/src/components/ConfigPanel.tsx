import React, { useEffect } from 'react';
import { Card, Form, Select, Switch } from 'antd';
import { SessionConfig } from '../types';

interface ConfigPanelProps {
  config: SessionConfig;
  onConfigChange: (config: SessionConfig) => void;
}

const ConfigPanel: React.FC<ConfigPanelProps> = ({ config, onConfigChange }) => {
  const [form] = Form.useForm();

  const handleValuesChange = (changedValues: any, allValues: SessionConfig) => {
    // If ASR Vendor changed, reset ASR Language to default
    if (changedValues.asrProvider && changedValues.asrProvider !== config.asrProvider) {
      const defaultLanguage = changedValues.asrProvider === 'modelstudio' ? 'zh-CN' : 'en-US';
      allValues.asrLanguage = defaultLanguage;
      // Update the form field to reflect the new default value
      form.setFieldsValue({ asrLanguage: defaultLanguage });
    }

    // If TTS Vendor changed, reset TTS Voice to default
    if (changedValues.ttsProvider && changedValues.ttsProvider !== config.ttsProvider) {
      const defaultVoice = changedValues.ttsProvider === 'modelstudio' ? 'longcheng_v2' : 'en-US-AvaMultilingualNeural';
      allValues.ttsVoice = defaultVoice;
      // Update the form field to reflect the new default value
      form.setFieldsValue({ ttsVoice: defaultVoice });
    }
    onConfigChange(allValues);
  };

  // Update form values when config changes externally
  useEffect(() => {
    form.setFieldsValue(config);
  }, [config, form]);

  return (
    <Card title="会话配置" style={{ height: '100%' }}>
      <Form
        form={form}
        layout="vertical"
        initialValues={config}
        onValuesChange={handleValuesChange}
      >
        <Form.Item
          label="Enable Tools"
          name="enableTool"
          valuePropName="checked"
        >
          <Switch />
        </Form.Item>

        <Form.Item
          label="ASR Vendor"
          name="asrProvider"
          rules={[{ required: true, message: '请选择ASR厂商' }]}
        >
          <Select placeholder="请选择ASR厂商">
            <Select.Option value="modelstudio">modelstudio</Select.Option>
            <Select.Option value="azure">azure</Select.Option>
          </Select>
        </Form.Item>

        <Form.Item
          label="ASR Language"
          name="asrLanguage"
          rules={[{ required: true, message: '请选择ASR语言' }]}
        >
          <Select placeholder="请选择ASR语言">
            <Select.Option value="zh-CN">zh-CN</Select.Option>
            <Select.Option value="en-US">en-US</Select.Option>
          </Select>
        </Form.Item>

        <Form.Item
          label="TTS Vendor"
          name="ttsProvider"
          rules={[{ required: true, message: '请选择TTS厂商' }]}
        >
          <Select placeholder="请选择TTS厂商">
            <Select.Option value="modelstudio">modelstudio</Select.Option>
            <Select.Option value="azure">azure</Select.Option>
          </Select>
        </Form.Item>

        <Form.Item
          label="TTS Voice"
          name="ttsVoice"
          rules={[{ required: true, message: '请选择TTS语音' }]}
        >
          <Select placeholder="请选择TTS语音">
            {config.ttsProvider === 'modelstudio' ? (
              <>
                <Select.Option value="longcheng_v2">longcheng_v2</Select.Option>
                <Select.Option value="longwan_v2">longwan_v2</Select.Option>
              </>
            ) : (
              <>
                <Select.Option value="en-US-AvaMultilingualNeural">en-US-AvaMultilingualNeural</Select.Option>
                <Select.Option value="zh-CN-XiaoxiaoNeural">zh-CN-XiaoxiaoNeural</Select.Option>
              </>
            )}
          </Select>
        </Form.Item>
      </Form>
    </Card>
  );
};

export default ConfigPanel;