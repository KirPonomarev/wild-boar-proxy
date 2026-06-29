import unittest

from wild_boar_proxy.custom_codex_physical_observer import (
    observe_visible_output,
    output_after_worked_segment,
)


class CustomCodexPhysicalObserverTests(unittest.TestCase):
    def test_native_exact_requires_more_than_prompt_echo(self) -> None:
        packet = observe_visible_output(
            before_text="",
            after_text="Codex: ответь ровно TOKEN",
            prompt="Codex: ответь ровно TOKEN",
            expected_text="TOKEN",
            mode="native",
        ).as_packet()

        self.assertEqual(packet["status"], "blocked")
        self.assertEqual(packet["machine_error_code"], "CUSTOM_PHYSICAL_PROMPT_ECHO_ONLY")
        self.assertFalse(packet["custom_response_bound_to_request"])

    def test_native_exact_accepts_prompt_plus_visible_response(self) -> None:
        packet = observe_visible_output(
            before_text="",
            after_text="Codex: ответь ровно TOKEN\n\nTOKEN",
            prompt="Codex: ответь ровно TOKEN",
            expected_text="TOKEN",
            mode="native",
        ).as_packet()

        self.assertEqual(packet["status"], "ok")
        self.assertTrue(packet["custom_response_bound_to_request"])

    def test_api_exact_rejects_command_echo_without_output_segment(self) -> None:
        packet = observe_visible_output(
            before_text="",
            after_text=(
                "Builder: ответь ровно TOKEN\n"
                "Выполнена команда WBP_ROUTER_PROMPT='Builder: ответь ровно TOKEN'\n"
                "Работал на протяжении 6s\n\nFAIL something_else"
            ),
            prompt="Builder: ответь ровно TOKEN",
            expected_text="TOKEN",
            mode="api",
        ).as_packet()

        self.assertEqual(packet["status"], "blocked")
        self.assertEqual(packet["machine_error_code"], "CUSTOM_PHYSICAL_COMMAND_ECHO_ONLY")
        self.assertFalse(packet["output_after_worked_contains_expected_text"])

    def test_api_exact_accepts_output_after_worked_segment(self) -> None:
        packet = observe_visible_output(
            before_text="",
            after_text=(
                "Builder: ответь ровно TOKEN\n"
                "Выполнена команда WBP_ROUTER_PROMPT='Builder: ответь ровно TOKEN'\n"
                "Работал на протяжении 6s\n\nTOKEN"
            ),
            prompt="Builder: ответь ровно TOKEN",
            expected_text="TOKEN",
            mode="api",
        ).as_packet()

        self.assertEqual(packet["status"], "ok")
        self.assertTrue(packet["output_after_worked_contains_expected_text"])

    def test_multiline_prompt_split_into_recommendations_is_blocked(self) -> None:
        packet = observe_visible_output(
            before_text="",
            after_text=(
                "После green ответь ровно TOKEN\n"
                "Отправить как рекомендацию\n"
                "TOKEN"
            ),
            prompt="line one\nПосле green ответь ровно TOKEN",
            expected_text="TOKEN",
            mode="native",
        ).as_packet()

        self.assertEqual(packet["status"], "blocked")
        self.assertEqual(
            packet["machine_error_code"],
            "CUSTOM_PHYSICAL_PROMPT_SPLIT_INTO_RECOMMENDATIONS",
        )

    def test_output_after_worked_uses_last_run_segment(self) -> None:
        self.assertEqual(
            output_after_worked_segment(
                "Работал на протяжении 1s\nOLD\nРаботал на протяжении 2s\nNEW"
            ),
            "Работал на протяжении 2s\nNEW",
        )


if __name__ == "__main__":
    unittest.main()
