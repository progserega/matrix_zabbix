#!/usr/bin/env python
# -*- coding: utf-8 -*-
import config as conf
from matrix_client.client import MatrixClient

client = MatrixClient(conf.server)

# New user
#token = client.register_with_password(username=conf.username, password=conf.password)

# Existing user
token = client.login_with_password(username=conf.username, password=conf.password)

room_info = client.join_room(conf.room_info)
room_major = client.join_room(conf.room_major)
room_critical = client.join_room(conf.room_critical)
ret=room_info.send_text("Hello!")
print("ret=",ret)
