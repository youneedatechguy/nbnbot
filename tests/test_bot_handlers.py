"""Tests for Telegram bot handlers."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from bot.nbn_service import NBNResult


def make_update(text="11 Wattle Drive Yamba NSW 2464"):
    message = MagicMock()
    message.text = text
    reply = AsyncMock()
    reply.edit_text = AsyncMock()
    message.reply_text = AsyncMock(return_value=reply)
    update = MagicMock()
    update.message = message
    return update, reply


@pytest.mark.asyncio
async def test_handle_message_success():
    from bot.handlers import handle_message
    import bot.handlers as handlers

    result = NBNResult(
        loc_id="LOC1",
        address="11 Wattle Drive, Yamba NSW 2464",
        technology="FTTP",
        service_class="20",
        status="Serviceable",
        fibre_on_demand=False,
    )
    mock_service = MagicMock()
    mock_service.lookup = AsyncMock(return_value=[result])

    update, thinking_msg = make_update()
    context = MagicMock()

    with patch.object(handlers, "_get_service", return_value=mock_service):
        await handle_message(update, context)

    thinking_msg.edit_text.assert_called_once()
    call_text = thinking_msg.edit_text.call_args[0][0]
    assert "FTTP" in call_text


@pytest.mark.asyncio
async def test_handle_message_no_results():
    from bot.handlers import handle_message
    import bot.handlers as handlers

    mock_service = MagicMock()
    mock_service.lookup = AsyncMock(return_value=[])

    update, thinking_msg = make_update()
    context = MagicMock()

    with patch.object(handlers, "_get_service", return_value=mock_service):
        await handle_message(update, context)

    thinking_msg.edit_text.assert_called_once()
    assert "No NBN results" in thinking_msg.edit_text.call_args[0][0]


@pytest.mark.asyncio
async def test_handle_message_geocode_error():
    from bot.handlers import handle_message
    import bot.handlers as handlers

    mock_service = MagicMock()
    mock_service.lookup = AsyncMock(side_effect=ValueError("address not found"))

    update, thinking_msg = make_update("gibberish address")
    context = MagicMock()

    with patch.object(handlers, "_get_service", return_value=mock_service):
        await handle_message(update, context)

    call_text = thinking_msg.edit_text.call_args[0][0]
    assert "geocode" in call_text.lower() or "Could not" in call_text


@pytest.mark.asyncio
async def test_handle_message_api_error():
    from bot.handlers import handle_message
    import bot.handlers as handlers

    mock_service = MagicMock()
    mock_service.lookup = AsyncMock(side_effect=Exception("connection error"))

    update, thinking_msg = make_update()
    context = MagicMock()

    with patch.object(handlers, "_get_service", return_value=mock_service):
        await handle_message(update, context)

    call_text = thinking_msg.edit_text.call_args[0][0]
    assert "error" in call_text.lower()


@pytest.mark.asyncio
async def test_cmd_start():
    from bot.handlers import cmd_start

    update = MagicMock()
    update.message.reply_text = AsyncMock()
    context = MagicMock()

    await cmd_start(update, context)
    update.message.reply_text.assert_called_once()
    text = update.message.reply_text.call_args[0][0]
    assert "NBN" in text


@pytest.mark.asyncio
async def test_cmd_lookup_no_args():
    from bot.handlers import cmd_lookup

    update = MagicMock()
    update.message.reply_text = AsyncMock()
    context = MagicMock()
    context.args = []

    await cmd_lookup(update, context)
    update.message.reply_text.assert_called_once()
    assert "Usage" in update.message.reply_text.call_args[0][0]
