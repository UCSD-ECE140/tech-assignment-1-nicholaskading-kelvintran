import random
import threading
import time

import paho.mqtt.client as paho
from paho import mqtt
import random


class Subscriber:
    def __init__(self, topic):
        self.topic = topic

        self.client = paho.Client(callback_api_version=paho.CallbackAPIVersion.VERSION1, client_id="", userdata=None,
                                  protocol=paho.MQTTv5)

        self.client.on_connect = self.on_connect

        self.client.tls_set(tls_version=mqtt.client.ssl.PROTOCOL_TLS)
        self.client.username_pw_set("common", "Password6543!")
        self.client.connect("d7e612be0a164aeb983a9486bef3c4bf.s1.eu.hivemq.cloud", 8883)

        self.client.on_subscribe = self.on_subscribe
        self.client.on_message = self.on_message

        self.client.subscribe(self.topic, qos=1)

    def run_loop(self):
        self.client.loop_start()

    def stop_loop(self):
        self.client.loop_stop()

    def on_subscribe(self, client, userdata, mid, granted_qos, properties=None):
        print("Subscribed: " + str(mid) + " " + str(granted_qos))

    def on_message(self, client, userdata, msg):
        print(f"SUBSCRIBED {msg.qos} [{msg.topic}] {msg.payload}")

    def on_connect(self, client, userdata, flags, rc, properties=None):
        print("CONNACK received with code %s." % rc)


class Publisher:
    def __init__(self, topic):
        self.topic = topic

        self.client = paho.Client(callback_api_version=paho.CallbackAPIVersion.VERSION1, client_id="", userdata=None,
                                  protocol=paho.MQTTv5)
        self.client.on_connect = self.on_connect

        self.client.tls_set(tls_version=mqtt.client.ssl.PROTOCOL_TLS)
        self.client.username_pw_set("nkading", "Password2389!")
        self.client.connect("d7e612be0a164aeb983a9486bef3c4bf.s1.eu.hivemq.cloud", 8883)

        self.client.on_publish = self.on_publish

        self.shutdown = False
    def run_publish_loop(self):
        self.shutdown = False
        while not self.shutdown:
            self.client.publish(self.topic, payload=str(random.randint(0,999)), qos=1)
            time.sleep(3)

    def run_loop(self):
        self.client.loop_start()
        self.t = threading.Thread(target=self.run_publish_loop, args=())
        self.t.start()


    def stop_loop(self):
        self.shutdown = True
        self.t.join()
        self.client.loop_stop()

    def on_publish(self, client, userdata, mid, properties=None):
        print(f"PUBLISHED to [{self.topic}]")
        # print("mid: " + str(mid))

    def on_connect(self, client, userdata, flags, rc, properties=None):
        print("CONNACK received with code %s." % rc)


if __name__ == "__main__":
    p1 = Publisher("school/topic1")
    p2 = Publisher("school/topic1")
    s1 = Subscriber("school/topic1")


    p1.run_loop()
    p2.run_loop()
    s1.run_loop()

    while True:
        time.sleep(1)
