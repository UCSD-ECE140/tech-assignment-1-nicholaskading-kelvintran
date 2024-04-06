import os
import json
from dotenv import load_dotenv

import paho.mqtt.client as paho
from paho import mqtt
import time


# setting callbacks for different events to see if it works, print the message etc.
def on_connect(client, userdata, flags, rc, properties=None):
    print("CONNACK received with code %s." % rc)


# with this callback you can see if your publish was successful
def on_publish(client, userdata, mid, properties=None):
    # print("mid: " + str(mid))
    pass


# print which topic was subscribed to
def on_subscribe(client, userdata, mid, granted_qos, properties=None):
    print("Subscribed: " + str(mid) + " " + str(granted_qos))


# print message, useful for checking if it was successful
def on_message(client, userdata, msg):
    # print("message: " + msg.topic + " " + str(msg.qos) + " " + str(msg.payload))
    topic_list = msg.topic.split("/")

    # Validate it is input we can deal with
    if topic_list[-1] in dispatch.keys():
        dispatch[topic_list[-1]](client, topic_list, msg.payload)


def print_scores(client, topic_list, payload):
    data = json.loads(payload.decode('utf8'))
    for t, s in data.items():
        print(f"{t}:{s}", end='  ')
    print("")


def print_game_state(client, topic_list, payload):
    state = json.loads(payload)
    # print(state)
    my_map = [[None for _ in range(5)] for _ in range(5)]

    playerpos = state["currentPosition"]

    def translate_pos(pos):
        return (pos[0] - playerpos[0] + 2, pos[1] - playerpos[1] + 2)

    def translate_pos_inv(pos):
        return (playerpos[0] - 2 + pos[0], playerpos[1] - 2 + pos[1])

    def within_range(pos):
        return 0 <= pos[0] < 5 and 0 <= pos[1] < 5

    my_map[2][2] = 6  # player position

    for i, set1 in enumerate(["enemyPositions", "coin1", "coin2", "coin3", "walls", "teammatePositions"]):
        for a in state[set1]:
            a = translate_pos(a)
            if within_range(a):
                my_map[a[0]][a[1]] = i

    for y in range(5):
        for x in range(5):
            game_pos = translate_pos_inv((y, x))
            if game_pos[0] < 0 or game_pos[0] > 9 or game_pos[1] < 0 or game_pos[1] > 9:
                dat = 4
            else:
                dat = my_map[y][x]
            if dat == 4:
                txt = "  ▨  "
            elif dat == 1:  # coin1
                txt = "  1  "
            elif dat == 2:  # coin2
                txt = "  2  "
            elif dat == 3:  # coin3
                txt = "  3  "
            elif dat == 6:
                txt = "  ❖  "
            elif dat == 0:
                txt = "  ☉  "
            elif dat == 5:
                txt = "  ☮  "
            else:
                txt = "  □  "
            print(txt, end='')
        print("")


def print_msg(client, topic_list, payload):
    data = json.loads(payload)
    if data["player_name"] != player_name:
        print(f"[{data['player_name']}]: {data['message']}")

game_finished = False
def handle_server_messages(client, topic_list, payload):
    msg = payload.decode('utf8')
    if msg == "Game Over: All coins have been collected":
        global game_finished
        game_finished = True
    else:
        print(f"SERVER MSG {msg}")


dispatch = {
    'lobby': handle_server_messages,
    'game_state': print_game_state,
    'scores': print_scores,
    'comms': print_msg,
}

if __name__ == '__main__':
    load_dotenv(dotenv_path='credentials.env')

    broker_address = os.environ.get('BROKER_ADDRESS')
    broker_port = int(os.environ.get('BROKER_PORT'))
    username = os.environ.get('USER_NAME')
    password = os.environ.get('PASSWORD')

    lobby_name = input("what lobby do you want to join? ")
    player_name = input("what's your player name? ")
    team_name = input("what's your team name? ")

    client = paho.Client(callback_api_version=paho.CallbackAPIVersion.VERSION1, client_id=player_name, userdata=None,
                         protocol=paho.MQTTv5)

    # enable TLS for secure connection
    client.tls_set(tls_version=mqtt.client.ssl.PROTOCOL_TLS)
    # set username and password
    client.username_pw_set(username, password)
    # connect to HiveMQ Cloud on port 8883 (default for MQTT)
    client.connect(broker_address, broker_port)

    # setting callbacks, use separate functions like above for better visibility
    client.on_subscribe = on_subscribe  # Can comment out to not print when subscribing to new topics
    client.on_message = on_message
    client.on_publish = on_publish  # Can comment out to not print when publishing to topics

    client.loop_start()

    client.subscribe(f"games/{lobby_name}/lobby")  # error messages
    client.subscribe(f'games/{lobby_name}/{player_name}/game_state')  # print board
    client.subscribe(f'games/{lobby_name}/scores')  # print current scores
    client.subscribe(f"games/{lobby_name}/{team_name}/comms")

    client.publish("new_game", json.dumps({'lobby_name': lobby_name,
                                           'team_name': team_name,
                                           'player_name': player_name}))

    while True:
        if game_finished:
            break

        command = input("")
        args = command.split(" ")
        arg_count = len(args)

        if command == "start":
            client.publish(f"games/{lobby_name}/start", "START")
        elif command == "up" or command == "u":
            print("moving up")
            client.publish(f"games/{lobby_name}/{player_name}/move", "UP")
        elif command == "down" or command == "d":
            print("moving down")
            client.publish(f"games/{lobby_name}/{player_name}/move", "DOWN")
        elif command == "left" or command == "l":
            print("moving left")
            client.publish(f"games/{lobby_name}/{player_name}/move", "LEFT")
        elif command == "right" or command == "r":
            print("moving right")
            client.publish(f"games/{lobby_name}/{player_name}/move", "RIGHT")
        elif command == "stop" or command == "s":
            client.publish(f"games/{lobby_name}/start", "STOP")
        elif command == "comms" or command == "c":
            msg = input("message: ")
            client.publish(f"games/{lobby_name}/{team_name}/comms", json.dumps({
                "player_name": player_name,
                "message": msg
            }))
