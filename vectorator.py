import io
import time
from datetime import datetime, timedelta
from threading import Thread
import random
import anki_vector
import urllib
import requests
import feedparser
import json
import csv
from anki_vector.events import Events
from anki_vector.faces import Face
from anki_vector.util import degrees, distance_mm, speed_mmps
from anki_vector import audio
from anki_vector.connection import ControlPriorityLevel
from anki_vector.user_intent import UserIntent, UserIntentEvent
import config
import os, sys, traceback

# (I think these are called enums in Python... They relate to my dialogue.csv file)
NAME = 0
LINES = 1
INT_LOW = 2
INT_HIGH = 3
MOOD = 4

DIST_COUNT = 0
LAST_NAME = ""

MULTS = { # These are multipliers for the chattiness setting (they raise or lower the time delays)
  1: 7,
  2: 4,
  3: 2,
  4: 1.35,
  5: 1,
  6: 0.8,
  7: 0.5,
  8: 0.35,
  9: 0.2,
  10: 0.1
}

CHATTINESS = MULTS[config.chattiness]

# In the config file users can set a volume (1-5) for Vector's voice and sounds
VOL = {
    1: audio.RobotVolumeLevel.LOW, 
    2: audio.RobotVolumeLevel.MEDIUM_LOW, 
    3: audio.RobotVolumeLevel.MEDIUM, 
    4: audio.RobotVolumeLevel.MEDIUM_HIGH, 
    5: audio.RobotVolumeLevel.HIGH
}

# After Vector tells a joke he randomly plays one of these animation triggers
JOKE_ANIM = [
    "GreetAfterLongTime",
    "ComeHereSuccess",
    "OnboardingReactToFaceHappy",
    "PickupCubeSuccess",
    "PounceSuccess",
    "ConnectToCubeSuccess",
    "FetchCubeSuccess",
    "FistBumpSuccess",
    "OnboardingWakeWordSuccess"
]

# Set up dictionaries for the event names and timestamps 
dic = {}
ts = {}

version = 1.0

# For the randomizer function (if a dialogue contains "{good}"", for example, then I randomly replace it with a word below)
good = ["good", "great", "cool", "wonderful", "lovely", "charming", "nice", "enjoyable", "incredible", "remarkable", "fabulous", "pleasant", "fantastic", "magnificent"]
weird = ["weird", "odd", "strange", "very weird", "crazy", "bizarre", "remarkable", "outlandish", "different", "random", "curious", "freaky"]
scary = ["scary", "frightening", "terrifying", "alarming", "daunting", "frightful", "grim", "harrowing", "shocking"]
interesting = ["interesting", "weird", "strange", "curious", "fascinating", "intriguing", "provocative", "thought-provoking", "unusual", "captivating", "amazing"]

# get the path of the local files
pyPath = os.path.realpath(__file__)
pyPath1 = os.path.dirname(pyPath)
jokesPath = os.path.join(pyPath1, "jokes.txt")
factsPath = os.path.join(pyPath1, "facts.txt")
dialoguePath = os.path.join(pyPath1, "dialogue.csv")

# Load the jokes into a list called 'jokes'. Try local, then download. Need to figure out a better way to do do this... 
try:
    with open(jokesPath, 'r') as f:
        jokes = [line.rstrip('\n') for line in f]
        print("Reading jokes from local file...")
except:
    print("Downloading jokes from Website...")
    jokes = []
    content=urllib.request.urlopen("http://www.cuttergames.com/vector/jokes.txt") 
    
    for line in content:
        line = line.decode("utf-8")
        jokes.append(line.rstrip('\n'))

# Load the facts into a list called 'facts'. Try local, then download. Need to figure out a better way to do do this... 
try:
    with open(factsPath, 'r') as f:
        facts = [line.rstrip('\n') for line in f]
        print("Reading facts from local file...")
except:
    print("Downloading facts from Website...")
    facts = []
    content=urllib.request.urlopen("http://www.cuttergames.com/vector/facts.txt") 
    
    for line in content:
        line = line.decode("utf-8")
        facts.append(line.rstrip('\n'))

# Try to load local dialogue file. On exception, load file from website. Need to figure out a better way to do do this... 
try:
    with open(dialoguePath) as csvfile:
        cr = csv.reader(csvfile, delimiter=',')
        dlg = list(cr)
        print("Reading dialogue from local file...")
