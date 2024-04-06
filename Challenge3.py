import math
import os
import json
import random

from dotenv import load_dotenv

import paho.mqtt.client as paho
from paho import mqtt
import time


def on_connect(client, userdata, flags, rc, properties=None):
    print("CONNACK received with code %s." % rc)


def on_publish(client, userdata, mid, properties=None):
    pass


def on_subscribe(client, userdata, mid, granted_qos, properties=None):
    print("Subscribed: " + str(mid) + " " + str(granted_qos))


def on_message(client, userdata, msg):
    topic_list = msg.topic.split("/")

    if topic_list[-1] in dispatch.keys():
        dispatch[topic_list[-1]](client, topic_list, msg.payload)


game_finished = False
latest_scores = {}


def handle_server_messages(client, topic_list, payload):
    msg = payload.decode('utf8')
    if msg == "Game Over: All coins have been collected":
        global game_finished
        game_finished = True
    elif msg == "Lobby name not found.":
        pass
    else:
        print(f"SERVER MSG {msg}")


def print_scores(client, topic_list, payload):
    data = json.loads(payload.decode('utf8'))
    global latest_scores
    latest_scores = data
    for t, s in data.items():
        print(f"{t}:{s}", end='  ')
    print("")


players_game_state = {}
player_facing_direction = {}


def print_game_state(client, topic_list, payload):
    global players_game_state
    player_name = topic_list[2]
    state = json.loads(payload)
    players_game_state[player_name] = state
    players_game_state[player_name]["ready"] = True


def display_game_board(game_state):
    my_map = [[None for _ in range(5)] for _ in range(5)]

    playerpos = game_state["currentPosition"]

    def translate_pos(pos):
        return (pos[0] - playerpos[0] + 2, pos[1] - playerpos[1] + 2)

    def translate_pos_inv(pos):
        return (playerpos[0] - 2 + pos[0], playerpos[1] - 2 + pos[1])

    my_map[2][2] = 6

    for i, set1 in enumerate(["enemyPositions", "coin1", "coin2", "coin3", "walls", "teammatePositions"]):
        for a in game_state[set1]:
            a = translate_pos(a)
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
            elif dat == 1:
                txt = "  1  "
            elif dat == 2:
                txt = "  2  "
            elif dat == 3:
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


dispatch = {
    'lobby': handle_server_messages,
    'game_state': print_game_state,
    'scores': print_scores,
}


def sign_(num):
    if num > 0:
        return 1
    elif num < 0:
        return -1
    else:
        return 0


def compute_dist(pos1, pos2):
    return math.sqrt(math.pow(pos1[0] - pos2[0], 2) + math.pow(pos1[1] - pos2[1], 2))


class Path:
    def __init__(self, pos, prev):
        self.pos = pos
        self.prev_path = prev


def is_blocked(game_state, pos):
    block_objects = []
    block_objects.extend(game_state["walls"])
    block_objects.extend(game_state["teammatePositions"])
    block_objects.extend(game_state["enemyPositions"])

    playerpos = game_state["currentPosition"]

    game_pos = (playerpos[0] + pos[0], playerpos[1] + pos[1])
    if game_pos[0] < 0 or game_pos[0] > 9 or game_pos[1] < 0 or game_pos[1] > 9:
        return True

    for obj in block_objects:
        rel_pos = (obj[0] - playerpos[0], obj[1] - playerpos[1])

        if rel_pos == pos:
            return True

    return False


def rotate_right(dir):
    if dir == (-1, 0):
        return (0, 1)
    elif dir == (0, 1):
        return (1, 0)
    elif dir == (1, 0):
        return (0, -1)
    else:
        return (-1, 0)


