from aiogram import Bot, Dispatcher, types, executor
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup
from dotenv import load_dotenv, find_dotenv

from api_requests import request
from database import orm
import math
from os import getenv

load_dotenv(find_dotenv())


bot = Bot(token=getenv('bot_token'))
storage = MemoryStorage()
dp = Dispatcher(bot, storage=storage)


###### Реализация установки города по умолчанию ########

class SetUserCity(StatesGroup):  # FSM, для хранения информации в оперативной памяти
    waiting_user_city = State()


@dp.message_handler(regexp='Установить свой город')
async def set_user_city_start(message: types.Message):
    '''Функция для обращения в FSM для установки города по умолчанию'''
    markup = types.reply_keyboard.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
    btn1 = types.KeyboardButton('Меню')
    markup.add(btn1)
    text = 'В каком городе проживаете?'
    await message.answer(text, reply_markup=markup)
    await SetUserCity.waiting_user_city.set()


@dp.message_handler(state=SetUserCity.waiting_user_city)
async def user_city_chosen(message: types.Message, state: FSMContext):
    '''Логика FSM для установки города по умолчанию, и записи в бд'''

    if message.text[0].islower():
        await message.answer('Названия городов пишутся с большой буквы)')
        return
    try:
        data = request.get_weather(message.text)
    except:
        await message.answer('Истёк срок пробной версии API')
        await state.finish()
    await state.update_data(waiting_user_city=message.text)
    user_data = await state.get_data()
    orm.set_user_city(message.from_user.id,
                      user_data.get('waiting_user_city'))
    markup = await main_menu()
    text = f'Запомнил, {user_data.get("waiting_user_city")} ваш город'
    await message.answer(text, reply_markup=markup)
    await state.finish()


##### Вывод погоды в своём городе и запись#####
@dp.message_handler(regexp='Погода в моём городе')
async def get_city_weather(message: types.Message):
    '''Логика FSM для вывода погоды в городе по умолчанию, и записи в бд'''

    markup = await main_menu()
    home_city = orm.get_user_city(message.from_user.id)
    if home_city is None:
        await message.answer('У вас не установлен город. Сначала задайте его')
        return
    try:
        data = request.get_weather(home_city)
    except:
        await message.answer('Истёк срок пробной версии API')
        return
    orm.create_report(message.from_user.id, data["temp"], data["feels_like"], data["wind_speed"], data["pressure_mm"],
                      home_city)
    text = f'Погода в городе {home_city}: \nТемпература: {data["temp"]} C\nОщущается как: {data["feels_like"]} C \nСкорость ветра: {data["wind_speed"]}м/с\nДавление: {data["pressure_mm"]}мм'
    await message.answer(text, reply_markup=markup)


###### Реализация вывода погоды в чужом городе и записи в бд ########

class ChoiceCityWeather(StatesGroup):  # FSM, для хранения информации в оперативной памяти
    waiting_city = State()


@dp.message_handler(regexp='Погода в другом месте')
async def city_start(message: types.Message):
    '''Функция для обращения в FSM для установки погоды в другом городе'''
    markup = types.reply_keyboard.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
    btn1 = types.KeyboardButton('Меню')
    markup.add(btn1)
    text = 'Введите название города'
    await message.answer(text, reply_markup=markup)
    await ChoiceCityWeather.waiting_city.set()  # устанавливаем State, чтобы вызвать следующий метод


@dp.message_handler(state=ChoiceCityWeather.waiting_city)
async def city_chosen(message: types.Message, state: FSMContext):
    '''Логика FSM для установки погоды в другом городе, и записи в бд'''
    if message.text[0].islower():
        await message.answer('Названия городов пишутся с большой буквы)')
        return
    await state.update_data(waiting_city=message.text)
    markup = await main_menu()
    city = await state.get_data()
    try:
        data = request.get_weather(city.get('waiting_city'))  # обращаемся к API, передаём город
    except:
        await message.answer('Истёк пробный срок API')
        await state.finish()
    orm.create_report(message.from_user.id, data["temp"], data["feels_like"], data["wind_speed"], data["pressure_mm"],
                      city.get('waiting_city'))
    text = f'Погода в {city.get("waiting_city")}\nТемпература: {data["temp"]} C\nОщущается как: {data["feels_like"]} C \nСкорость ветра: {data["wind_speed"]}м/с\nДавление: {data["pressure_mm"]}мм'
    await message.answer(text, reply_markup=markup)
    await state.finish()


