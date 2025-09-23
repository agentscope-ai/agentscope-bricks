#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
支付宝订阅组件演示脚本

本演示展示了如何使用 AgentDev 的支付宝订阅组件进行：
1. 订阅状态检查
2. 订阅套餐初始化
3. 订阅计次记录
4. 订阅检查或初始化组合操作

运行前请确保：
- 已配置支付宝环境变量
- 已安装依赖包
"""
import asyncio
import os
import sys

# 添加项目根目录到 Python 路径
sys.path.insert(
    0,
    os.path.dirname(
        os.path.dirname(  # noqa: E402
            os.path.dirname(__file__),
        ),
    ),
)

from agentscope_bricks.components.alipay.subscribe import (  # noqa: E402
    AlipaySubscribeStatusCheck,
    AlipaySubscribeTimesSave,
    AlipaySubscribeCheckOrInitialize,
    SubscribeStatusCheckInput,
    SubscribeTimesSaveInput,
    SubscribeCheckOrInitializeInput,
)


def print_section(title: str):
    """打印分隔线"""
    print("\n" + "=" * 60)
    print(f"🎯 {title}")
    print("=" * 60)


async def demo_simple_scenarios(user_uuid: str):
    """
    生成诗歌的完整流程，包含订阅检查和计次

    第一部分：调用AlipaySubscribeCheckOrInitialize接口，校验状态
    第二部分：如果已订阅，调用大模型生成诗歌
    第三部分：调用AlipaySubscribeTimesSave接口，进行计次

    Args:
        user_uuid: 用户唯一标识
        plan_id: 订阅计划ID

    Returns:
        dict: 包含状态、诗歌内容、订阅链接等信息
    """
    print_section("📝 诗歌生成服务 - 订阅检查流程")

    try:
        # 第一部分：订阅状态检查
        print("\n📋 第一步：检查用户订阅状态...")
        check_or_init = AlipaySubscribeCheckOrInitialize()

        check_input = SubscribeCheckOrInitializeInput(uuid=user_uuid)

        check_result = await check_or_init._arun(check_input)

        # 如果未订阅，返回订阅链接并结束流程
        if not check_result.subscribe_flag:
            print("⚠️  用户未订阅，需要引导订阅")
            print(f"🔗 订阅链接: {check_result.subscribe_url}")
            return {
                "status": "INVALID",
                "subscribe_url": check_result.subscribe_url,
                "poem": None,
                "message": "请先完成订阅后再使用诗歌生成功能",
            }

        print(f"✅ 用户订阅状态: {check_result.subscribe_flag}")

        # 第二部分：生成诗歌
        print("\n🎨 第二步：生成诗歌...")

        # 模拟调用大模型生成诗歌
        # 实际项目中这里应该调用真实的大模型API
        poems = [
            "春风得意马蹄疾，一日看尽长安花。",
            "人生若只如初见，何事秋风悲画扇。",
            "山有木兮木有枝，心悦君兮君不知。",
            "曾经沧海难为水，除却巫山不是云。",
            "落红不是无情物，化作春泥更护花。",
        ]

        import random

        generated_poem = random.choice(poems)

        print(f"🖋️  生成的诗歌: {generated_poem}")

        # 第三部分：计次记录
        print("\n📊 第三步：记录使用次数...")

        times_save = AlipaySubscribeTimesSave()
        times_input = SubscribeTimesSaveInput(
            uuid=user_uuid,
            out_request_no=f"poem_{user_uuid}_"
            f"{int(asyncio.get_event_loop().time())}",
        )

        times_result = await times_save._arun(times_input)

        status_check = AlipaySubscribeStatusCheck()
        check_input = SubscribeStatusCheckInput(uuid=user_uuid)

        check_result = await status_check._arun(check_input)

        print(
            "测试状态校验:",
            check_result.subscribe_flag,
            "套餐信息:",
            check_result.subscribe_package,
        )

        if times_result.success:
            print("✅ 计次记录成功")
            return {
                "status": "SUCCESS",
                "poem": generated_poem,
                "subscribe_url": None,
                "message": "诗歌生成成功，已记录使用次数",
            }
        else:
            print("❌ 计次记录失败")
            return {
                "status": "COUNT_ERROR",
                "poem": generated_poem,
                "subscribe_url": None,
                "message": "诗歌生成成功，但计次记录失败",
            }

    except Exception as e:
        print(f"❌ 诗歌生成流程失败: {e}")
        return {
            "status": "ERROR",
            "poem": None,
            "subscribe_url": None,
            "message": f"服务异常: {str(e)}",
        }


async def main():
    """主函数：运行所有演示"""
    print("🚀 支付宝订阅组件演示开始")
    print("=" * 60)

    # 检查环境配置
    print("\n🔍 环境检查...")
    required_vars = [
        "ALIPAY_APP_ID",
        "ALIPAY_PRIVATE_KEY",
        "ALIPAY_PUBLIC_KEY",
    ]
    missing_vars = [var for var in required_vars if not os.getenv(var)]

    if missing_vars:
        print(f"⚠️  缺少环境变量: {', '.join(missing_vars)}")
        print("💡 请确保已配置支付宝相关环境变量")
        print("📖 参考: 支付宝配置说明.md")
    else:
        print("✅ 环境配置检查通过")

    # 运行所有演示
    await demo_simple_scenarios("123")

    print_section("演示完成")
    print("🎉 所有支付宝订阅组件演示已完成！")
    print("\n📚 使用建议:")
    print("1. 根据业务需求选择合适的组件")
    print("2. 确保用户ID和计划ID的一致性")
    print("3. 合理处理异常情况")
    print("4. 记录关键操作日志")


if __name__ == "__main__":
    # 运行演示
    asyncio.run(main())
