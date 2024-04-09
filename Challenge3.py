import math
import os
import json
import random
from typing import Optional

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


# The players game state is sent by the server, therefore before doing
#   any processing, wait for the server to send the data and then give
#   the go-ahead
players_game_state = {}


def print_game_state(client, topic_list, payload):
    """
    Save the game state retrieved from the server, and use it in another thread
    to do processing on it.
    :param client:
    :param topic_list:
    :param payload:
    """
    global players_game_state
    player_name = topic_list[2]
    state = json.loads(payload)
    players_game_state[player_name] = state
    players_game_state[player_name]["ready"] = True


def display_game_board(game_state):
    """
    Display the game board in console in a user-friendly way
    :param game_state:
    :return:
    """
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


# Class used for keeping track of the path taken to a coin in A*
class Point:
    def __init__(self, pos, prev, g, h):
        self.pos = pos
        self.prev_path = prev
        self.g = g
        self.h = h

    def get_f(self):
        return self.g + self.h


def is_blocked(game_state, pos):
    """
    Check if there is a collision object at a specific position RELATIVE TO THE PLAYER
    Collision objects: Walls, Teammates, Enemies, Map boundaries

    :param game_state:
    :param pos:
    :return:
    """
    block_objects = []
    block_objects.extend(game_state["walls"])
    block_objects.extend(game_state["teammatePositions"])
    block_objects.extend(game_state["enemyPositions"])

    playerpos = game_state["currentPosition"]

    game_pos = (playerpos[0] + pos[0], playerpos[1] + pos[1])
    if game_pos[0] < 0 or game_pos[0] > 9 or game_pos[1] < 0 or game_pos[1] > 9:
        return True

    for obj in block_objects:
        if (obj[0] - playerpos[0], obj[1] - playerpos[1]) == pos:
            return True

    return False


# Heuristic function for A*
def calculate_h_value(pos: (int, int), dest: (int, int)):
    return abs(pos[0] - dest[0]) + abs(pos[1] - dest[1])


def get_coin_path(game_state, target_coin) -> Optional[Point]:
    """
    Function that computes the POINT object that contains the path from the
    start point to the end point.
    :param game_state:
    :param target_coin:
    :return:
    """
    playerpos = game_state["currentPosition"]

    frontier = [Point((0, 0), None, 0, 0)]
    closed_path = {(0, 0): 0}

    while len(frontier) > 0:
        working_frontier = sorted(frontier[:], key=lambda x: x.get_f())
        frontier.clear()
        for point in working_frontier:
            for c in [(1, 0), (-1, 0), (0, 1), (0, -1)]:
                new_pos = (point.pos[0] + c[0], point.pos[1] + c[1])
                game_pos = (playerpos[0] + point.pos[0] + c[0], playerpos[1] + point.pos[1] + c[1])
                new_g = point.g + 1
                new_h = calculate_h_value(game_pos, target_coin)
                new_point = Point(new_pos, point, new_g, new_h)

                # print(f"{new_pos} valid={is_valid(new_pos)}")
                if game_pos[0] == target_coin[0] and game_pos[1] == target_coin[1]:
                    return new_point
                elif -2 <= new_pos[0] <= 2 and -2 <= new_pos[1] <= 2 and not is_blocked(game_state, new_pos) and (
                        new_pos not in closed_path.keys() or new_point.get_f() < closed_path[new_pos]):
                    frontier.append(Point(new_pos, point, new_g, new_h))
                    closed_path[new_pos] = new_point.get_f()

    return None


def compute_direction_to_coin(game_state, target_coin):
    """
    Compute the path as a list of moves from the start point to
    the end point.
    :param game_state:
    :param target_coin:
    :return:
    """
    path = get_coin_path(game_state, target_coin)
    if path is None:
        return None

    # print("computed final coin position")

    steps = []
    while True:
        path_parent = path.prev_path
        if path_parent is None:
            steps.reverse()
            return steps

        movement = (path.pos[0] - path_parent.pos[0], path.pos[1] - path_parent.pos[1])
        steps.append(movement)
        path = path_parent