##### Реализации выдачи истории запросов пользователя #####

@dp.message_handler(regexp='История')
async def get_reports(message: types.Message):
    '''Функция для реализации выдачи истории запросов пользователя'''
    current_page = 1
    reports = orm.get_reports(message.from_user.id)
    total_pages = math.ceil(len(reports) / 4)
    text = 'История запросов:'
    inline_markup = types.InlineKeyboardMarkup()
    for report in reports[:current_page * 4]:
        inline_markup.add(types.InlineKeyboardButton(
            text=f'{report.city} {report.date.day}.{report.date.month}.{report.date.year}',
            callback_data=f'report_{report.id}'
        ))
    current_page += 1
    inline_markup.row(
        types.InlineKeyboardButton(text=f'{current_page - 1}/{total_pages}', callback_data='None'),
        types.InlineKeyboardButton(text='Вперёд', callback_data=f'next_{current_page}')
    )
    await message.answer(text, reply_markup=inline_markup)


@dp.callback_query_handler(lambda call: True)
async def callback_query(call, state: FSMContext):
    '''Функция-пагинатор, используемая в истории запросов пользователя'''
    query_type = call.data.split('_')[0]
    if query_type == 'delete' and call.data.split('_')[1] == 'report':
        report_id = int(call.data.split('_')[2])
        current_page = 1
        orm.delete_user_report(report_id)
        reports = orm.get_reports(call.from_user.id)
        total_pages = math.ceil(len(reports) / 4)
        inline_markup = types.InlineKeyboardMarkup()
        for report in reports[:current_page * 4]:
            inline_markup.add(types.InlineKeyboardButton(
                text=f'{report.city} {report.date.day}.{report.date.month}.{report.date.year}',
                callback_data=f'report_{report.id}'
            ))
        current_page += 1
        inline_markup.row(
            types.InlineKeyboardButton(text=f'{current_page - 1}/{total_pages}', callback_data='None'),
            types.InlineKeyboardButton(text='Вперёд', callback_data=f'next_{current_page}')
        )
        await call.message.edit_text(text='История запросов:', reply_markup=inline_markup)
        return
    async with state.proxy() as data:
        data['current_page'] = int(call.data.split('_')[1])
        await state.update_data(current_page=data['current_page'])
        if query_type == 'next':
            reports = orm.get_reports(call.from_user.id)
            total_pages = math.ceil(len(reports) / 4)
            inline_markup = types.InlineKeyboardMarkup()
            if data['current_page'] * 4 >= len(reports):
                for report in reports[data['current_page'] * 4 - 4:len(reports) + 1]:
                    inline_markup.add(types.InlineKeyboardButton(
                        text=f'{report.city} {report.date.day}.{report.date.month}.{report.date.year}',
                        callback_data=f'report_{report.id}'
                    ))
                data['current_page'] -= 1
                inline_markup.row(
                    types.InlineKeyboardButton(text='Назад', callback_data=f'prev_{data["current_page"]}'),
                    types.InlineKeyboardButton(text=f'{data["current_page"] + 1}/{total_pages}', callback_data='None')
                )
                await call.message.edit_text(text="История запросов:", reply_markup=inline_markup)
                return
            for report in reports[data['current_page'] * 4 - 4:data['current_page'] * 4]:
                inline_markup.add(types.InlineKeyboardButton(
                    text=f'{report.city} {report.date.day}.{report.date.month}.{report.date.year}',
                    callback_data=f'report_{report.id}'
                ))
            data['current_page'] += 1
            inline_markup.row(
                types.InlineKeyboardButton(text='Назад', callback_data=f'prev_{data["current_page"] - 2}'),
                types.InlineKeyboardButton(text=f'{data["current_page"] - 1}/{total_pages}', callback_data='None'),
                types.InlineKeyboardButton(text='Вперёд', callback_data=f'next_{data["current_page"]}')
            )
            await call.message.edit_text(text="История запросов:", reply_markup=inline_markup)
        if query_type == 'prev':
            reports = orm.get_reports(call.from_user.id)
            total_pages = math.ceil(len(reports) / 4)
            inline_markup = types.InlineKeyboardMarkup()
            if data['current_page'] == 1:
                for report in reports[0:data['current_page'] * 4]:
                    inline_markup.add(types.InlineKeyboardButton(
                        text=f'{report.city} {report.date.day}.{report.date.month}.{report.date.year}',
                        callback_data=f'report_{report.id}'
                    ))
                data['current_page'] += 1
                inline_markup.row(
                    types.InlineKeyboardButton(text=f'{data["current_page"] - 1}/{total_pages}', callback_data='None'),
                    types.InlineKeyboardButton(text='Вперёд', callback_data=f'next_{data["current_page"]}')
                )
                await call.message.edit_text(text="История запросов:", reply_markup=inline_markup)
                return
            for report in reports[data['current_page'] * 4 - 4:data['current_page'] * 4]:
                inline_markup.add(types.InlineKeyboardButton(
                    text=f'{report.city} {report.date.day}.{report.date.month}.{report.date.year}',
                    callback_data=f'report_{report.id}'
                ))
            data['current_page'] -= 1
            inline_markup.row(
                types.InlineKeyboardButton(text='Назад', callback_data=f'prev_{data["current_page"]}'),
                types.InlineKeyboardButton(text=f'{data["current_page"] + 1}/{total_pages}', callback_data='None'),
                types.InlineKeyboardButton(text='Вперёд', callback_data=f'next_{data["current_page"]}'),
            )
            await call.message.edit_text(text="История запросов:", reply_markup=inline_markup)
        if query_type == 'report':
            reports = orm.get_reports(call.from_user.id)
            report_id = call.data.split('_')[1]
            inline_markup = types.InlineKeyboardMarkup()
            for report in reports:
                if report.id == int(report_id):
                    inline_markup.add(
                        types.InlineKeyboardButton(text='Назад', callback_data=f'reports_{data["current_page"]}'),
                        types.InlineKeyboardButton(text='Удалить зарос', callback_data=f'delete_report_{report_id}')
                    )
                    await call.message.edit_text(
                        text=f'Данные по запросу\n'
                             f'Город:{report.city}\n'
                             f'Температура:{report.temp}\n'
                             f'Ощущается как:{report.feels_like}\n'
                             f'Скорость ветра:{report.wind_speed}\n'
                             f'Давление:{report.pressure_mm}',
                        reply_markup=inline_markup
                    )
                    break
        if query_type == 'reports':
            reports = orm.get_reports(call.from_user.id)
            total_pages = math.ceil(len(reports) / 4)
            inline_markup = types.InlineKeyboardMarkup()
            data['current_page'] = 1
            for report in reports[:data['current_page'] * 4]:
                inline_markup.add(types.InlineKeyboardButton(
                    text=f'{report.city} {report.date.day}.{report.date.month}.{report.date.year}',
                    callback_data=f'report_{report.id}'
                ))
            data['current_page'] += 1
            inline_markup.row(
                types.InlineKeyboardButton(text=f'{data["current_page"] - 1}/{total_pages}', callback_data='None'),
                types.InlineKeyboardButton(text='Вперёд', callback_data=f'next_{data["current_page"]}')
            )
            await call.message.edit_text(text='История запросов:', reply_markup=inline_markup)


