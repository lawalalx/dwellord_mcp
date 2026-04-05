# banking_mcp_client_async.py
import asyncio
import json
import os
from contextlib import AsyncExitStack

from mcp import ClientSession
from mcp.client.sse import sse_client


from dotenv import load_dotenv
from front.app.agent.model import llm
from config import settings

load_dotenv()  # Load OPENAI_API_KEY or GROQ_API_KEY, MCP_SSE_URL

class BankingMCPClient:
    def __init__(self):
        self.session = None
        self.exit_stack = AsyncExitStack()
        self.available_tools = []
        self.messages = []
        self.llm = llm

    async def connect_to_mcp(self, mcp_url: str):
        print("Connecting to MCP server via SSE...")
        self._streams_context = sse_client(url=mcp_url)
        streams = await self._streams_context.__aenter__()

        self._session_context = ClientSession(*streams)
        self.session: ClientSession = await self._session_context.__aenter__()

        # Initialize session & get tools/prompts
        await self.session.initialize()
        await self.get_available_tools()
        await self.get_initial_prompts()

    async def cleanup(self):
        if self._session_context:
            await self._session_context.__aexit__(None, None, None)
        if self._streams_context:
            await self._streams_context.__aexit__(None, None, None)

    async def get_initial_prompts(self):
        prompt = await self.session.get_prompt("get_initial_prompts")
        self.messages = [
            {"role": m.role, "content": m.content.text} for m in prompt.messages
        ]

    async def get_available_tools(self):
        response = await self.session.list_tools()
        self.available_tools = [
            {
                "type": "function",
                "function": {
                    "name": t.name,
                    "description": t.description,
                    "parameters": t.inputSchema,
                },
                "strict": True,
            }
            for t in response.tools
        ]
        print("Available tools:", [t["function"]["name"] for t in self.available_tools])

    async def call_llm(self) -> str:
        # LangChain Groq client call
        response = self.llm.chat(
            messages=self.messages,
            tools=self.available_tools,
            stream=False,  # set True for streaming tokens
        )
        return response

    async def process_llm_response(self, llm_response) -> str:
        """
        Checks if the LLM wants to call a tool and executes it.
        Loops until LLM returns a final answer.
        """
        if llm_response.tool_calls:
            for call in llm_response.tool_calls:
                tool_name = call.function.name
                args = json.loads(call.function.arguments)
                print(f"[Calling tool: {tool_name} with args {args}]")
                result = await self.session.call_tool(tool_name, args)
                print(f"[Tool result: {result.content}]")

                # Add tool result back to messages
                self.messages.append({
                    "role": "tool",
                    "tool_call_id": call.id,
                    "content": result.content,
                })

            # Recursive call until LLM finishes
            next_response = await self.call_llm()
            return await self.process_llm_response(next_response)

        else:
            # LLM finished generating answer
            self.messages.append({
                "role": "assistant",
                "content": llm_response.content
            })
            return llm_response.content

    async def process_query(self, query: str) -> str:
        self.messages.append({"role": "user", "content": query})
        llm_response = await self.call_llm()
        return await self.process_llm_response(llm_response)

    async def chat_loop(self):
        print("\nBanking MCP Client Started! Type 'quit' to exit.")
        while True:
            query = input("\nQuery: ").strip()
            if query.lower() == "quit":
                break
            if query:
                try:
                    answer = await self.process_query(query)
                    print("\nAssistant:", answer)
                except Exception as e:
                    print("Error:", str(e))


async def main():
    client = BankingMCPClient()
    try:
        await client.connect_to_mcp(settings.MCP_SSE_URL)
        await client.chat_loop()
    finally:
        await client.cleanup()


if __name__ == "__main__":
    asyncio.run(main())
