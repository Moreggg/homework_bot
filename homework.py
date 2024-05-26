from http import HTTPStatus
import logging
from logging import StreamHandler
import os
import sys
import time

from dotenv import load_dotenv
import requests
from telebot import TeleBot

import exceptions


load_dotenv()

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
handler = StreamHandler(stream=sys.stdout)
formatter = logging.Formatter(
    '%(asctime)s  [%(levelname)s]  %(message)s'
)
handler.setFormatter(formatter)
logger.addHandler(handler)

PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN', default='PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN', default='TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID', default='TELEGRAM_CHAT_ID')

RETRY_PERIOD = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}


HOMEWORK_VERDICTS = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}


def check_tokens():
    """Проверка доступности переменных окружения."""
    ENV_VARS = (PRACTICUM_TOKEN, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID)
    ENV_VARS_KEYS = ('PRACTICUM_TOKEN', 'TELEGRAM_TOKEN', 'TELEGRAM_CHAT_ID')
    for var in ENV_VARS:
        if var in ENV_VARS_KEYS or var is None:
            logger.critical(
                f'Отсутствует обязательная переменная окружения: "{var}"'
                f'\nПрограмма принудительно остановлена'
            )
            raise exceptions.UnknownStatusError(
                'В качестве ответа получен неизвестный статус'
            )


def send_message(bot, message):
    """Отправляет сообщение в чат, указанный в TELEGRAM_CHAT_ID."""
    bot.send_message(TELEGRAM_CHAT_ID, message)
    logger.debug('Сообщение отправлено')


def get_api_answer(timestamp):
    """Делает запрос к API сервиса Практикум Домашка."""
    try:
        homework_statuses = requests.get(ENDPOINT,
                                         headers=HEADERS,
                                         params={'from_date': timestamp})
    except requests.RequestException as error:
        message = f'Сбой в работе программы: {error}'
        logger.error(message)
        bot = TeleBot(token=TELEGRAM_TOKEN)
        send_message(bot, message)
    if homework_statuses.status_code != HTTPStatus.OK:
        raise requests.HTTPError('Эндпоинт недоступен.')
    return homework_statuses.json()


def check_response(response):
    """Проверяет ответ на соответствие документации API сервиса."""
    if type(response) is not dict:
        raise TypeError('Получен не словарь.')
    if 'homeworks' not in response:
        raise KeyError('Отсутствует ключ "homeworks"')
    if type(response['homeworks']) is not list:
        raise TypeError('Под ключом "homeworks" не список.')


def parse_status(homework):
    """Извлекает статус домашней работы."""
    if 'homework_name' not in homework:
        raise KeyError(f'Отсутствует ключ "homework_name", {homework}')
    if homework['status'] not in HOMEWORK_VERDICTS:
        raise exceptions.UnknownStatusError
    homework_name = homework['homework_name']
    verdict = HOMEWORK_VERDICTS[homework['status']]
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def main():
    """Основная логика работы бота."""
    check_tokens()
    bot = TeleBot(token=TELEGRAM_TOKEN)
    timestamp = int(time.time())

    old_status = ''

    while True:
        response = get_api_answer(timestamp)
        check_response(response)

        if response['homeworks'] != old_status:
            try:
                message = parse_status(response['homeworks'][0])
            except IndexError:
                message = 'Домашних работ за указанный период не обнаружено.'

            try:
                send_message(bot, message)
            except Exception as error:
                logger.error(f'Не удалось отправить сообщение: {error}')

            time.sleep(RETRY_PERIOD)
        else:
            time.sleep(RETRY_PERIOD)

        old_status = response['homeworks']


if __name__ == '__main__':
    main()
