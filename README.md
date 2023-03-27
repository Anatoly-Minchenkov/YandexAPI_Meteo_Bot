# YandexAPI_Meteo_Bot

This telegram bot was created as a practice to learn how to work with APIs, Docker and databases.
It uses Yandex API weather data (https://developer.tech.yandex.ru/) 

The bot implements:
- Binding of the city to the user, and weather browsing;
- Weather display in any other city;
- Saving the history of weather requests and output for the user.

Bot link: https://t.me/yandex_weather_checker_bot (Not deployed yet.)

#


### :computer: Technologies:
- Aiogram;
- Docker (Compose);
- DataBases (PostgreSQL, SQLAlchemy).
---





### :hammer_and_wrench: Installation:
1. $ pip install -r requirements.txt
2. Add the following variables to the **.env** environment, to work with the python_dotenv library:
  
       - GEO_KEY = <Api key from Yanex.Geocoder>
       - WEATHER_KEY = <Api key from Yanex.Weather>
       - BOT_TOKEN = <API key from Telegram bot>
       - URL = <URL of the PostgreSQL database>  

  **Optional**

3. You can set up a project from docker-compose by using the command "docker-compose up"
