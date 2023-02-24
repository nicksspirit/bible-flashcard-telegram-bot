import logging
import random
import re
from enum import Enum
from textwrap import dedent
from typing import cast

from aiogoogle import Aiogoogle
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ParseMode
from telegram.ext import (
    ApplicationBuilder,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
)

import config

QUESTION_ID = str
QUESTION = str
ANSWER = str
SheetRow = tuple[QUESTION_ID, QUESTION, ANSWER]

QA_ID = "ADV-1"
ANSWER_STATE = 0
FEEDBACK_STATE = 1
MULTIPLE_ANS_REGEX = re.compile(r"(?P<ol>[a-z]\.)(?P<li>\s.+)", re.MULTILINE)

logger = logging.getLogger(f"{config.APP_NAME}.{__name__}")


class FeedbackStatus(str, Enum):
    YES = "yes"
    NO = "no"

    def __str__(self) -> str:
        return str.__str__(self)


def hide_answer(ans: str) -> str:
    return MULTIPLE_ANS_REGEX.sub("\g<1> ||\g<2>||\n", ans)


def escape_chars(string: str) -> str:
    return (
        string.replace("[", "*[")
        .replace("]", "]*")
        .replace(".", "\.")
        .replace("-", "\-")
        .replace("+", "\+")
        .replace("(", "\(")
        .replace(")", "\)")
        .replace(">", "\>")
    )


def answer_block(ans: str) -> str:
    return f"\n\n*Answer:*\n\n{escape_chars(ans)}"


def question_block(qid: str, question: str) -> str:
    return f"__Q{qid}:__\n{escape_chars(question)}"


async def fetch_random_question() -> SheetRow:
    global QA_ID

    async with Aiogoogle(service_account_creds=config.SA_CREDS) as aiogoogle:
        sheets_svc = await aiogoogle.discover("sheets", "v4")
        spreadsheets = sheets_svc.spreadsheets
        
        logger.info(f"Fetching admin configuration from spreadsheet.")

        reqs = (
            spreadsheets.values.get(spreadsheetId=config.GOOGLE_SHEETS_ID, range=f"'Admin'!A1:C"),
        )
        result = await aiogoogle.as_service_account(*reqs)
        admin_config = cast(
            config.AdminConfig, {config_name: value for config_name, value in result["values"]}
        )

        QA_ID = admin_config["question_set"]
        min_qid, max_qid = [
            int(qid.strip()) + 1 for qid in admin_config["question_range"].split("-")
        ]
        
        reqs = (
            spreadsheets.values.get(
                spreadsheetId=config.GOOGLE_SHEETS_ID, range=f"'{QA_ID}'!A{min_qid}:C{max_qid}"
            ),
        )

        result = await aiogoogle.as_service_account(*reqs)
        questions: list[SheetRow] = result["values"]

        logger.info(f"Retrieved questions {min_qid} to {max_qid} from sheet {QA_ID}.")

        qid, question, answer = random.choice(
            [(qid, question, answer) for qid, question, answer in questions]
        )

        logger.info(f"Randomly picked question {qid} from sheet {QA_ID}.")

        return qid, question, answer


async def write_feedback(timestamp, user_id: int, qset: str, qid: str, answer_status: str):
    logger.info(f"Writing feedback for question {qid} from sheet {QA_ID} to spreadsheet.")

    sheet_range = f"'Answers'!A2:E"

    async with Aiogoogle(service_account_creds=config.SA_CREDS) as aiogoogle:
        sheets_svc = await aiogoogle.discover("sheets", "v4")
        spreadsheets = sheets_svc.spreadsheets

        req_args = {
            "spreadsheetId": config.GOOGLE_SHEETS_ID,
            "range": sheet_range,
            "insertDataOption": "INSERT_ROWS",
            "valueInputOption": "USER_ENTERED",
        }

        body = {
            "majorDimension": "ROWS",
            "values": [[timestamp, user_id, qset, qid, answer_status]],
        }

        reqs = (spreadsheets.values.append(**req_args, json=body),)

        await aiogoogle.as_service_account(*reqs)


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
    logger.info(f"User ({context._user_id}) issued QUESTION command")

    if context.user_data is None:
        logger.error("{user_data} does not exist in chat update event!")
        return

    qid, question, answer = await fetch_random_question()
    qkey = f"{QA_ID}:{qid}"

    context.user_data[qkey] = (question, answer)
    question_block_ = question_block(qid, question)

    reply_markup = InlineKeyboardMarkup(
        [[InlineKeyboardButton(text="Reveal Answer", callback_data=qkey)]]
    )

    await update.message.reply_markdown_v2(question_block_, reply_markup=reply_markup)

    return ANSWER_STATE


