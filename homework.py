from http import HTTPStatus
import logging
from logging import FileHandler, StreamHandler
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
handler1 = FileHandler(filename=__file__ + '.log', encoding='UTF-8')
formatter = logging.Formatter(
    ('%(asctime)s [%(levelname)s] [строка %(lineno)d] '
     '[%(funcName)s] %(message)s')
)
handler.setFormatter(formatter)
handler1.setFormatter(formatter)
logger.addHandler(handler)
logger.addHandler(handler1)

PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

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
    ENV_VARS_KEYS = (
        (PRACTICUM_TOKEN, 'PRACTICUM_TOKEN'),
        (TELEGRAM_TOKEN, 'TELEGRAM_TOKEN'),
        (TELEGRAM_CHAT_ID, 'TELEGRAM_CHAT_ID')
    )
    error_message = 'Отсутствует обязательная переменная окружения: '
    check = True
    for var in ENV_VARS_KEYS:
        if var[0] is None:
            logger.critical(
                error_message + var[1]
            )
            check = False
    if not check:
        logger.critical('Программа принудительно остановлена')
        raise exceptions.MissedTokensError(
            error_message + var[1]
        )


def send_message(bot, message):
    """Отправляет сообщение в чат, указанный в TELEGRAM_CHAT_ID."""
    try:
        bot.send_message(TELEGRAM_CHAT_ID, message)
    except Exception as error:
        logger.error(f'Произошла ошибка ({error}) '
                     f'при отправке сообщения: {message}')
        return False
    logger.debug(f'Отправлено сообщение: {message}')
    return True


def get_api_answer(timestamp):
    """Делает запрос к API сервиса Практикум Домашка."""
    api_data = {
        'url': ENDPOINT,
        'headers': HEADERS,
        'params': {'from_date': timestamp}
    }
    logger.debug(
        ('Направлен запрос к {url}, '
         'headers - {headers}, '
         'params - {params}').format(**api_data)
    )
    try:
        homework_statuses = requests.get(**api_data)
    except requests.RequestException as error:
        error_message = (('Сбой при обращении к {url}, '
                          'headers - {headers}, '
                          'params - {params}, ').format(**api_data)
                         + (f'ошибка: {error}'))
        logger.error(error_message)
        raise ConnectionError(error_message)
    if homework_statuses.status_code != HTTPStatus.OK:
        error_message = f'Эндпоинт [{ENDPOINT}] недоступен.'
        logger.error(error_message)
        raise ConnectionError(error_message)
    return homework_statuses.json()


def check_response(response):
    """Проверяет ответ на соответствие документации API сервиса."""
    logger.debug(f'Начало проверки ответа от API [{ENDPOINT}]')
    if not isinstance(response, dict):
        error_message = 'Получен не словарь.'
        logger.error(error_message)
        raise TypeError(error_message)
    if 'homeworks' not in response:
        error_message = 'Отсутствует ключ "homeworks"'
        logger.error(error_message)
        raise exceptions.EmptyResponseFromAPI(error_message)
    homeworks = response.get('homeworks')
    if not isinstance(homeworks, list):
        error_message = 'Под ключом "homeworks" не список.'
        logger.error(error_message)
        raise TypeError(error_message)
    return homeworks


def parse_status(homework):
    """Извлекает статус домашней работы."""
    if 'homework_name' not in homework:
        raise KeyError(f'Отсутствует ключ "homework_name", {homework}')
    status = homework.get('status')
    if status is None:
        error_message = 'Отсутствует статус домашней работы'
        logger.error(error_message)
        raise exceptions.UnknownStatusError(error_message)
    if status not in HOMEWORK_VERDICTS:
        error_message = 'Неизвестный статус домашней работы'
        logger.error(error_message)
        raise exceptions.UnknownStatusError(error_message)
    homework_name = homework['homework_name']
    verdict = HOMEWORK_VERDICTS[status]
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def main():
    """Основная логика работы бота."""
    check_tokens()
    bot = TeleBot(token=TELEGRAM_TOKEN)
    timestamp = int(time.time())

    old_status = ''
    old_error = ''

    while True:
        try:
            response = get_api_answer(timestamp)
            homeworks = check_response(response)
            if not homeworks:
                logger.error('Список домашних работ пуст')
                continue
            homework = homeworks[0]
            status = homework['status']
            if status != old_status:
                message = parse_status(homework)
                bot_status = send_message(bot, message)
            if bot_status:
                old_status = status
                timestamp = response.get('current_date')
        except Exception as error:
            message_error = f'Произошел сбой: {error}'
            logger.error(message_error)
            if error != old_error:
                bot_status = send_message(bot, message)
            if bot_status:
                old_error = error
        finally:
            time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    main()
