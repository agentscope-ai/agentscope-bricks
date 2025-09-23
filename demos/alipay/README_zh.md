# 支付宝集成演示

## 快速开始

本演示展示了 agentbricks 与支付宝支付和订阅服务的集成，用于 AI智能体的支付处理和付费服务。

### 运行支付演示

1. 配置环境变量：
```shell
export ALIPAY_APP_ID=your_alipay_app_id
export ALIPAY_PRIVATE_KEY="your_alipay_private_key"  # pragma: allowlist secret
export ALIPAY_PUBLIC_KEY="your_alipay_public_key"
export AP_CURRENT_ENV=sandbox  # 沙箱环境或 production 生产环境
export DASHSCOPE_API_KEY=your_dashscope_api_key
```

2. 安装必需的依赖：
```shell
pip install "agentscope-bricks[alipay]"
```

3. 运行支付演示：
```shell
python alipay_payment_demo.py
```

### 运行订阅演示

1. 配置额外的环境变量：
```shell
export SUBSCRIBE_PLAN_ID=your_subscription_plan_id
export X_AGENT_NAME=your_agent_name
export USE_TIMES=1  # 每次使用扣减的次数
```

2. 运行订阅演示：
```shell
python alipay_subscribe_demo.py
```

### 功能特性

#### 支付组件
- **手机支付**：为手机浏览器生成支付链接，支持 App 跳转
- **网页支付**：为桌面浏览器生成二维码支付链接
- **支付查询**：检查支付状态和交易详情
- **退款处理**：处理全额和部分退款，支持跟踪
- **退款查询**：检查退款状态和详情

#### 订阅服务
- **状态检查**：验证用户订阅状态和套餐详情
- **套餐初始化**：生成订阅购买链接
- **使用跟踪**：记录和扣减按次付费模式的使用次数
- **智能检查**：结合订阅检查和自动链接生成


### 架构说明

演示包含以下组件：
- `alipay_payment_demo.py`：完整的支付工作流程和 AI 智能体集成
- `alipay_subscribe_demo.py`：订阅管理和使用跟踪

### 使用场景

#### 电商集成
- 产品购买工作流程
- 订单管理和跟踪
- 支付状态监控
- 自动退款处理


#### AI 智能体付费服务
- 基于使用量的定价模式
- 订阅管理自动化

## 配置说明

### 必需的环境变量

| 变量名 | 必需 | 说明 |
|--------|------|------|
| `ALIPAY_APP_ID` | ✅ | 支付宝应用 ID |
| `ALIPAY_PRIVATE_KEY` | ✅ | 应用私钥（RSA 格式）|
| `ALIPAY_PUBLIC_KEY` | ✅ | 支付宝公钥，用于签名验证 |
| `SUBSCRIBE_PLAN_ID` | ✅| 订阅计划 ID |
| `X_AGENT_NAME` | ✅ | AI 智能体名称，用于订阅跟踪 |

### 可选的环境变量

| 变量名 | 默认值 | 说明 |
|--------|-------|------|
| `AP_RETURN_URL` | - | 支付完成后重定向 URL |
| `AP_NOTIFY_URL` | - | 支付异步通知回调 URL |
| `USE_TIMES` | 1 | 每次服务调用扣减的使用次数 |
| `AP_CURRENT_ENV` | -  | 环境：`sandbox` 或 `production` |

## 演示流程

### 支付演示流程

1. **订单生成**：AI 智能体根据用户请求创建订单
2. **支付处理**：生成适当的支付链接（手机/桌面）
3. **状态监控**：检查支付状态和处理回调
4. **退款管理**：处理退款并跟踪状态

### 订阅演示流程

1. **订阅检查**：验证用户订阅状态
2. **链接生成**：根据需要创建订阅购买链接
3. **服务使用**：模拟 AI 服务使用（诗歌生成）
4. **使用跟踪**：记录使用情况并扣减订阅配额

### 核心组件演示

```python
# 支付处理
mobile_payment = MobileAlipayPayment()
payment_result = await mobile_payment.arun({
    "out_trade_no": "ORDER_001",
    "order_title": "AI 服务",
    "total_amount": 99.99
})

# 订阅管理
subscription_check = AlipaySubscribeCheckOrInitialize()
result = await subscription_check.arun({"uuid": "user_123"})

# 使用跟踪
usage_tracker = AlipaySubscribeTimesSave()
usage_result = await usage_tracker.arun({
    "uuid": "user_123",
    "out_request_no": "usage_001"
})
```

## 测试说明

### 沙箱环境

使用支付宝沙箱环境进行测试：
1. 设置 `AP_CURRENT_ENV=sandbox`
2. 使用沙箱应用凭证
3. 使用沙箱账号和支付方式进行测试

### 生产部署

生产环境使用：
1. 设置 `AP_CURRENT_ENV=production`
2. 使用生产应用凭证
3. 配置正确的回调 URL
4. 实现适当的错误处理和日志记录

## 安全注意事项

- 安全存储私钥（使用环境变量，不要写在代码中）
- 防止提示词注入风险，优先使用工作流模式


## 故障排除

### 常见问题

1. **签名无效**：检查私钥/公钥配置
2. **环境不匹配**：确保沙箱/生产环境设置匹配
3. **依赖缺失**：安装 `alipay-sdk-python` 和 `cryptography`
4. **API 超时**：为网络问题实现重试逻辑


## 文档链接

- [支付宝 SDK 文档](https://github.com/alipay/alipay-sdk-python)
- [手机支付接入](https://opendocs.alipay.com/open/203/105285)
- [订阅服务 API](https://opendocs.alipay.com/solution/0i40x9?pathHash=29e2835d)