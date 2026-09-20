import uuid

from a2a.server.agent_execution.agent_executor import AgentExecutor
from a2a.types import Message, Part, Role


class SellerAgentExecutor(AgentExecutor):

    async def execute(self, context, event_queue):
        # Read the text sent by the other A2A agent
        user_text = context.get_user_input()

        reply = Message(
            message_id=str(uuid.uuid4()),
            role=Role.ROLE_AGENT,
            parts=[
                Part(
                    text=f"Seller Agent received via A2A: {user_text}"
                )
            ],
        )

        # Preserve A2A conversation/task IDs when present
        if context.context_id:
            reply.context_id = context.context_id

        if context.task_id:
            reply.task_id = context.task_id

        # Send the A2A response
        await event_queue.enqueue_event(reply)

    async def cancel(self, context, event_queue):
        return