except:
    print("Downloading dialogue from website...")
    CSV_URL = 'https://github.com/CertifiedCallatic/vectorator/blob/master/dialogue.csv'
    with requests.Session() as s:
        download = s.get(CSV_URL)
        decoded_content = download.content.decode('utf-8')
        cr = csv.reader(decoded_content.splitlines(), delimiter=',')
        dlg = list(cr)

# Load the timestamps file, if not found then create a new file. Need to find a better way to do this...
try:
    with open('timestamps.csv', mode='r') as infile:
        ts = dict(filter(None, csv.reader(infile)))
except:
    with open('timestamps.csv', 'w', newline = '') as csv_file:
        writer = csv.writer(csv_file)

# Convert strings from CSV to datetime objects
for key, value in ts.items():
    ts[key] = datetime.strptime(value,'%Y-%m-%d %H:%M:%S')

# This sets up the event name dictionary -- it needs the event names from CSV (above) 
for index, row in enumerate(dlg):
    event_name = dlg[index][NAME]
    if event_name not in ts:
        now = datetime.now()
        ts[event_name] = now - timedelta(seconds = 100) 
        ts[event_name + "_next"] = now + timedelta(seconds = 10)
        ts["greeting_next"] = now
    if event_name != "" and event_name != "NAME":
        dic[event_name] = index

# START OF FUNCTIONS ###################################################################################

# Whenever Vector speaks I save the timestamps in ts (when the event/trigger happened, and when it can happen next)
def save_timestamps():
    with open('timestamps.csv', 'w', newline = '') as csv_file:
        writer = csv.writer(csv_file)
        for key, value in ts.items():
            value = datetime.strftime(value,"%Y-%m-%d %H:%M:%S")
            writer.writerow([key, value])

# With 10 lines of dialogue, the first line will be spoken 28% of the time, the 5th line 9%, and the last line less than 1% 
def get_low(low,high):
    nums = []
    nums.append(random.randint(low,high))
    nums.append(random.randint(low,high))
    nums.append(random.randint(low,high))
    return min(nums)

# This takes the line Vector is about to say and replaces anything in curly brackets with either a random word, or the name of the last seen human
def randomizer(say):
    global LAST_NAME

    if "{name}" in say: 
        if "last_saw_name" in ts and (datetime.now() - ts["last_saw_name"]).total_seconds() < 60: # Saw a specific face within last 60 seconds
            say = say.replace("{name}", LAST_NAME)
        else:
            say = say.replace("{name}", "") # If we didn't see a specific face, then remove "{name}"

    return say.format(good=random.choice(good), scary=random.choice(scary), weird=random.choice(weird), interesting=random.choice(interesting), version=version)

# This makes Vector react to different events/triggers
def vector_react(arg):
    global ts
    if arg != "news_intro": print("Vector is trying to react to: ", arg)



    if (datetime.now() - ts["wake_word"]).total_seconds() < 15: # If Vector was listening, don't react for a little while
        print("Wake word timeout")
        return
    if robot.status.is_pathing == True: # If Vector is doing something, don't speak
        print("Vector is pathing...")
        return
    if arg == "pass": # This adds a bit of controllable randomness to some of the random dialogues (jokes, telling the time, etc.)
        print("Instead of attempting a random comment, I chose to pass this time...")
        return

    now = datetime.now()
    if arg not in ts:
        ts[arg] = now - timedelta(seconds = 100) # Fixes problem for new installs where Vector thinks everything JUST happened
        ts[arg +"_next"] = now + timedelta(seconds = random.randint(2,15)) # Don't want him trying to say everything at once 
    if now > ts[arg + "_next"]: # If the time for the [event/trigger]_next timestamp has passed, that event is available 
        if arg == "sleeping":
            say_sleep(arg)
        else:
            row = dic[arg]
            low = int(int(dlg[row][INT_LOW]) * CHATTINESS) # Get the minimum (INT_LOW) timestamp delay (from dialogue file) and adjust up or down by CHATTINESS
            high = int(int(dlg[row][INT_HIGH]) * CHATTINESS) # Get the maximum (INT_HIGH) timestamp delay (from dialogue file) and adjust by CHATTINESS
            to_add = random.randint(low,high)
            print(f"Adding {to_add} seconds to {arg}.")
            ts[arg + "_next"] = now + timedelta(seconds = to_add) # Update ts with the next time Vector will be able to speak on that event/trigger
            ts[arg] = datetime.now() # Update the event in ts so I have a timestamp for when event/trigger occurred
            save_timestamps() 
            say(arg) 
    else:
        if arg != "news_intro": print(f"Vector isn't ready to talk about {arg} yet.")

