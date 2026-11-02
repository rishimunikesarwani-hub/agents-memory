"""Check message flow without sending requests to OpenAI."""

import io
import unittest
from contextlib import redirect_stdout
from unittest.mock import Mock, patch

from langchain_core.messages import AIMessage, HumanMessage

import demo


class DemoTest(unittest.TestCase):
    def test_input_history_reset_and_api_response_display(self):
        fact = "My project code is blue-719."
        question = "What is my project code?"
        model = Mock(spec=demo.ChatOpenAI)
        model.invoke.side_effect = [
            AIMessage(
                content=f"Test response {number}",
                response_metadata={"id": f"test-id-{number}"},
                usage_metadata={"input_tokens": 11, "output_tokens": 7, "total_tokens": 18},
            )
            for number in range(6)
        ]
        output = io.StringIO()
        with (
            patch("builtins.input", side_effect=["", fact, question, "/reset", question, "/quit"]),
            redirect_stdout(output),
        ):
            demo.run_demo(model)

        requests = [call.args[0] for call in model.invoke.call_args_list]
        self.assertEqual([len(messages) - 1 for messages in requests], [1, 1, 1, 3, 1, 1])
        for without, with_memory in zip(requests[::2], requests[1::2]):
            self.assertEqual(without[-1].content, with_memory[-1].content)
            self.assertEqual(without[0].content, with_memory[0].content)
        self.assertNotIn(fact, [message.content for message in requests[2]])
        self.assertIn(fact, [message.content for message in requests[3]])
        self.assertNotIn(fact, [message.content for message in requests[5]])
        self.assertTrue(all(isinstance(messages[-1], HumanMessage) for messages in requests))
        self.assertIn("AI: Test response 5", output.getvalue())
        self.assertIn("OpenAI response ID: test-id-5", output.getvalue())
        self.assertIn("Tokens: input=11, output=7", output.getvalue())


if __name__ == "__main__":
    unittest.main()
