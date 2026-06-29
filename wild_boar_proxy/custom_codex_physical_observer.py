"""Visible-output observer for physical Custom Codex smoke runs."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


ObserverMode = Literal["native", "api", "fail_closed", "auto"]


@dataclass(frozen=True)
class VisibleOutputObservation:
    status: str
    machine_error_code: str
    expected_text_observed: bool
    custom_response_bound_to_request: bool
    prompt_echo_only: bool
    command_echo_only: bool
    before_count: int
    after_count: int
    observed_count_delta: int
    required_count_delta: int
    prompt_contains_expected_text: bool
    output_after_worked_contains_expected_text: bool
    run_active: bool
    queued_recommendations_observed: bool

    def as_packet(self) -> dict[str, object]:
        return {
            "status": self.status,
            "machine_error_code": self.machine_error_code,
            "expected_text_observed": self.expected_text_observed,
            "custom_response_bound_to_request": self.custom_response_bound_to_request,
            "prompt_echo_only": self.prompt_echo_only,
            "command_echo_only": self.command_echo_only,
            "before_count": self.before_count,
            "after_count": self.after_count,
            "observed_count_delta": self.observed_count_delta,
            "required_count_delta": self.required_count_delta,
            "prompt_contains_expected_text": self.prompt_contains_expected_text,
            "output_after_worked_contains_expected_text": (
                self.output_after_worked_contains_expected_text
            ),
            "run_active": self.run_active,
            "queued_recommendations_observed": self.queued_recommendations_observed,
        }


def count_occurrences(text: str, needle: str) -> int:
    if not needle:
        return 0
    count = 0
    start = 0
    while True:
        index = text.find(needle, start)
        if index < 0:
            return count
        count += 1
        start = index + len(needle)


def visible_text_delta(before_text: str, after_text: str) -> str:
    if after_text.startswith(before_text):
        return after_text[len(before_text) :]
    return after_text


def output_after_worked_segment(delta_text: str) -> str:
    markers = ("Работал", "Worked")
    positions = [delta_text.rfind(marker) for marker in markers]
    position = max(positions)
    if position < 0:
        return ""
    return delta_text[position:]


def observe_visible_output(
    *,
    before_text: str,
    after_text: str,
    prompt: str,
    expected_text: str,
    mode: ObserverMode = "auto",
    run_active: bool = False,
) -> VisibleOutputObservation:
    before_count = count_occurrences(before_text, expected_text)
    after_count = count_occurrences(after_text, expected_text)
    delta_count = max(0, after_count - before_count)
    prompt_contains_expected = expected_text in prompt
    required_delta = 2 if prompt_contains_expected else 1
    delta_text = visible_text_delta(before_text, after_text)
    after_worked = output_after_worked_segment(delta_text)
    after_worked_contains_expected = expected_text in after_worked
    queued_recommendations_observed = "Отправить как рекомендацию" in delta_text

    prompt_echo_only = bool(prompt_contains_expected and delta_count == 1)
    command_echo_only = bool(
        mode in {"api", "auto"}
        and prompt_contains_expected
        and delta_count >= required_delta
        and "WBP_ROUTER_PROMPT" in delta_text
        and not after_worked_contains_expected
    )

    if run_active:
        return VisibleOutputObservation(
            status="blocked",
            machine_error_code="CUSTOM_PHYSICAL_RUN_STILL_ACTIVE",
            expected_text_observed=False,
            custom_response_bound_to_request=False,
            prompt_echo_only=prompt_echo_only,
            command_echo_only=command_echo_only,
            before_count=before_count,
            after_count=after_count,
            observed_count_delta=delta_count,
            required_count_delta=required_delta,
            prompt_contains_expected_text=prompt_contains_expected,
            output_after_worked_contains_expected_text=after_worked_contains_expected,
            run_active=True,
            queued_recommendations_observed=queued_recommendations_observed,
        )

    if mode == "api":
        ok = after_worked_contains_expected
    elif mode == "native":
        ok = delta_count >= required_delta and not queued_recommendations_observed
    elif mode == "fail_closed":
        ok = delta_count >= required_delta
    else:
        ok = (
            after_worked_contains_expected
            if "WBP_ROUTER_PROMPT" in delta_text
            else delta_count >= required_delta and not queued_recommendations_observed
        )

    if ok:
        machine_error_code = "OK"
    elif prompt_echo_only:
        machine_error_code = "CUSTOM_PHYSICAL_PROMPT_ECHO_ONLY"
    elif command_echo_only:
        machine_error_code = "CUSTOM_PHYSICAL_COMMAND_ECHO_ONLY"
    elif queued_recommendations_observed:
        machine_error_code = "CUSTOM_PHYSICAL_PROMPT_SPLIT_INTO_RECOMMENDATIONS"
    else:
        machine_error_code = "CUSTOM_PHYSICAL_EXPECTED_TEXT_NOT_OBSERVED"

    return VisibleOutputObservation(
        status="ok" if ok else "blocked",
        machine_error_code=machine_error_code,
        expected_text_observed=ok,
        custom_response_bound_to_request=ok,
        prompt_echo_only=prompt_echo_only,
        command_echo_only=command_echo_only,
        before_count=before_count,
        after_count=after_count,
        observed_count_delta=delta_count,
        required_count_delta=required_delta,
        prompt_contains_expected_text=prompt_contains_expected,
        output_after_worked_contains_expected_text=after_worked_contains_expected,
        run_active=False,
        queued_recommendations_observed=queued_recommendations_observed,
    )