# This makes Vector talk by looking up dialogue in the dlg file 
def say(arg_name):
    row_start = dic[arg_name]
    row_end = row_start + int(dlg[row_start][LINES]) # Use row_start and LINES (from dialogue file) to figure out where the dialogue starts/stops
    num_row = get_low(row_start,row_end-1)
    to_say = dlg[num_row][MOOD] # Vector's default mood is "normal", eventually he will say different dialogue based on his mood
    if arg_name == "wake_word"       : return # If wake_word then skip talking for a bit
    if arg_name == "news_intro"      : to_say = to_say + get_news() + get_weather("forecast") # if news then add to end of intro
    if arg_name == "joke_intro"      : to_say = to_say + get_joke() # if joke then add to end of intro
    if arg_name == "fact_intro"      : to_say = to_say + get_fact() # if fact then add to end of intro
    if arg_name == "time_intro"      : to_say = to_say + get_time() # Randomly announce the time
    if arg_name == "random_weather"  : to_say = get_weather("random_weather") # Randomly announce a weather fact
    if arg_name == "weather_forecast": to_say = get_weather("forecast")
    if arg_name == "stranger": to_say = to_say + get_pickupline()

    to_say = randomizer(to_say) # This replaces certain words with synonyms
    max_attempts = 15 # Had to add this after the last update. I'm having trouble getting control of Vector to speak
    current_attempts = 0
    
    while current_attempts < max_attempts:
        current_attempts = current_attempts + 1
        try:
            robot.conn.request_control()
            robot.audio.set_master_volume(VOL[config.voice_volume]) # Change voice volume to config setting
            robot.behavior.say_text(to_say, duration_scalar=1.15) # I slow voice down slightly to make him easier to understand
            if arg_name == "joke_intro":
                robot.anim.play_animation_trigger(random.choice(JOKE_ANIM)) # If a joke, play a random animation trigger
            robot.conn.release_control()
            robot.audio.set_master_volume(VOL[config.sound_volume]) # Change sound effects volume back to config setting
            return
        except:
            print("Couldn't get control of robot. Trying again to say: ", to_say)
            batt = robot.get_battery_state()
            print("Battery Level ", batt.battery_level, batt.battery_volts)
            time.sleep(1)

    if current_attempts == 15:
        print("Error getting control")

# When Vector talks in his sleep he starts by randomly mumbling
def say_sleep(arg_name):
    sleep_mumble = ""
    mumble = []
    mumble.append("lelumerrummelumwamera,")
    mumble.append("mellelmelumwarmel,")
    mumble.append("emmelmummemellerm,")
    mumble.append("memmumlemellemell,")
    mumble.append("memmemmellerrumwallamella,")
    mumble.append("rummelwammellrummerwimmenlemerell,")
    mumble.append("remellemmer,")
    mumble.append("ellemrumwellesserr,")
    mumble.append("memmbleblemmerwumble,")
    mumble.append("blemmerummberwuddlelempervermmondoodle,")
    sleep_mumble = random.choice(mumble)

    print("Okay, I am going into REM sleep now...")
    row_start = dic[arg_name]
    row_end = row_start + int(dlg[row_start][LINES])
    num_row = random.randint(row_start,row_end-1)
    to_say = dlg[num_row][MOOD]
    robot.conn.request_control()
    robot.anim.play_animation("anim_gotosleep_sleeploop_01") # Playing a sleep animation so Vector appears to sleep/snore while he's talking
    time.sleep(60)
    to_say = sleep_mumble + to_say
    robot.audio.set_master_volume(VOL[1])
    robot.behavior.say_text(to_say, duration_scalar=2.0)
    robot.anim.play_animation("anim_gotosleep_sleeploop_01")
    #say("wake_up") # Vector always wakes up after he talks, so I have him say something about waking up
    robot.audio.set_master_volume(VOL[config.sound_volume])
    robot.conn.release_control()

###############################################################################
def average(number1, number2):
    return (number1 + number2) / 2