def moving_direction_to_command(dir_coord):
    """
    Convert a movement direction to a command that is understood by
    the server.
    :param dir_coord:
    :return:
    """
    my_map = {(-1, 0): "UP",
              (0, -1): "LEFT",
              (1, 0): "DOWN",
              (0, 1): "RIGHT"}
    return my_map[dir_coord]


coin_fixation = {}


def pick_new_coin(game_state, coins):
    """
    If a coin is unreachable or exits from view, find a new VALID COIN
    to pick from.
    :param game_state:
    :param coins:
    :return:
    """
    for potential_coin in coins:
        direction_to_coin = compute_direction_to_coin(game_state, potential_coin)
        if direction_to_coin is not None:
            return potential_coin, direction_to_coin
    return None, None


# Use momentum parameter to catch coins quicker
player_momentum = {}
player_facing_direction = {}

if __name__ == "__main__":
    # def main():
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
        for player in players.keys():  # do movement computations for each player
            if game_finished:
                break
            while player not in players_game_state.keys() or players_game_state[player]["ready"] is False:
                time.sleep(0.2)  # if the game state is not ready for the player, wait until it is

            game_state = players_game_state[player]

            players_game_state[player]["ready"] = False

            playerpos = game_state["currentPosition"]

            all_coins = []
            all_coins.extend(game_state["coin3"])
            all_coins.extend(game_state["coin2"])
            all_coins.extend(game_state["coin1"])

            print(f"{player} -------------")
            print(game_state)

            direction_to_coin = None
            if player not in coin_fixation or coin_fixation[player] not in all_coins:
                # give one specific coin for each player to "fixate" on. Don't keep switching coins because of
                # context changes.
                coin, direction_to_coin = pick_new_coin(game_state, all_coins)

                if coin is not None:
                    coin_fixation[player] = coin
                else:
                    if player in coin_fixation:
                        del coin_fixation[player]
            else:
                print(f"using existing coin")
                direction_to_coin = compute_direction_to_coin(game_state, coin_fixation[player])

            if direction_to_coin:  # valid coin on screen. Do A* pathing.
                client.publish(f"games/{lobby_name}/{player}/move", moving_direction_to_command(direction_to_coin[0]))
            else:  # do random pathing
                if not is_blocked(game_state, player_facing_direction[player]):
                    if player in player_momentum.keys():
                        if player_momentum[player] > 0:
                            player_momentum[player] -= 0.25
                    else:
                        player_momentum[player] = 1

                    if random.random() < player_momentum[player]:
                        # tend to move player over larger distances in order for easier traversal of the map.
                        # (Pseudo-random motion)
                        client.publish(f"games/{lobby_name}/{player}/move",
                                       moving_direction_to_command(player_facing_direction[player]))
                        continue

                # if the forward direction is blocked, pick a new direction
                candidates = [(1, 0), (-1, 0), (0, -1), (0, 1)]
                valid_candidates = []
                for dir in candidates:
                    if not is_blocked(game_state, dir):
                        valid_candidates.append(dir)

                if len(valid_candidates)==1:
                    random_direction = valid_candidates[0]
                    player_momentum[player] = 1  # reset momentum for new direction
                    player_facing_direction[player] = random_direction

                    client.publish(f"games/{lobby_name}/{player}/move",
                                   moving_direction_to_command(random_direction))
                elif len(valid_candidates)>1:
                    i = random.randint(0, len(valid_candidates) - 1)
                    random_direction = valid_candidates[i]  # pick from valid direction

                    player_momentum[player] = 1  # reset momentum for new direction
                    player_facing_direction[player] = random_direction

                    client.publish(f"games/{lobby_name}/{player}/move",
                                   moving_direction_to_command(random_direction))
                else:
                    print("player trapped. critical error")

            time.sleep(0.5)

    print("game finished")
    print("final scores: ", end='')
    for t, s in latest_scores.items():
        print(f"{t}:{s}", end=' ')
    print("")
