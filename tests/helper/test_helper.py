from typing import Any, Callable, Dict, Iterable, List, Set, Tuple

import pytest
from pytest import param as case
from pytest_mock import MockerFixture

from zulipterminal.api_types import Composition
from zulipterminal.helper import (
    Index,
    canonicalize_color,
    classify_unread_counts,
    display_error_if_present,
    get_unused_fence,
    hash_util_decode,
    index_messages,
    notify,
    notify_if_message_sent_outside_narrow,
    powerset,
)
from zulipterminal.platform_code import AllPlatforms, SupportedPlatforms


MODULE = "zulipterminal.helper"
MODEL = "zulipterminal.model.Model"


def test_index_messages_narrow_all_messages(
    mocker: MockerFixture,
    messages_successful_response: Dict[str, Any],
    index_all_messages: Index,
    initial_index: Index,
) -> None:
    messages = messages_successful_response["messages"]
    model = mocker.patch(MODEL + ".__init__", return_value=None)
    model.index = initial_index
    model.narrow = []
    assert index_messages(messages, model, model.index) == index_all_messages


def test_index_messages_narrow_stream(
    mocker: MockerFixture,
    messages_successful_response: Dict[str, Any],
    index_stream: Index,
    initial_index: Index,
) -> None:
    messages = messages_successful_response["messages"]
    model = mocker.patch(MODEL + ".__init__", return_value=None)
    model.index = initial_index
    model.narrow = [["stream", "PTEST"]]
    model.is_search_narrow.return_value = False
    model.stream_id = 205
    assert index_messages(messages, model, model.index) == index_stream


def test_index_messages_narrow_topic(
    mocker: MockerFixture,
    messages_successful_response: Dict[str, Any],
    index_topic: Index,
    initial_index: Index,
) -> None:
    messages = messages_successful_response["messages"]
    model = mocker.patch(MODEL + ".__init__", return_value=None)
    model.index = initial_index
    model.narrow = [["stream", "7"], ["topic", "Test"]]
    model.is_search_narrow.return_value = False
    model.stream_id = 205
    assert index_messages(messages, model, model.index) == index_topic


def test_index_messages_narrow_user(
    mocker: MockerFixture,
    messages_successful_response: Dict[str, Any],
    index_user: Index,
    initial_index: Index,
) -> None:
    messages = messages_successful_response["messages"]
    model = mocker.patch(MODEL + ".__init__", return_value=None)
    model.index = initial_index
    model.narrow = [["pm_with", "boo@zulip.com"]]
    model.is_search_narrow.return_value = False
    model.user_id = 5140
    model.user_dict = {
        "boo@zulip.com": {
            "user_id": 5179,
        }
    }
    assert index_messages(messages, model, model.index) == index_user


def test_index_messages_narrow_user_multiple(
    mocker: MockerFixture,
    messages_successful_response: Dict[str, Any],
    index_user_multiple: Index,
    initial_index: Index,
) -> None:
    messages = messages_successful_response["messages"]
    model = mocker.patch(MODEL + ".__init__", return_value=None)
    model.index = initial_index
    model.narrow = [["pm_with", "boo@zulip.com, bar@zulip.com"]]
    model.is_search_narrow.return_value = False
    model.user_id = 5140
    model.user_dict = {
        "boo@zulip.com": {
            "user_id": 5179,
        },
        "bar@zulip.com": {"user_id": 5180},
    }
    assert index_messages(messages, model, model.index) == index_user_multiple


@pytest.mark.parametrize(
    "edited_msgs",
    [
        {537286, 537287, 537288},
        {537286},
        {537287},
        {537288},
        {537286, 537287},
        {537286, 537288},
        {537287, 537288},
    ],
)
def test_index_edited_message(
    mocker: MockerFixture,
    messages_successful_response: Dict[str, Any],
    empty_index: Index,
    edited_msgs: Set[int],
    initial_index: Index,
) -> None:
    messages = messages_successful_response["messages"]
    for msg in messages:
        if msg["id"] in edited_msgs:
            msg["edit_history"] = []
    model = mocker.patch(MODEL + ".__init__", return_value=None)
    model.index = initial_index
    model.narrow = []

    expected_index: Dict[str, Any] = dict(
        empty_index, edited_messages=edited_msgs, all_msg_ids={537286, 537287, 537288}
    )
    for msg_id, msg in expected_index["messages"].items():
        if msg_id in edited_msgs:
            msg["edit_history"] = []

    assert index_messages(messages, model, model.index) == expected_index


