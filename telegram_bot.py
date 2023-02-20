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

def format_question_answer(qid: str, question: str, answer: str):
    def escape_chars(string: str):
        return string.replace("[", "*[").replace("]", "]*").replace(".", "\.").replace("-", "\-")

    def hide_answer(ans: str):
        return MULTIPLE_ANS_REGEX.sub("\g<1> ||\g<2>||\n", ans)

    def answer_block(ans: str):
        return "\n" "\n" "*Answer:*" "\n" "\n" f"{escape_chars(ans)}"

    template = (
        f"__Q{qid}:__" "\n" f"{escape_chars(question)}" f"{answer_block(answer) if answer else ''}"
    )

    return template


async def fetch_random_question() -> SheetRow:
    logger.info("Fetching random question from spreadsheet.")

    async with Aiogoogle(api_key=config.SHEETS_API_KEY) as aiogoogle:
        sheets_svc = await aiogoogle.discover("sheets", "v4")
        spreadsheets = sheets_svc.spreadsheets

        reqs = (spreadsheets.values.get(spreadsheetId=config.GOOGLE_SHEETS_ID, range="'Q&A'!A2:C"),)
        result = await aiogoogle.as_api_key(*reqs)

        values: list[SheetRow] = result["values"]

        qid, question, answer = random.choice(
            [(qid, question, answer) for qid, question, answer in values]
        )

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

    logger.info("User issued START command")

    await update.message.reply_text(start_msg, parse_mode=ParseMode.MARKDOWN_V2)


async def question_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.chat_data is None:
        logger.error("Chat data context does not exist!")
        return

    qid, question, answer = await fetch_random_question()

    context.chat_data[qid] = (question, answer)

    reply_markup = InlineKeyboardMarkup(
        [[InlineKeyboardButton(text="Reveal Answer", callback_data=qid)]]
    )

    fmt_question = format_question_answer(qid, question, "")

    await update.message.reply_text(
        fmt_question, reply_markup=reply_markup, parse_mode=ParseMode.MARKDOWN_V2
    )


async def reveal_answer_btn(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles callback event when reveal answer button is clicked"""

    if not context.chat_data:
        logger.error("Chat data context does not exist!")
        return

    query = update.callback_query

    # CallbackQueries need to be answered, even if no notification to the user is needed
    # Some clients may have trouble otherwise. See https://core.telegram.org/bots/api#callbackquery
    await query.answer()

    qid = query.data
    question, answer = context.chat_data[qid]

    fmt_question = format_question_answer(qid, question, answer)

    await query.edit_message_text(text=fmt_question, parse_mode=ParseMode.MARKDOWN_V2)


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