async def reveal_answer_btn(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles callback event when reveal answer button is clicked"""

    logger.info(f"User ({context._user_id}) clicked REVEAL ANSWER button")

    if not context.user_data:
        logger.error("{user_data} does not exist in chat update event!")
        return

    if not update.effective_message:
        logger.error("{effective_message} does not exist in chat update event!")
        return

    query = update.callback_query

    # CallbackQueries need to be answered, even if no notification to the user is needed
    # Some clients may have trouble otherwise. See https://core.telegram.org/bots/api#callbackquery
    await query.answer()

    qkey = query.data

    if qkey not in context.user_data:
        logger.error(f'"{qkey}" does not exist in chat update event\'s {{user_data}}!')
        return

    _, qid = qkey.split(":")
    question, answer = context.user_data[qkey]
    question_block_ = question_block(qid, question)

    if MULTIPLE_ANS_REGEX.match(answer):
        logger.debug(f"Question {qid} from sheet {QA_ID} has multiple answers.")

        answers = answer.split("\n")
        question_answer_txt = question_block_ + answer_block("You ready? Here are the answers:")

        await query.edit_message_text(text=question_answer_txt, parse_mode=ParseMode.MARKDOWN_V2)

        for ans in answers:
            hidden_ans = escape_chars(hide_answer(ans))
            await update.effective_message.reply_markdown_v2(hidden_ans)

        logger.info(f"Revealed {len(answers)} answers to question {qid}.")

    else:
        logger.debug(f"Question {qid} from sheet {QA_ID} has a single answer.")

        question_answer_txt = question_block_ + answer_block(answer)
        await query.edit_message_text(text=question_answer_txt, parse_mode=ParseMode.MARKDOWN_V2)

        logger.info(f"Revealed answer to question {qid}.")

    reply_markup = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(text="Yes", callback_data=f"{qkey}:yes"),
                InlineKeyboardButton(text="No", callback_data=f"{qkey}:no"),
            ]
        ]
    )

    await update.effective_message.reply_text(
        "Did you get the question correct?", reply_markup=reply_markup
    )

    return FEEDBACK_STATE


async def answer_yes_btn(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.user_data:
        logger.error("{user_data} does not exist in chat update event!")
        return

    if not update.effective_message:
        logger.error("{effective_message} does not exist in chat update event!")
        return

    query = update.callback_query
    await query.answer()

    qset, qid, _ = query.data.split(":")

    logger.info(
        f"User ({context._user_id}) clicked YES button to question {qid} from sheet {QA_ID}."
    )

    await update.effective_message.reply_text("Oh! That's awesome. Great job!")

    reply_timestamp = update.effective_message.date.timestamp()
    user_id = context._user_id
    await write_feedback(reply_timestamp, user_id, qset, qid, "Yes")

    return ConversationHandler.END


async def answer_no_btn(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.user_data:
        logger.error("{user_data} does not exist in chat update event!")
        return

    if not update.effective_message:
        logger.error("{effective_message} does not exist in chat update event!")
        return

    query = update.callback_query
    await query.answer()

    qset, qid, _ = query.data.split(":")

    logger.info(
        f"User ({context._user_id}) clicked NO button to question {qid} from sheet {QA_ID}."
    )

    await update.effective_message.reply_text("Oh no! Keep at it. You will get it right next time.")

    reply_timestamp = update.effective_message.date.timestamp()
    user_id = context._user_id
    await write_feedback(reply_timestamp, user_id, qset, qid, "No")

    return ConversationHandler.END


def main():
    """
    Run the bot
    """

    telegram_app = ApplicationBuilder().token(config.TOKEN).build()

    start_handler = CommandHandler("start", start_command)
    question_handler = CommandHandler("question", question_command)

    conv_handler = ConversationHandler(
        entry_points=[question_handler],
        states={
            ANSWER_STATE: [CallbackQueryHandler(reveal_answer_btn, pattern=r"^\w+-\d+:\d+$")],
            FEEDBACK_STATE: [
                CallbackQueryHandler(
                    answer_yes_btn, pattern=rf"^\w+-\d+:\d+:{FeedbackStatus.YES}$"
                ),
                CallbackQueryHandler(answer_no_btn, pattern=rf"^\w+-\d+:\d+:{FeedbackStatus.NO}$"),
            ],
        },
        fallbacks=[question_handler],
    )

    telegram_app.add_handler(start_handler)
    telegram_app.add_handler(conv_handler)

    telegram_app.run_polling()


if __name__ == "__main__":
    main()