@pytest.mark.parametrize(
    "msgs_with_stars",
    [
        {537286, 537287, 537288},
        {537286},
        {537287},
        {537288},
        {537286, 537287},
        {537286, 537288},
        {537287, 537288},
    ],
)
def test_index_starred(
    mocker: MockerFixture,
    messages_successful_response: Dict[str, Any],
    empty_index: Index,
    msgs_with_stars: Set[int],
    initial_index: Index,
) -> None:
    messages = messages_successful_response["messages"]
    for msg in messages:
        if msg["id"] in msgs_with_stars and "starred" not in msg["flags"]:
            msg["flags"].append("starred")

    model = mocker.patch(MODEL + ".__init__", return_value=None)
    model.index = initial_index
    model.narrow = [["is", "starred"]]
    model.is_search_narrow.return_value = False
    expected_index: Dict[str, Any] = dict(
        empty_index, private_msg_ids={537287, 537288}, starred_msg_ids=msgs_with_stars
    )
    for msg_id, msg in expected_index["messages"].items():
        if msg_id in msgs_with_stars and "starred" not in msg["flags"]:
            msg["flags"].append("starred")

    assert index_messages(messages, model, model.index) == expected_index


def test_index_mentioned_messages(
    mocker: MockerFixture,
    messages_successful_response: Dict[str, Any],
    empty_index: Index,
    mentioned_messages_combination: Tuple[Set[int], Set[int]],
    initial_index: Index,
) -> None:
    messages = messages_successful_response["messages"]
    mentioned_messages, wildcard_mentioned_messages = mentioned_messages_combination
    for msg in messages:
        if msg["id"] in mentioned_messages and "mentioned" not in msg["flags"]:
            msg["flags"].append("mentioned")
        if (
            msg["id"] in wildcard_mentioned_messages
            and "wildcard_mentioned" not in msg["flags"]
        ):
            msg["flags"].append("wildcard_mentioned")

    model = mocker.patch(MODEL + ".__init__", return_value=None)
    model.index = initial_index
    model.narrow = [["is", "mentioned"]]
    model.is_search_narrow.return_value = False
    expected_index: Dict[str, Any] = dict(
        empty_index,
        private_msg_ids={537287, 537288},
        mentioned_msg_ids=(mentioned_messages | wildcard_mentioned_messages),
    )

    for msg_id, msg in expected_index["messages"].items():
        if msg_id in mentioned_messages and "mentioned" not in msg["flags"]:
            msg["flags"].append("mentioned")
        if (
            msg["id"] in wildcard_mentioned_messages
            and "wildcard_mentioned" not in msg["flags"]
        ):
            msg["flags"].append("wildcard_mentioned")

    assert index_messages(messages, model, model.index) == expected_index


@pytest.mark.parametrize(
    "iterable, map_func, expected_powerset",
    [
        ([], set, [set()]),
        ([1], set, [set(), {1}]),
        ([1, 2], set, [set(), {1}, {2}, {1, 2}]),
        ([1, 2, 3], set, [set(), {1}, {2}, {3}, {1, 2}, {1, 3}, {2, 3}, {1, 2, 3}]),
        ([1, 2], tuple, [(), (1,), (2,), (1, 2)]),
    ],
)
def test_powerset(
    iterable: Iterable[Any],
    map_func: Callable[[Any], Any],
    expected_powerset: List[Any],
) -> None:
    assert powerset(iterable, map_func) == expected_powerset


