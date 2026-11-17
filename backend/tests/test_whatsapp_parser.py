"""
WhatsApp export parser: formats (Android, iOS, FR, EN), date order rule,
multi-line messages, attachments, system messages and error counting.
"""
from datetime import datetime

import pytest

from mcp_servers.whatsapp_connector import WhatsAppConnector
from mcp_servers.whatsapp_parser import ParsedMessage, export_messages, is_attachment, parse_export

NOV_1_0924 = datetime(2026, 11, 1, 9, 24, 0)


@pytest.mark.parametrize(
    "line, default_order",
    [
        ("[01/11/2026, 09:24:00] Client A: perceuse 500W", "dmy"),
        ("[01/11/2026 09:24:00] Client A: perceuse 500W", "dmy"),
        ("01/11/2026 09:24 - Client A: perceuse 500W", "dmy"),
        ("01/11/2026, 09:24 - Client A: perceuse 500W", "dmy"),
        ("[11/1/26, 9:24:00 AM] Client A: perceuse 500W", "mdy"),
        ("11/1/26, 9:24 AM - Client A: perceuse 500W", "mdy"),
        ("11/1/26, 9:24 am - Client A: perceuse 500W", "mdy"),
        ("[11/1/26, 9:24:00\u202fAM] Client A: perceuse 500W", "mdy"),
        ("[11/1/26, 9:24:00 a.m.] Client A: perceuse 500W", "mdy"),
        ("\u200e[01/11/2026, 09:24:00] Client A: perceuse 500W", "dmy"),
        ("[01.11.2026, 09:24:00] Client A: perceuse 500W", "dmy"),
    ],
)
def test_should_read_the_same_message_when_the_line_uses_any_supported_format(line, default_order):
    result = parse_export([line], default_order)

    assert result.messages == [ParsedMessage(NOV_1_0924, "Client A", "perceuse 500W")]
    assert (result.parse_errors, result.system_skipped) == (0, 0)


@pytest.mark.parametrize(
    "line, hour",
    [
        ("[11/1/26, 12:05:00 AM] Client A: x", 0),
        ("[11/1/26, 12:05:00 PM] Client A: x", 12),
        ("[11/1/26, 11:05:00 PM] Client A: x", 23),
    ],
)
def test_should_convert_the_12_hour_clock_when_the_line_has_am_or_pm(line, hour):
    result = parse_export([line], "mdy")

    assert result.messages[0].timestamp.hour == hour


def test_should_append_continuation_lines_to_the_message_when_a_text_spans_several_lines():
    lines = [
        "[01/11/2026, 09:24:00] Client A: Bonjour,",
        "il me faut:",
        "",
        "du ciment 50 kg",
        "[01/11/2026, 09:30:00] Client B: merci",
    ]

    result = parse_export(lines)

    assert [m.text for m in result.messages] == ["Bonjour,\nil me faut:\n\ndu ciment 50 kg", "merci"]
    assert result.parse_errors == 0


def test_should_number_a_message_by_its_first_line_when_it_spans_several_lines():
    lines = [
        "[01/11/2026, 09:24:00] Client A: un",
        "deux",
        "[01/11/2026, 09:30:00] Client B: trois",
    ]

    result = parse_export(lines)

    assert [m.line_no for m in result.messages] == [1, 3]


@pytest.mark.parametrize(
    "text",
    [
        "<Media omitted>",
        "<Médias omis>",
        "<médias omis>",
        "image omitted",
        "video omitted",
        "vidéo omise",
        "sticker omitted",
        "\u200e<attached: 00000012-PHOTO-2026-11-01-09-24-00.jpg>",
        "<attached: 00000012-PHOTO.jpg>",
        "IMG-20261101-WA0001.jpg (file attached)",
        "IMG-20261101-WA0001.jpg (fichier joint)",
        "<Media omitted>\nvoici la photo du mur",
    ],
)
def test_should_flag_the_message_as_attachment_when_the_text_is_a_media_placeholder(text):
    assert is_attachment(text)


