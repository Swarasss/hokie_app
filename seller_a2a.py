import asyncio
import uuid

from a2a.server.agent_execution.agent_executor import AgentExecutor
from a2a.types import Message, Part, Role


class SellerAgentExecutor(AgentExecutor):

    def __init__(self, generate_response):
        self.generate_response = generate_response

    async def execute(self, context, event_queue):
        # Read message sent by Buyer over A2A
        user_text = context.get_user_input()

        # Run Gemini without blocking the async A2A server
        seller_text = await asyncio.to_thread(
            self.generate_response,
            user_text
        )

        reply = Message(
            message_id=str(uuid.uuid4()),
            role=Role.ROLE_AGENT,
            parts=[
                Part(text=seller_text)
            ],
        )

        if context.context_id:
            reply.context_id = context.context_id

        if context.task_id:
            reply.task_id = context.task_id

        await event_queue.enqueue_event(reply)

    async def cancel(self, context, event_queue):
        return