@pytest.mark.parametrize(
    "muted_streams, muted_topics, vary_in_unreads",
    [
        (
            {99},
            [["Some general stream", "Some general unread topic"]],
            {
                "all_msg": 8,
                "streams": {99: 1},
                "unread_topics": {(99, "Some private unread topic"): 1},
                "all_mentions": 0,
            },
        ),
        (
            {1000},
            [["Secret stream", "Some private unread topic"]],
            {
                "all_msg": 8,
                "streams": {1000: 3},
                "unread_topics": {(1000, "Some general unread topic"): 3},
                "all_mentions": 0,
            },
        ),
        ({1}, [], {"all_mentions": 0}),
    ],
    ids=[
        "mute_private_stream_mute_general_stream_topic",
        "mute_general_stream_mute_private_stream_topic",
        "no_mute_some_other_stream_muted",
    ],
)
def test_classify_unread_counts(
    mocker: MockerFixture,
    initial_data: Dict[str, Any],
    stream_dict: Dict[int, Dict[str, Any]],
    classified_unread_counts: Dict[str, Any],
    muted_topics: List[List[str]],
    muted_streams: Set[int],
    vary_in_unreads: Dict[str, Any],
) -> None:
    model = mocker.Mock()
    model.stream_dict = stream_dict
    model.initial_data = initial_data
    model.is_muted_topic = mocker.Mock(
        side_effect=(
            lambda stream_id, topic: [model.stream_dict[stream_id]["name"], topic]
            in muted_topics
        )
    )
    model.muted_streams = muted_streams
    assert classify_unread_counts(model) == dict(
        classified_unread_counts, **vary_in_unreads
    )


@pytest.mark.parametrize(
    "color", ["#ffffff", "#f0f0f0", "#f0f1f2", "#fff", "#FFF", "#F3F5FA"]
)
def test_color_formats(mocker: MockerFixture, color: str) -> None:
    canon = canonicalize_color(color)
    assert canon == "#fff"


@pytest.mark.parametrize(
    "color", ["#", "#f", "#ff", "#ffff", "#fffff", "#fffffff", "#abj", "#398a0s"]
)
def test_invalid_color_format(mocker: MockerFixture, color: str) -> None:
    with pytest.raises(ValueError) as e:
        canon = canonicalize_color(color)
    assert str(e.value) == f'Unknown format for color "{color}"'


@pytest.mark.parametrize(
    "PLATFORM, is_notification_sent",
    [
        # PLATFORM: Literal["WSL", "MacOS", "Linux", "unsupported"]
        pytest.param(
            "WSL",
            True,
            marks=pytest.mark.xfail(reason="WSL notify disabled"),
        ),
        ("MacOS", True),
        ("Linux", True),
        ("unsupported", False),  # Unsupported OS
    ],
)
def test_notify(
    mocker: MockerFixture, PLATFORM: AllPlatforms, is_notification_sent: bool
) -> None:
    title = "Author"
    text = "Hello!"
    mocker.patch(MODULE + ".PLATFORM", PLATFORM)
    subprocess = mocker.patch(MODULE + ".subprocess")
    notify(title, text)
    assert subprocess.run.called == is_notification_sent


@pytest.mark.parametrize(
    "text",
    ["x", "Spaced text.", "'", '"'],
    ids=["x", "spaced_text", "single", "double"],
)
@pytest.mark.parametrize(
    "title",
    ["X", "Spaced title", "'", '"'],
    ids=["X", "spaced_title", "single", "double"],
)
@pytest.mark.parametrize(
    "PLATFORM, cmd_length",
    [
        ("Linux", 4),
        ("MacOS", 10),
        pytest.param("WSL", 2, marks=pytest.mark.xfail(reason="WSL notify disabled")),
    ],
)
def test_notify_quotes(
    monkeypatch: pytest.MonkeyPatch,
    mocker: MockerFixture,
    PLATFORM: SupportedPlatforms,
    cmd_length: int,
    title: str,
    text: str,
) -> None:
    subprocess = mocker.patch(MODULE + ".subprocess")
    platform = mocker.patch(MODULE + ".PLATFORM", PLATFORM)

    notify(title, text)

    params = subprocess.run.call_args_list
    assert len(params) == 1  # One external run call
    assert len(params[0][0][0]) == cmd_length

    # NOTE: If there is a quoting error, we may get a ValueError too


@pytest.mark.parametrize(
    "response, footer_updated",
    [
        ({"result": "error", "msg": "Request failed."}, True),
        ({"result": "success", "msg": "msg content"}, False),
    ],
)
def test_display_error_if_present(
    mocker: MockerFixture, response: Dict[str, str], footer_updated: bool
) -> None:
    controller = mocker.Mock()
    report_error = controller.report_error

    display_error_if_present(response, controller)

    if footer_updated:
        report_error.assert_called_once_with(response["msg"])
    else:
        report_error.assert_not_called()