@pytest.mark.parametrize("text", ["perceuse 500W", "image du ciment 50 kg", "omitted", "voici <Media omitted>"])
def test_should_not_flag_the_message_as_attachment_when_the_text_is_written(text):
    assert not is_attachment(text)


def test_should_skip_and_count_apart_when_a_line_is_a_system_message():
    lines = [
        "[01/11/2026, 09:00:00] Les messages et les appels sont chiffrés de bout en bout.",
        "Seules les personnes de cette discussion peuvent les lire.",
        "01/11/2026 09:10 - Client B a rejoint avec le lien d'invitation",
        "[01/11/2026, 09:24:00] Client A: perceuse 500W",
        "[01/11/2026, 09:25:00] \u200eClient A a changé l'objet du groupe",
    ]

    result = parse_export(lines)

    assert [m.text for m in result.messages] == ["perceuse 500W"]
    assert (result.parse_errors, result.system_skipped) == (0, 3)


def test_should_count_one_error_when_a_line_comes_before_any_message():
    lines = ["not a message line", "", "[01/11/2026, 09:24:00] Client A: perceuse 500W"]

    result = parse_export(lines)

    assert (len(result.messages), result.parse_errors) == (1, 1)


def test_should_count_one_error_and_drop_continuations_when_a_header_has_an_impossible_date():
    lines = [
        "[31/02/2026, 09:24:00] Client A: perceuse 500W",
        "suite du message",
        "[01/11/2026, 25:00:00] Client A: perceuse 500W",
        "[01/11/2026, 09:30:00] Client B: ciment",
    ]

    result = parse_export(lines)

    assert ([m.text for m in result.messages], result.parse_errors) == (["ciment"], 2)


def test_should_count_one_error_when_a_header_has_an_author_and_no_text():
    result = parse_export(["[01/11/2026, 09:24:00] Client A:"])

    assert (len(result.messages), result.parse_errors) == (0, 1)


def test_should_read_day_first_when_a_first_field_is_above_12_whatever_the_default():
    lines = ["[13/11/2026, 09:24:00] A: x", "[01/11/2026, 09:25:00] A: y"]

    result = parse_export(lines, "mdy")

    assert (result.date_order, result.date_order_source) == ("dmy", "detected")
    assert result.messages[1].timestamp == datetime(2026, 11, 1, 9, 25)


def test_should_read_month_first_when_a_second_field_is_above_12_whatever_the_default():
    lines = ["[11/13/26, 9:24:00 AM] A: x", "[11/1/26, 9:25:00 AM] A: y"]

    result = parse_export(lines, "dmy")

    assert (result.date_order, result.date_order_source) == ("mdy", "detected")
    assert result.messages[1].timestamp == datetime(2026, 11, 1, 9, 25)


@pytest.mark.parametrize("default_order, expected", [("dmy", datetime(2026, 11, 2)), ("mdy", datetime(2026, 2, 11))])
def test_should_apply_the_default_order_when_every_date_is_ambiguous(default_order, expected):
    result = parse_export(["[02/11/2026, 00:00:00] A: x"], default_order)

    assert result.date_order_source == "default"
    assert result.messages[0].timestamp == expected


def test_should_prefer_day_first_and_count_the_misfits_when_the_file_holds_both_kinds_of_evidence():
    lines = ["[13/11/2026, 09:24:00] A: x", "[11/13/2026, 09:25:00] A: y"]

    result = parse_export(lines)

    assert (result.date_order, len(result.messages), result.parse_errors) == ("dmy", 1, 1)


def test_should_refuse_a_default_date_order_that_is_not_dmy_or_mdy():
    with pytest.raises(ValueError, match="date order"):
        parse_export([], "ymd")


def test_should_expand_a_two_digit_year_to_the_2000s_when_the_header_has_two_digits():
    result = parse_export(["[1/11/99, 9:24:00 AM] A: x"], "dmy")

    assert result.messages[0].timestamp.year == 2099


