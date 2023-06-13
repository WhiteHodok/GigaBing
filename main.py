import asyncio
import os
import re
import telebot
from EdgeGPT import Chatbot, ConversationStyle
from telebot.util import quick_markup

TOKEN = "6209676775:AAEkGC-XxBmM_p66VeiZtMzIBOdyMeTHX1Y"
COOKIE_PATH = 'cookie.json'
bot = telebot.TeleBot(TOKEN)
EDGES = {}
my_conversation_style = ConversationStyle.balanced

@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    bot.reply_to(
        message, "Введи /help для показа информации\nДля смены стилей вводи /switch и следующую приписку: \ncreative (Креативный)\nbalanced (Баланс)\nprecise (Строгий)")

@bot.message_handler(commands=['reset'])
def send_reset(message):
    try:
        if message.from_user.id not in EDGES:
            EDGES[message.from_user.id] = Chatbot(cookie_path=COOKIE_PATH)
        asyncio.run(EDGES[message.from_user.id].reset())
    except Exception as e:
        bot.reply_to(message, "Ошибка: " + str(e), parse_mode='Markdown')
    else:
        bot.reply_to(message, "Очищено успешно!")

@bot.message_handler(commands=['switch'])
def switch_style(message):
    message_list = message.text.split(" ")
    if len(message_list) > 1:
        styles = {
            "creative": ConversationStyle.creative,
            "balanced": ConversationStyle.balanced,
            "precise": ConversationStyle.precise
        }
        if message_list[1] in styles:
            global my_conversation_style
            my_conversation_style = styles[message_list[1]]
            bot.reply_to(
                message, f"Текущий стиль: {message_list[1].capitalize()}")
        else:
            bot.reply_to(
                message, "Выберите один из параметров! (/help)")
    else:
        bot.reply_to(
            message, "Выберите один из параметров! (/help)")

@bot.message_handler(func=lambda msg: True)
def response_all(message):
    if message.text.startswith('/') and message.text[1:] not in ['start', 'help', 'reset', 'switch']:
        bot.reply_to(message, "Нет такой команды")
        return
    message_text = ''
    if message.chat.type == "private":
        message_text = message.text
        bot.reply_to(message, "Обработка запроса, ожидайте!")
        response_list = asyncio.run(bing_chat(message_text, message))
        if len(response_list[0]) > 4095:
            for x in range(0, len(response_list[0]), 4095):
                bot.reply_to(
                    message, response_list[0][x:x + 4095], parse_mode='Markdown', reply_markup=response_list[1])
        else:
            bot.reply_to(
                message, response_list[0], parse_mode='Markdown', reply_markup=response_list[1])

@bot.callback_query_handler(func=lambda msg: True)
def callback_all(callback_query):
    try:
        response_list = asyncio.run(
            bing_chat(callback_query.data, callback_query))
    except Exception as e:
        bot.reply_to(callback_query.message, "Ошибка: " +
                     str(e), parse_mode='Markdown')
    else:
        if len(response_list[0]) > 4095:
            for x in range(0, len(response_list[0]), 4095):
                bot.reply_to(
                    callback_query.message, response_list[0][x:x +
                                                             4095], parse_mode='Markdown',
                    reply_markup=response_list[1])
        else:
            bot.reply_to(
                callback_query.message, response_list[0], parse_mode='Markdown', reply_markup=response_list[1])

async def bing_chat(message_text, message):
    if message.from_user.id not in EDGES:
        EDGES[message.from_user.id] = Chatbot(cookie_path=COOKIE_PATH)
    response_dict = await EDGES[message.from_user.id].ask(prompt=message_text,
                                                          conversation_style=my_conversation_style)

    if 'text' in response_dict['item']['messages'][1]:
        response = re.sub(r'\[\^\d\^]', '',
                          response_dict['item']['messages'][1]['text'])
    else:
        response = "Что-то не так. Пожалуйста, перезагрузите чат"

    if 'suggestedResponses' in response_dict['item']['messages'][1]:
        suggested_responses = response_dict['item']['messages'][1]['suggestedResponses']
        markup = quick_markup({
            re.sub(r'\[\^\d\^]', '', suggested_responses[i]['text']): {
                'callback_data': suggested_responses[i]['text'].encode('utf-8')[:64].decode('utf-8', 'ignore')}
            for i in range(min(len(suggested_responses), 3))
        }, row_width=1)
    else:
        markup = quick_markup({
            'Предложенных ответов нет': {'url': 'https://bing.com/chat'}
        }, row_width=1)

    throttling = response_dict['item']['throttling']
    if 'maxNumUserMessagesInConversation' in throttling and 'numUserMessagesInConversation' in throttling:
        max_num_user_messages_in_conversation = throttling['maxNumUserMessagesInConversation']
        num_user_messages_in_conversation = throttling['numUserMessagesInConversation']
        response += "\n———————\n"
        response += f"Контекст: {num_user_messages_in_conversation} / {max_num_user_messages_in_conversation}"

    if num_user_messages_in_conversation >= max_num_user_messages_in_conversation:
        await EDGES[message.from_user.id].reset()
        response += "\nКонтекст был автоматически очищен"

    attributions = response_dict['item']['messages'][1]['sourceAttributions']
    if len(attributions) >= 3:
        response += "\n———————\nИсточники:\n"
        for i in range(3):
            provider_display_name = re.sub(
                r'\[\^\d\^]', '', attributions[i]['providerDisplayName'])
            see_more_url = re.sub(
                r'\[\^\d\^]', '', attributions[i]['seeMoreUrl'])
            response += f"{i + 1}.[{provider_display_name}]({see_more_url})\n"

    response_list = [response, markup]
    return response_list

bot.polling()
