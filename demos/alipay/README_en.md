# Alipay Integration Demo

## Quick Start

This demo showcases the integration of agentbricks with Alipay payment and subscription services for AI agent payment processing and paid services.

### Running Payment Demo

1. Configure environment variables:
```shell
export ALIPAY_APP_ID=your_alipay_app_id
export ALIPAY_PRIVATE_KEY="your_alipay_private_key"
export ALIPAY_PUBLIC_KEY="your_alipay_public_key"
export AP_CURRENT_ENV=sandbox  # sandbox or production environment
export DASHSCOPE_API_KEY=your_dashscope_api_key
```

2. Install required dependencies:
```shell
pip install alipay-sdk-python cryptography
```

3. Run payment demo:
```shell
python alipay_payment_demo.py
```

### Running Subscription Demo

1. Configure additional environment variables:
```shell
export SUBSCRIBE_PLAN_ID=your_subscription_plan_id
export X_AGENT_NAME=your_agent_name
export USE_TIMES=1  # Usage count deducted per use
```

2. Run subscription demo:
```shell
python alipay_subscribe_demo.py
```

### Features

#### Payment Components
- **Mobile Payment**: Generate payment links for mobile browsers with app redirection support
- **Web Payment**: Generate QR code payment links for desktop browsers
- **Payment Query**: Check payment status and transaction details
- **Refund Processing**: Handle full and partial refunds with tracking
- **Refund Query**: Check refund status and details

#### Subscription Services
- **Status Check**: Verify user subscription status and package details
- **Package Initialization**: Generate subscription purchase links
- **Usage Tracking**: Record and deduct usage counts for pay-per-use models
- **Smart Check**: Combine subscription checking with automatic link generation

### Architecture Overview

The demo includes the following components:
- `alipay_payment_demo.py`: Complete payment workflow and AI agent integration
- `alipay_subscribe_demo.py`: Subscription management and usage tracking

### Use Cases

#### E-commerce Integration
- Product purchase workflows
- Order management and tracking
- Payment status monitoring
- Automated refund processing

#### AI Agent Paid Services
- Usage-based pricing models
- Subscription management automation

## Configuration

### Required Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `ALIPAY_APP_ID` | ✅ | Alipay application ID |
| `ALIPAY_PRIVATE_KEY` | ✅ | Application private key (RSA format) |
| `ALIPAY_PUBLIC_KEY` | ✅ | Alipay public key for signature verification |
| `SUBSCRIBE_PLAN_ID` | ✅ | Subscription plan ID |
| `X_AGENT_NAME` | ✅ | AI agent name for subscription tracking |

### Optional Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `AP_RETURN_URL` | - | Redirect URL after payment completion |
| `AP_NOTIFY_URL` | - | Asynchronous payment notification callback URL |
| `USE_TIMES` | 1 | Usage count deducted per service call |
| `AP_CURRENT_ENV` | - | Environment: `sandbox` or `production` |

## Demo Workflows

### Payment Demo Flow

1. **Order Generation**: AI agent creates orders based on user requests
2. **Payment Processing**: Generate appropriate payment links (mobile/desktop)
3. **Status Monitoring**: Check payment status and handle callbacks
4. **Refund Management**: Process refunds and track status

### Subscription Demo Flow

1. **Subscription Check**: Verify user subscription status
2. **Link Generation**: Create subscription purchase links as needed
3. **Service Usage**: Simulate AI service usage (poetry generation)
4. **Usage Tracking**: Record usage and deduct subscription quotas

### Core Component Demo

```python
# Payment processing
mobile_payment = MobileAlipayPayment()
payment_result = await mobile_payment.arun({
    "out_trade_no": "ORDER_001",
    "order_title": "AI Service",
    "total_amount": 99.99
})

# Subscription management
subscription_check = AlipaySubscribeCheckOrInitialize()
result = await subscription_check.arun({"uuid": "user_123"})

# Usage tracking
usage_tracker = AlipaySubscribeTimesSave()
usage_result = await usage_tracker.arun({
    "uuid": "user_123",
    "out_request_no": "usage_001"
})
```

## Testing

### Sandbox Environment

Use Alipay sandbox environment for testing:
1. Set `AP_CURRENT_ENV=sandbox`
2. Use sandbox application credentials
3. Test with sandbox accounts and payment methods

### Production Deployment

For production use:
1. Set `AP_CURRENT_ENV=production`
2. Use production application credentials
3. Configure proper callback URLs
4. Implement appropriate error handling and logging

## Security Notes

- Securely store private keys (use environment variables, not in code)
- Prevent prompt injection risks, prioritize workflow mode usage

## Troubleshooting

### Common Issues

1. **Invalid Signature**: Check private/public key configuration
2. **Environment Mismatch**: Ensure sandbox/production environment settings match
3. **Missing Dependencies**: Install `alipay-sdk-python` and `cryptography`
4. **API Timeout**: Implement retry logic for network issues

## Documentation Links

- [Alipay SDK Documentation](https://github.com/alipay/alipay-sdk-python)
- [Mobile Payment Integration](https://opendocs.alipay.com/open/203/105285)
- [Subscription Service API](https://opendocs.alipay.com/solution/0i40x9?pathHash=29e2835d)