###############################################################################
# An API call that allows Vector to deliver a weather forecast (it's not always accurate, in my experience)
def get_weather(var):
    
    rnd_weather = []
    
    try:
        #location can be city, state; city, country; zip code.
        if var == "forecast":
            url = f"http://api.openweathermap.org/data/2.5/forecast?APPID={config.api_weather}&q={config.weather_location}&units={config.temperature}"
        else:
            url = f"http://api.openweathermap.org/data/2.5/weather?APPID={config.api_weather}&q={config.weather_location}&units={config.temperature}"
        req = urllib.request.Request(
            url,
            data=None,
            headers={}
            )
        data = urllib.request.urlopen(req).read()
        output = json.loads(data)

        if var == "forecast":
            section =output["list"][0]
            forecast_condition = section["weather"][0]["description"]
            forecast_humidity = section["main"]["humidity"]
            forecast_temp = output["list"][0]["main"]["temp"]
            forecast_temp_high = int(round(section["main"]["temp_min"]))
            forecast_temp_low = int(round(section["main"]["temp_max"]))
            forecast_temp_avg = int(round(average(forecast_temp_high, forecast_temp_low)))
            forecast_wind = int(round(section["wind"]["speed"]))
        else:
            #10/23/2019 JDR free api, no forecast (weather.gov for US?)
            #forecast_condition = output["forecast"]["forecastday"][0]["day"]["condition"]["text"]
            #10/23/2019 JDR new API object
            current_condition = output["weather"][0]["description"]
            #forecast_avghumidity = output["forecast"]["forecastday"][0]["day"]["avghumidity"]
            current_humidity = output["main"]["humidity"]

            #weather_name = output["location"]["name"]
            #weather_region = output["location"]["region"]

            #New API, specify the units in the request
            #current_temp_feelslike = output["current"]["feelslike"]
            current_temp = int(round(average(output["main"]["temp_min"], output["main"]["temp_max"])))
            current_wind = output["wind"]["speed"]

        if config.temperature == "imperial":
            #forecast_temp_avg = output["forecast"]["forecastday"][0]["day"]["avgtemp_f"]
            #forecast_wind = output["forecast"]["forecastday"][0]["day"]["maxwind_kph"]
            wind_speed = " kilometers per hour"
        else:
            #forecast_temp_avg = output["forecast"]["forecastday"][0]["day"]["avgtemp_c"]
            #forecast_temp_high = output["forecast"]["forecastday"][0]["day"]["maxtemp_c"]
            #forecast_temp_low = output["forecast"]["forecastday"][0]["day"]["mintemp_c"]
            #forecast_wind = output["forecast"]["forecastday"][0]["day"]["maxwind_mph"]
            wind_speed = " miles per hour"

        # In the morning, Vector tells the news and weather when he sees a face
        if var == "forecast":
            weather = []
            weather.append(f". And now for some weather. Today in {config.weather_location}, it will be {forecast_condition}, with a temperature of {forecast_temp_high} degrees, and wind speeds around {forecast_wind}{wind_speed}.")
            weather.append(f". Later today in {config.weather_location}, it will be {forecast_condition}, with a high of {forecast_temp_high} degrees and a low of {forecast_temp_low} degrees.")
            weather.append(f". Here's your local weather in {config.weather_location}. The high today will be {forecast_temp_high} degrees, and look for a low of around {forecast_temp_low}. Winds will be {forecast_wind}{wind_speed}.")
            weather.append(f". Later today it will be {forecast_condition} in {config.weather_location}, with an average temperature of {forecast_temp_avg} degrees, and wind speeds around {forecast_wind}{wind_speed}.")
            return(random.choice(weather))

        # At random times, Vector will see a face and announce something about the weather
        if var == "random_weather":
            rnd_weather = []
            #if {current_temp} != {current_temp_feelslike}:
            #   rnd_weather.append(f"The current temperature is {current_temp} degrees, but it feels like {current_temp_feelslike} degrees.")
            rnd_weather.append(f"Right now, the temperature is {current_temp} degrees.")

            if current_wind < 15:
                rnd_weather.append(f"Right now in {config.weather_location}, it is a relatively calm {current_temp} degrees, with winds at {current_wind}{wind_speed}.")
            else:
                rnd_weather.append(f"Right now in {config.weather_location}, it is a blustery {current_temp} degrees, with winds at {current_wind}{wind_speed}.")
                rnd_weather.append(f"At this moment in {config.weather_location}, the weather is {current_condition}.")
                rnd_weather.append(f"Hello. It is currently {current_temp} degrees in {config.weather_location}. The humidity is {current_humidity} percent.")

    except Exception as inst:
        print(traceback.format_exc())
        rnd_weather.append("I'm more of an indoor robot.")
        rnd_weather.append("I have no idea what it is like out there.")
        rnd_weather.append("I'm a robot, not a weather forecaster.")
        rnd_weather.append("I had trouble getting the weather for you.")

    return(random.choice(rnd_weather))