@pytest.mark.parametrize(
    "req, narrow, footer_updated",
    [
        case(
            {"type": "private", "to": ["foo@gmail.com"], "content": "bar"},
            [["is", "private"]],
            False,
            id="all_private__pm__not_notified",
        ),
        case(
            {
                "type": "private",
                "to": ["foo@zulip.com", "bar@zulip.com"],
                "content": "Hi",
            },
            [["pm_with", "foo@zulip.com, bar@zulip.com"]],
            False,
            id="group_private_conv__same_group_pm__not_notified",
        ),
        case(
            {
                "type": "private",
                "to": ["user@abc.com", "user@chat.com"],
                "content": "Hi",
            },
            [["pm_with", "user@0abc.com"]],
            True,
            id="private_conv__other_pm__notified",
        ),
        case(
            {"type": "private", "to": ["bar-bar@foo.com"], "content": ":party_parrot:"},
            [["pm_with", "user@abc.com, user@chat.com, bar-bar@foo.com"]],
            True,
            id="private_conv__other_pm2__notified",
        ),
        case(
            {"type": "stream", "to": "ZT", "subject": "1", "content": "foo"},
            [["stream", "ZT"], ["topic", "1"]],
            False,
            id="stream_topic__same_stream_topic__not_notified",
        ),
        case(
            {"type": "stream", "to": "here", "subject": "pytest", "content": "py"},
            [["stream", "test here"]],
            True,
            id="stream__different_stream__notified",
        ),
        case(
            {
                "type": "stream",
                "to": "|new_stream|",
                "subject": "(no topic)",
                "content": "Hi `|new_stream|`",
            },
            [],
            False,
            id="all_messages__stream__not_notified",
        ),
        case(
            {
                "type": "stream",
                "to": "zulip-terminal",
                "subject": "issue#T781",
                "content": "Added tests",
            },
            [["is", "starred"]],
            True,
            id="starred__stream__notified",
        ),
        case(
            {"type": "private", "to": ["2@aBd%8@random.com"], "content": "fist_bump"},
            [["is", "mentioned"]],
            True,
            id="mentioned__private_no_mention__notified",
        ),
        case(
            {"type": "stream", "to": "PTEST", "subject": "TEST", "content": "Test"},
            [["stream", "PTEST"], ["search", "FOO"]],
            True,
            id="stream_search__stream_match_not_search__notified",
        ),
    ],
)
def test_notify_if_message_sent_outside_narrow(
    mocker: MockerFixture,
    req: Composition,
    narrow: List[Any],
    footer_updated: bool,
) -> None:
    controller = mocker.Mock()
    report_success = controller.report_success
    controller.model.narrow = narrow

    notify_if_message_sent_outside_narrow(req, controller)

    if footer_updated:
        report_success.assert_called_once_with(
            "Message is sent outside of current narrow."
        )
    else:
        report_success.assert_not_called()


@pytest.mark.parametrize(
    "quoted_string, expected_unquoted_string",
    [
        ("(no.20topic)", "(no topic)"),
        (".3Cstrong.3Exss.3C.2Fstrong.3E", "<strong>xss</strong>"),
        (".23test-here.20.23T1.20.23T2.20.23T3", "#test-here #T1 #T2 #T3"),
        (".2Edot", ".dot"),
        (".3Aparty_parrot.3A", ":party_parrot:"),
    ],
)
def test_hash_util_decode(quoted_string: str, expected_unquoted_string: str) -> None:
    return_value = hash_util_decode(quoted_string)

    assert return_value == expected_unquoted_string


@pytest.mark.parametrize(
    "message_content, expected_fence",
    [
        ("Hi `test_here`", "```"),
        ("```quote\nZ(dot)T(dot)\n```\nempty body", "````"),
        ("```python\ndef zulip():\n  pass\n```\ncode-block", "````"),
        ("````\ndont_know_what_this_does\n````", "`````"),
        ("````quote\n```\ndef zulip():\n  pass\n```\n````", "`````"),
        ("```math\n\\int_a^b f(t)\\, dt = F(b) - F(a)\n```", "````"),
        ("```spoiler Header Text\nSpoiler content\n```", "````"),
    ],
    ids=[
        "inline_code",
        "block_quote",
        "block_code_python",
        "block_code",
        "block_code_quoted",
        "block_math",
        "block_spoiler",
    ],
)
def test_get_unused_fence(message_content: str, expected_fence: str) -> None:
    generated_fence = get_unused_fence(message_content)

    assert generated_fence == expected_fence
