from dotenv import load_dotenv, find_dotenv

from os import getenv
import json
import requests

load_dotenv(find_dotenv())

def get_city_coord(city):
    payload = {'geocode': city, 'apikey': getenv('geo_key'), 'format': 'json'}
    r = requests.get('https://geocode-maps.yandex.ru/1.x', params=payload)
    geo = json.loads(r.text)
    return geo['response']['GeoObjectCollection']['featureMember'][0]['GeoObject']['Point']['pos']

def get_weather(city):
    coordinates = get_city_coord(city).split()
    payload = {'lat': coordinates[1], 'lon': coordinates[0], 'lang': 'ru_RU'}
    r = requests.get('https://api.weather.yandex.ru/v2/forecast', params=payload, headers=eval(getenv('weather_key')))
    weather_data = json.loads(r.text)
    return weather_data['fact']