##### Функции, для работы с меню и запуском #####

@dp.message_handler(commands=['start'])
async def start_message(message: types.Message):
    '''Функция запуска'''
    orm.add_user(message.from_user.id, message.from_user.first_name)
    markup = await main_menu()
    text = f'Привет {message.from_user.first_name}, я бот, который расскжет тебе о погоде на сегодня'
    await message.answer(text, reply_markup=markup)


@dp.message_handler(regexp='Меню')
async def start_message(message: types.Message):
    '''Функция, вызывающая меню'''
    markup = await main_menu()
    text = f'Привет, {message.from_user.first_name}! Я бот, который расскажет тебе о погоде на сегодня!'
    await message.answer(text, reply_markup=markup)


async def main_menu():  # выносим меню в функцию, чтобы не перегружать код
    '''Функция формирования кнопок меню'''
    markup = types.reply_keyboard.ReplyKeyboardMarkup(row_width=2)
    btn1 = types.KeyboardButton('Погода в моём городе')
    btn2 = types.KeyboardButton('Погода в другом месте')
    btn3 = types.KeyboardButton('История')
    btn4 = types.KeyboardButton('Установить свой город')
    markup.add(btn1, btn2, btn3, btn4)
    return markup


@dp.message_handler()
async def on_startup(message):
    '''Заглушка для непрописанных команд'''
    await message.answer(f'Привет! Напиши /start, чтобы начать работу')


if __name__ == '__main__':
    executor.start_polling(dp)