def compute_direction_to_coin(game_state):
    all_coins = []
    all_coins.extend(game_state["coin3"])
    all_coins.extend(game_state["coin2"])
    all_coins.extend(game_state["coin1"])
    if len(all_coins) == 0:
        return None

    playerpos = game_state["currentPosition"]

    poi = [Path((0, 0), None)]
    historical_pos = [(0, 0)]
    path_out = None

    while True:
        working_poi = poi[:]
        poi.clear()
        if path_out or len(working_poi) == 0:
            break

        for point in working_poi:
            for coin in all_coins:
                rel_pos = (coin[0] - playerpos[0], coin[1] - playerpos[1])
                if rel_pos == point.pos:
                    path_out = point
                    break

            candidates = [(1, 0), (-1, 0), (0, 1), (0, -1)]
            for c in candidates:
                rel_grid_pos = (point.pos[0] + c[0], point.pos[1] + c[1])
                if not (-2 <= rel_grid_pos[0] <= 2 and -2 <= rel_grid_pos[1] <= 2):
                    pass

                elif is_blocked(game_state, rel_grid_pos):

                    pass
                elif rel_grid_pos in historical_pos:
                    pass

                else:
                    poi.append(Path(rel_grid_pos, point))

                    historical_pos.append(rel_grid_pos)

    if not path_out:
        return None

    while True:
        path_parent = path_out.prev_path
        if path_parent.prev_path is None:
            return path_out.pos
        path_out = path_parent


def rotate_facing_direction(dir, times):
    for i in range(times):
        dir = rotate_right(dir)
    return dir


def facing_direction_to_command(dir_coord):
    my_map = {(-1, 0): "UP",
              (0, -1): "LEFT",
              (1, 0): "DOWN",
              (0, 1): "RIGHT"}
    return my_map[dir_coord]


if __name__ == "__main__":
    load_dotenv(dotenv_path='credentials.env')

    broker_address = os.environ.get('BROKER_ADDRESS')
    broker_port = int(os.environ.get('BROKER_PORT'))
    username = os.environ.get('USER_NAME')
    password = os.environ.get('PASSWORD')

    client = paho.Client(callback_api_version=paho.CallbackAPIVersion.VERSION1, client_id="BotMain", userdata=None,
                         protocol=paho.MQTTv5)

    client.tls_set(tls_version=mqtt.client.ssl.PROTOCOL_TLS)
    client.username_pw_set(username, password)
    client.connect(broker_address, broker_port)

    time.sleep(0.5)

    client.on_subscribe = on_subscribe
    client.on_message = on_message
    client.on_publish = on_publish

    client.loop_start()

    lobby_name = "BotLobby"

    client.subscribe(f"games/{lobby_name}/lobby")
    client.subscribe(f'games/{lobby_name}/+/game_state')
    client.subscribe(f'games/{lobby_name}/scores')

    players = {"Alex": "alpha", "Jake": "alpha", "Ben": "beta", "Alice": "beta"}

    for player, team in players.items():
        client.publish("new_game", json.dumps({'lobby_name': lobby_name,
                                               'team_name': team,
                                               'player_name': player}))
        player_facing_direction[player] = (-1, 0)

    time.sleep(1)

    client.publish(f"games/{lobby_name}/start", "START")

    while True:
        if game_finished:
            break
        for player in players.keys():
            if game_finished:
                break
            while player not in players_game_state.keys() or players_game_state[player]["ready"] is False:
                time.sleep(0.2)

            game_state = players_game_state[player]
            players_game_state[player]["ready"] = False
            facing_direction = player_facing_direction[player]

            playerpos = game_state["currentPosition"]

            direction_to_coin = compute_direction_to_coin(game_state)

            print(f"player game board [{player}]")
            display_game_board(game_state)

            if direction_to_coin:
                client.publish(f"games/{lobby_name}/{player}/move", facing_direction_to_command(direction_to_coin))
            else:
                candidates = [(1, 0), (-1, 0), (0, -1), (0, 1)]
                valid_candidates = []
                for dir in candidates:
                    if not is_blocked(game_state, dir):
                        valid_candidates.append(dir)

                i = random.randint(0, len(valid_candidates) - 1)
                facing_direction = valid_candidates[i]
                client.publish(f"games/{lobby_name}/{player}/move", facing_direction_to_command(facing_direction))

            time.sleep(0.5)
    print("game finished")
    print("final scores: ", end='')
    for t, s in latest_scores.items():
        print(f"{t}:{s}", end=' ')
    print("")