def test_should_refuse_to_export_seconds_when_the_format_has_no_seconds():
    message = ParsedMessage(datetime(2026, 11, 1, 9, 24, 5), "A", "x")

    with pytest.raises(ValueError, match="seconds"):
        export_messages([message], "android_nobracket_fr")


def test_should_refuse_to_export_when_the_format_is_unknown():
    with pytest.raises(ValueError, match="unknown export format"):
        export_messages([], "telegram")


# --- Connector: records built from a real file ---

EXPORT = (
    "\ufeff[01/11/2026, 09:00:00] Les messages sont chiffrés de bout en bout.\n"
    "[01/11/2026, 09:24:00] Client A: Bonjour, prix du ciment 50kg ?\n"
    "et aussi une perceuse 500W svp\n"
    "[01/11/2026, 09:30:00] Client B: <Médias omis>\n"
    "oups\n"
    "[01/11/2026, 09:31:00] Client B: texte\n"
)


@pytest.fixture
def export_path(tmp_path):
    path = tmp_path / "chat.txt"
    path.write_text(EXPORT, encoding="utf-8", newline="\n")
    return path


async def test_should_build_unified_records_when_the_export_has_multi_line_messages(export_path):
    connector = WhatsAppConnector(str(export_path))

    records = await connector.fetch_records()

    assert [(r.id, r.source_ref, r.timestamp) for r in records] == [
        ("wa-2", "chat.txt#L2", "2026-11-01T09:24:00"),
        ("wa-4", "chat.txt#L4", "2026-11-01T09:30:00"),
        ("wa-6", "chat.txt#L6", "2026-11-01T09:31:00"),
    ]
    assert records[0].payload == {
        "author": "Client A",
        "text": "Bonjour, prix du ciment 50kg ?\net aussi une perceuse 500W svp",
        "attachment": False,
    }


async def test_should_extract_the_products_of_every_line_when_a_message_spans_several_lines(export_path):
    records = await WhatsAppConnector(str(export_path)).fetch_records()

    assert [e["raw"] for e in records[0].entities] == ["ciment 50kg", "perceuse 500W"]


async def test_should_flag_the_attachment_and_keep_its_caption_when_the_message_is_a_placeholder(export_path):
    records = await WhatsAppConnector(str(export_path)).fetch_records()

    assert (records[1].payload["attachment"], records[1].payload["text"]) == (True, "<Médias omis>\noups")


async def test_should_count_system_messages_apart_when_fetching_records(export_path):
    connector = WhatsAppConnector(str(export_path))

    await connector.fetch_records()

    assert (connector.parse_errors, connector.system_skipped) == (0, 1)


async def test_should_return_at_most_the_limit_when_the_export_has_more_messages(export_path):
    records = await WhatsAppConnector(str(export_path)).fetch_records(limit=2)

    assert [r.id for r in records] == ["wa-2", "wa-4"]


async def test_should_report_the_default_order_when_the_dates_of_the_file_are_ambiguous(export_path):
    connector = WhatsAppConnector(str(export_path), default_date_order="mdy")

    records = await connector.fetch_records()

    assert (connector.date_order, connector.date_order_source) == ("mdy", "default")
    assert records[0].timestamp == "2026-01-11T09:24:00"


async def test_should_report_the_detected_order_when_a_date_settles_it(tmp_path):
    path = tmp_path / "chat.txt"
    path.write_text("[25/12/2026, 09:24:00] A: ciment 50 kg\n", encoding="utf-8")
    connector = WhatsAppConnector(str(path), default_date_order="mdy")

    await connector.fetch_records()

    assert (connector.date_order, connector.date_order_source) == ("dmy", "detected")


def test_should_refuse_a_default_date_order_when_building_a_connector():
    with pytest.raises(ValueError, match="default_date_order"):
        WhatsAppConnector("unused.txt", default_date_order="auto")
