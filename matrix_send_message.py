#!/usr/bin/env python
# -*- coding: utf-8 -*-
import config as conf
from matrix_client.client import MatrixClient
import sys

zbx_to = sys.argv[1]
zbx_subject = sys.argv[2]
zbx_body = sys.argv[3]


client = MatrixClient(conf.server)

# New user
#token = client.register_with_password(username=conf.username, password=conf.password)

# Existing user
token = client.login_with_password(username=conf.username, password=conf.password)

room_info = client.join_room(conf.room_info)
room_major = client.join_room(conf.room_major)
room_critical = client.join_room(conf.room_critical)

text="""%(zbx_subject)s
%(zbx_body)s
"""%{"zbx_subject":zbx_subject, "zbx_body":zbx_body}

ret=room_info.send_text(text)
print("ret=",ret)