###############################################################################
# I was using an API, but the free account only gave me a few hundred accesses per week. Then I found an RSS feed that works great!
# Users can specify how many news stories to hear. If more than one I randomly choose a bridge to say between them (like "In other news...")
def get_news():
    say_count = 0
    bridge = [". And in other news. ", ". In OTHER news... ", ". Taking a look at other news. ", ". Here is another news item. ", ". Here is an interesting story. "]
    news = ""
    news_count = config.news_count
    feed = feedparser.parse(config.news_feed)
    
    listeTitle = []
    for post in feed.entries:
        listeTitle.append(post.title)
       
    while say_count < news_count:
        news = news + listeTitle[say_count] + random.choice(bridge)
        say_count = say_count+1
        news = news + listeTitle[say_count+1]
    return news   

def get_fact():
    num = len(facts)
    my_rand = random.randint(0,num-1)
    raw_fact = facts[my_rand]
    raw_fact = raw_fact + get_fact_end()
    return raw_fact

def get_fact_end():
    row_start = dic["fact_end"]
    row_end = row_start + int(dlg[row_start][LINES]) # Use row_start and LINES (from dialogue file) to figure out where the dialogue starts/stops
    num_row = get_low(row_start,row_end-1)
    return dlg[num_row][MOOD] # Vector's default mood is "normal", eventually he will say different dialogue based on his mood

def get_joke():
    num = len(jokes)
    my_rand = random.randint(0,num-1)
    raw_joke = jokes[my_rand]
    return raw_joke

def get_time():
    return time.strftime("%I:%M %p")

# if Vector recognizes a familiar face he will remember 60 seconds
def get_last_name(robot):
    global LAST_NAME

    seenFaces = robot.world.visible_faces

    if (datetime.now() - ts["last_saw_face"]).total_seconds() > 60:
       LAST_NAME = ""
    
    for face in seenFaces:
        ts["last_saw_face"] = datetime.now() # Update timestamp - Vector saw a face
        if len(face.name) > 0: # Did Vector recognize the face?
            ts["last_saw_name"] = datetime.now() # Update timestamp - Vector recognized a face
            LAST_NAME = face.name # Save name of person Vector recognized

    return LAST_NAME

def wake_up(robot):
    vector_react("wake_up")

    # If Vector saw a face within 60 seconds and he is fully charged, drive of the charger
    if "last_saw_face" in ts and (datetime.now() - ts["last_saw_face"]).total_seconds() < 60:
        try:
            robot.conn.request_control()
            robot.behavior.drive_off_charger() # Drive off the Charger
            robot.conn.release_control()
            return
        except:
            #print("Couldn't get control of robot. Trying again to say: ", to_say)
            time.sleep(1)

def get_pickupline():
    lines = {"How you doin?",
             "I don't know you.",
             "Have we met before?",
             "Hey you!",
             "Wilson!",
             "May I introduce myself, I am Vector",
             "Say Vector, I am, then your name so I can recognize you in the future",
             "Are you my mother?",
             "What are you doing in my house?"
             }
    my_rand = random.randint(0, lines.__len__() - 1)
    return lines[my_rand]


def on_wake_word(robot, event_type, event):
    vector_react("wake_word")
    user_intent = event.wake_word_end.intent_json
    if len(user_intent) > 0:
        j = json.loads(user_intent)
        print(j['type'])
        #print(UserIntentEvent.greeting_goodmorning)
        print(j)
        valid_response = ["greeting_goodmorning", "greeting_hello",
                          "imperative_come", "imperative_lookatme",
                          "weather_response"]
        if j['type'] == "weather_response":
            #allow vector to do his built in weather
            time.sleep(10)
            say("random_weather")
        else:
            if j['type'] in valid_response:
                print("valid response")
                reaction78u = random.choices(["joke_intro", "fact_intro", "time_intro", "random_weather", "last_saw_name"])
                print(reaction)
                say(reaction[0])



