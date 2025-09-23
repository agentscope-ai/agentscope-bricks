# -*- coding: utf-8 -*-
import asyncio

from openai import OpenAI, AsyncOpenAI
import openai


class OpenAIResponseAPIClient:

    def __init__(self, base_url: str = "http://0.0.0.0:8090"):
        self.base_url = base_url
        self.api_url = f"{base_url}/compatible-mode/v1"

        self.openai_client = OpenAI(
            api_key="",
            base_url=self.api_url,
        )
        self.async_openai_client = AsyncOpenAI(
            api_key="",
            base_url=self.api_url,
        )

    def native_openai_api(self):
        """running OpenAI SDK responses.create streaming"""
        print("\n🌊 running OpenAI SDK responses.create streaming")
        print("=" * 50)

        try:
            openai.api_base = self.api_url
            openai.api_key = ""  # any value, since the service has
            # no identity service yet.

            print("📝 call openai.responses.create ...")
            response = self.openai_client.responses.create(
                model="gpt-4",
                input=[
                    {
                        "role": "user",
                        "content": "Tell me a short story about a robot "
                        "reading books.",
                    },
                ],
                stream=True,
            )
            event_count = 0
            for event in response:
                event_count += 1
                event_type = (
                    event.type
                    if hasattr(
                        event,
                        "type",
                    )
                    else "unknown"
                )
                print(f"   PACKAGE event {event_count}: {event_type}")

                # 打印事件详情
                if hasattr(event, "id"):
                    print(f"      ID: {event.id}")
                if hasattr(event, "created_at"):
                    print(f"      created: {event.created_at}")
                if hasattr(event, "model"):
                    print(f"      model: {event.model}")

                # 打印内容相关字段
                content_fields = ["content", "text", "item", "output"]
                for field in content_fields:
                    if hasattr(event, field):
                        value = getattr(event, field)
                        if value:
                            print(f"      {field}: {value}")

            print(f"   SUCCESS streaming，get {event_count} events")

        except Exception as e:
            print(f"ERROR calling failed with: {e}")
            import traceback

            traceback.print_exc()

    async def openai_sdk_responses_create_streaming(self):
        """running OpenAI SDK async responses.create streaming"""
        print("\n🌊 running  OpenAI SDK async responses.create streaming")
        print("=" * 50)

        try:
            # 设置 OpenAI 客户端指向本地服务
            openai.api_base = self.api_url
            openai.api_key = ""  # any value

            print("📝 call openai.responses.create (streaming)...")
            response = await self.async_openai_client.responses.create(
                model="gpt-4",
                input=[
                    {
                        "role": "user",
                        "content": "Tell me a short story about a robot "
                        "reading books.",
                    },
                ],
                stream=True,
            )

            event_count = 0
            async for event in response:
                event_count += 1
                event_type = (
                    event.type
                    if hasattr(
                        event,
                        "type",
                    )
                    else "unknown"
                )
                print(f"   PACKAGE events {event_count}: {event_type}")

                # 打印事件详情
                if hasattr(event, "id"):
                    print(f"      ID: {event.id}")
                if hasattr(event, "created_at"):
                    print(f"      created: {event.created_at}")
                if hasattr(event, "model"):
                    print(f"      model: {event.model}")

                # 打印内容相关字段
                content_fields = ["content", "text", "item", "output"]
                for field in content_fields:
                    if hasattr(event, field):
                        value = getattr(event, field)
                        if value:
                            print(f"      {field}: {value}")

            print(f"   SUCCESS streaming，get {event_count} events")

        except Exception as e:
            print(f"ERROR calling failed with: {e}")
            import traceback

            traceback.print_exc()


if __name__ == "__main__":
    response = OpenAIResponseAPIClient()
    response.native_openai_api()
    # asyncio.run(response.openai_sdk_responses_create_streaming())
