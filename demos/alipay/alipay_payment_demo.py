# -*- coding: utf-8 -*-
"""
支付宝支付组件AI智能体使用示例

本文件演示了如何在AI智能体中使用支付宝支付组件，

前提条件:
1. 安装依赖:
   pip install alipay-sdk-python cryptography
2. 配置环境变量:
   - ALIPAY_APP_ID: 支付宝应用ID
   - ALIPAY_PRIVATE_KEY: 应用私钥
   - ALIPAY_PUBLIC_KEY: 支付宝公钥
   - AP_CURRENT_ENV: "sandbox" 或 "production"
"""

import asyncio
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from agentscope_bricks.base.component import Component
from agentscope_bricks.components.alipay.payment import (
    MobileAlipayPayment,
    WebPageAlipayPayment,
    MobilePaymentInput,
    WebPagePaymentInput
)


# ===================== 订单管理系统 =====================

# 订单存储 - 模拟数据库
order_storage = {}


class OrderGeneratorInput(BaseModel):
    """订单生成输入"""
    product_name: str = Field(..., description="商品名称")
    amount: float = Field(..., description="商品金额")
    product_type: str = Field(
        "course", description="商品类型：course, vip, service"
    )
    platform: str = Field(
        "mobile", description="支付平台：mobile 或 webpage"
    )


class OrderGeneratorOutput(BaseModel):
    """订单生成输出"""
    order_no: str = Field(..., description="生成的订单号")
    order_info: str = Field(..., description="订单信息")


class OrderGenerator(Component[OrderGeneratorInput, OrderGeneratorOutput]):
    """商户订单生成器 - 模拟商户订单系统"""

    name: str = "order_generator"
    description: str = (
        "商户订单系统，负责生成业务订单号。"
        "根据商品类型和信息生成对应的订单号，"
        "并存储订单详情。"
    )

    async def _arun(
        self, args: OrderGeneratorInput, **kwargs: Any
    ) -> OrderGeneratorOutput:
        """生成订单号并存储订单信息"""
        _ = kwargs  # 忽略未使用的参数
        # 根据商品类型生成订单前缀
        type_prefix = {
            "course": "COURSE",
            "vip": "VIP",
            "service": "SERVICE"
        }.get(args.product_type, "ORDER")

        # 生成订单号
        timestamp = datetime.now().strftime('%Y%m%d')
        order_count = len([
            k for k in order_storage.keys() if k.startswith(type_prefix)
        ])
        order_no = (
            f"{type_prefix}_{timestamp}_{order_count + 1:03d}"
        )

        # 存储订单信息
        order_info = {
            "order_no": order_no,
            "product_name": args.product_name,
            "amount": args.amount,
            "product_type": args.product_type,
            "platform": args.platform,
            "status": "created",
            "created_at": datetime.now().isoformat()
        }
        order_storage[order_no] = order_info

        result_info = (
            f"订单创建成功！订单号: {order_no}, "
            f"商品: {args.product_name}, 金额: ¥{args.amount}"
        )

        return OrderGeneratorOutput(
            order_no=order_no,
            order_info=result_info
        )


def find_order_by_product(product_keywords: str) -> str:
    """根据商品关键词查找订单号"""
    for order_no, order_info in order_storage.items():
        if any(
            keyword.lower() in order_info["product_name"].lower()
            for keyword in product_keywords.split()
        ):
            return order_no
    return None


# ===================== 快速创建支付链接工具 =====================

async def create_quick_payment(
    amount: float,
    title: str = "商品购买",
    platform: str = "mobile",
    order_no: str = None
):
    """
    快速创建支付链接的工具函数

    Args:
        amount: 支付金额
        title: 订单标题
        platform: 支付平台 mobile 或 webpage
        order_no: 商户订单号
    """

    try:
        if platform == "mobile":
            payment = MobileAlipayPayment()
            input_data = MobilePaymentInput(
                out_trade_no=order_no,
                order_title=title,
                total_amount=amount
            )
        else:
            payment = WebPageAlipayPayment()
            input_data = WebPagePaymentInput(
                out_trade_no=order_no,
                order_title=title,
                total_amount=amount
            )

        result = await payment._arun(input_data)
        print("✅ 支付链接创建成功")
        print(f"📱 订单号: {order_no}")
        print(f"💰 金额: ¥{amount}")
        print(f"🔗 {result.result}")
        return result.result
    except Exception as e:
        error_msg = f"❌ 创建支付链接失败: {str(e)}"
        print(error_msg)
        return error_msg


# ===================== AI智能体场景演示 =====================

async def demo_simple_scenarios():
    """简单场景演示 - 展示完整的业务流程"""
    print("=" * 50)
    print("🤖 支付宝AI智能体 - 简单场景演示")
    print("=" * 50)
    print("💡 演示：先生成订单号，再创建支付链接")

    # 场景1: 完整流程 - 生成订单 + 创建手机支付
    print("\n📱 场景1: Python课程手机支付完整流程")
    print("  步骤1: 生成订单号")
    order_gen = OrderGenerator()
    order_result = await order_gen._arun(OrderGeneratorInput(
        product_name="Python入门课程",
        amount=20.0,
        product_type="course",
        platform="mobile"
    ))
    print(f"  ✅ {order_result.order_info}")

    print("  步骤2: 创建支付链接")
    await create_quick_payment(
        20.0, "Python入门课程", "mobile", order_result.order_no
    )

    # 场景2: 完整流程 - 生成订单 + 创建网页支付
    print("\n💻 场景2: VIP会员网页支付完整流程")
    print("  步骤1: 生成订单号")
    order_result2 = await order_gen._arun(OrderGeneratorInput(
        product_name="VIP年度会员",
        amount=99.0,
        product_type="vip",
        platform="webpage"
    ))
    print(f"  ✅ {order_result2.order_info}")

    print("  步骤2: 创建支付链接")
    await create_quick_payment(
        99.0, "VIP年度会员", "webpage", order_result2.order_no
    )

    print("\n🎯 简单场景演示完成 - 展示了标准的业务流程")


# ===================== 主函数 =====================

async def main():
    """主演示函数"""
    print("🎯 支付宝支付组件AI智能体演示")
    print(
        "🔄 业务流程: 订单生成 → 支付创建 → 状态查询"
    )

    # 工作流方式（建议使用）
    await demo_simple_scenarios()

    print("\n" + "=" * 50)
    print("✅ 演示完成!")
    print("=" * 50)


if __name__ == "__main__":
    print("""
🚀 使用说明:

1. 环境配置:
   - 支付宝沙箱/生产环境配置

2. 运行模式:
   - 直接运行: python alipay_payment_demo.py
   - 包含简单支付创建

3. 支持场景:
   - ⚙️ 商户订单系统集成演示
   - 🤖 AI智能体多步骤工作流(系统提示词约束)
   - 🗣️ 自然语言支付请求处理
   - 🔄 业务流程: 订单生成 → 支付创建 → 状态查询
    """)

    asyncio.run(main())
