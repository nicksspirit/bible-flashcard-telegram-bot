import logging
import random
import re
from textwrap import dedent

from aiogoogle import Aiogoogle
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ParseMode
from telegram.ext import ApplicationBuilder, CallbackQueryHandler, CommandHandler, ContextTypes

import config

QUESTION_ID = str
QUESTION = str
ANSWER = str
SheetRow = tuple[QUESTION_ID, QUESTION, ANSWER]

MULTIPLE_ANS_REGEX = re.compile(r"(?P<ol>[a-z]\.)(?P<li>\s.+)", re.MULTILINE)

logger = logging.getLogger(f"{config.APP_NAME}.{__name__}")


def hide_answer(ans: str) -> str:
    return MULTIPLE_ANS_REGEX.sub("\g<1> ||\g<2>||\n", ans)


def escape_chars(string: str) -> str:
    return (
        string.replace("[", "*[")
        .replace("]", "]*")
        .replace(".", "\.")
        .replace("-", "\-")
        .replace("+", "\+")
    )


def answer_block(ans: str):
    return f"\n\n*Answer:*\n\n{escape_chars(ans)}"


def question_block(qid: str, question: str):
    return f"__Q{qid}:__\n{escape_chars(question)}"


async def fetch_random_question() -> SheetRow:
    logger.info("Fetching random question from spreadsheet.")

    async with Aiogoogle(api_key=config.SHEETS_API_KEY) as aiogoogle:
        sheets_svc = await aiogoogle.discover("sheets", "v4")
        spreadsheets = sheets_svc.spreadsheets

        reqs = (spreadsheets.values.get(spreadsheetId=config.GOOGLE_SHEETS_ID, range="'Q&A'!A2:C"),)
        result = await aiogoogle.as_api_key(*reqs)

        values: list[SheetRow] = result["values"]

        qid, question, answer = random.choice(
            [(qid, question, answer) for qid, question, answer in values if qid == "25"]
        )

        logger.debug(f"Retrieved Question {qid}")

        return qid, question, answer


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):

    start_msg = dedent(
        """
        Hello 👋🏾 \! I am your friendly flash card bot\.
        I am here to help you study your bible 📖\. You can interact with me by sending these commands:
        
        /start \- Shows these instructions again
        /question \- Shows you a question\. _\Questions are randomly generated\._
        """
    )

    logger.info(f"User ({context._user_id}) issued START command.")

    await update.message.reply_markdown_v2(start_msg)


async def question_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.info("User issued QUESTION command")

    if context.chat_data is None:
        logger.error("{chat_data} does not exist in chat update event!")
        return

    qid, question, answer = await fetch_random_question()
    context.chat_data[qid] = (question, answer)
    question_block_ = question_block(qid, question)

    reply_markup = InlineKeyboardMarkup(
        [[InlineKeyboardButton(text="Reveal Answer", callback_data=qid)]]
    )

    await update.message.reply_markdown_v2(question_block_, reply_markup=reply_markup)


async def reveal_answer_btn(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles callback event when reveal answer button is clicked"""

    logger.info("User clicked REVEAL ANSWER button")

    if not context.chat_data:
        logger.error("{chat_data} does not exist in chat update event!")
        return

    if not update.effective_message:
        logger.error("{effective_message} does not exist in chat update event!")
        return

    query = update.callback_query

    # CallbackQueries need to be answered, even if no notification to the user is needed
    # Some clients may have trouble otherwise. See https://core.telegram.org/bots/api#callbackquery
    await query.answer()

    qid = query.data
    question, answer = context.chat_data[qid]
    question_block_ = question_block(qid, question)

    if MULTIPLE_ANS_REGEX.match(answer):
        logger.debug(f"Question {qid} has multiple answers.")

        answers = answer.split("\n")
        question_answer_txt = question_block_ + answer_block("You ready? Here are the answers:")

        await query.edit_message_text(text=question_answer_txt, parse_mode=ParseMode.MARKDOWN_V2)

        for ans in answers:
            hidden_ans = escape_chars(hide_answer(ans))
            await update.effective_message.reply_markdown_v2(hidden_ans)

    else:
        logger.debug(f"Question {qid} has a single answer.")

        question_answer_txt = question_block_ + answer_block(answer)
        await query.edit_message_text(text=question_answer_txt, parse_mode=ParseMode.MARKDOWN_V2)
    
    logger.info(f"Revealing answer(s) to question {qid} button.")

    reply_markup = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(text="Yes", callback_data=f"{qid}:yes"),
                InlineKeyboardButton(text="No", callback_data=f"{qid}:no"),
            ]
        ]
    )

    await update.effective_message.reply_text(
        "Did you get the question correct?", reply_markup=reply_markup
    )


def main():
    """
    Run the bot
    """
    telegram_app = ApplicationBuilder().token(config.TOKEN).build()

    start_handler = CommandHandler("start", start_command)
    question_handler = CommandHandler("question", question_command)

    telegram_app.add_handler(start_handler)
    telegram_app.add_handler(CallbackQueryHandler(reveal_answer_btn))
    telegram_app.add_handler(question_handler)

    telegram_app.run_polling()


if __name__ == "__main__":
    main()