def on_user_intent(robot, event_type, event, done):
    user_intent = UserIntent(event)
    print(user_intent.intent_data)
    valid_response = [UserIntentEvent.greeting_goodmorning, UserIntentEvent.greeting_hello, UserIntentEvent.imperative_come, UserIntentEvent.imperative_lookatme, UserIntentEvent.weather_response]
    if user_intent.intent_event == any(valid_response):
        vector_react("user")


# Event handler code for Vector detecting his cube -- if he heard his wake_word he won't try to talk right away as he will forget what he was doing
def on_cube_detected(robot, event_type, event):
    if robot.proximity.last_sensor_reading.distance.distance_mm in range(40,100):
        if (datetime.now() - ts["wake_word"]).total_seconds() > 10: # It has been at least 10 seconds since someone used Vector's wake word
            vector_react("cube_detected")

# MAIN ******************************************************************************************************************************
args = anki_vector.util.parse_command_args()
with anki_vector.Robot(args.serial, enable_face_detection=True) as robot:
    robot.conn.release_control() # I release control so Vector will do his normal behaviors
    robot.audio.set_master_volume(VOL[config.sound_volume])

    vector_react("greeting")
    ftime = time.time() + 1 # Check for faces every second or two
    ltime = time.time() + 5 # Delay when telling random joke, fact, etc.
    ctime = time.time() + random.randint(200,400)
    carry_flag = False

    robot.events.subscribe(on_wake_word, Events.wake_word)
    robot.events.subscribe(on_cube_detected, Events.robot_observed_object)
    robot.camera.init_camera_feed()
    #robot.events.subscribe(on_user_intent, Events.user_intent)
    while True:

        # Get the name, I Vector sees a face
        get_last_name(robot)
    
        if robot.status.is_being_held:
            vector_react("picked_up")

        if robot.status.is_on_charger and time.time() > ctime:
            vector_react("charging")
            ctime = time.time() + 30

        if robot.status.is_in_calm_power_mode:
            vector_react("sleeping")

        if robot.status.is_cliff_detected:
            vector_react("cliff")

        if robot.status.is_carrying_block == True:
            if carry_flag == False:
                carry_flag = True
        else: # Vector is NOT holding his block - Not sure this code is working. (Vector sometimes drops his block, but he he thinks he's still holding it)
            if carry_flag == True:
                vector_react("dropped_block")
                carry_flag = False

        if robot.status.is_button_pressed:
            vector_react("button_pressed")

        #any time  datetime.now().hour < 12 and
        if (datetime.now() - ts["last_saw_face"]).total_seconds() < 5: # It's morning and Vector recently saw a face
            vector_react("news_intro")

        # if Vector is fully charged
        battery_state = robot.get_battery_state()
        if battery_state.battery_level == 3:
            wake_up(robot)

        distance_mm = robot.proximity.last_sensor_reading.distance.distance_mm
        if distance_mm in range(50,60):
            DIST_COUNT +=1
        else:
            DIST_COUNT = 0
        if DIST_COUNT == 10: # I added the counters after Anki broke the proximity checking. They say it's fixed now, so I should re-visit this code
            DIST_COUNT = 0
            print("Vector sees an object in front of him...")
            if robot.status.is_docking_to_marker == False and robot.status.is_being_held == False:
                if (datetime.now() - ts["cube_detected"]).total_seconds() > 10: # I don't want Vector to stop in front of his cube and say "What is this?" (need to work on this)
                    vector_react("object_detected")
                    robot.vision.enable_display_camera_feed_on_face(True)
                    time.sleep(5.0)
                    robot.vision.enable_display_camera_feed_on_face(False)

                else:
                    print("Vector saw his cube recently, skipping object announcement")

        touch_data = robot.touch.last_sensor_reading
        if touch_data is not None:
            is_being_touched = touch_data.is_being_touched
            if is_being_touched == True:
                vector_react("touched")

            # if Vectors battery is going low
            if not robot.status.is_on_charger:
                if battery_state.battery_volts <= 3.63:  # <3.61 was too low
                    vector_react("tired")
                    time.sleep(90)

                #if battery_state.battery_level < 2:
                    #robot.behavior.say_text("My battery level is low.")

            #if not anyrecognized and my_var.__sizeof__() > 0:
             #   if ts["last_saw_stranger"] + datetime.timedelta(0, 600) < datetime.now():
              #      ts["last_saw_stranger"] = datetime.now()
               #     vector_react("stranger")

        time.sleep(0.1) # Sleep then loop back (Do I need this? Should it be longer?)