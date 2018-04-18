#!/usr/bin/env python
# -*- coding: utf-8 -*-
import config as conf
from matrix_client.client import MatrixClient
import sys

severity_types={\
  "Disaster":"Чрезвычайная",\
  "High":"Высокая",\
  "Average":"Средняя",\
  "Warning":"Предупреждение",\
  "Information":"Информация",\
  "Not classified":"Не классифицировано"\
}

status_types={\
  "OK":"Решена проблема",\
  "PROBLEM":"Проблема"\
}

zbx_to = sys.argv[1]
zbx_subject = sys.argv[2]
zbx_body = sys.argv[3]

room_dst=conf.room_info

keys=zbx_subject.split(';')
if len(keys) > 1:
  status=keys[0]
  severity=keys[1]
  trigger_name=keys[2]
  if status in status_types and severity in severity_types:
    zbx_subject = status_types[status] + "; " + severity_types[severity] + "; " + trigger_name

client = MatrixClient(conf.server)

# New user
#token = client.register_with_password(username=conf.username, password=conf.password)

# Existing user
token = client.login_with_password(username=conf.username, password=conf.password)

room = client.join_room(zbx_to)

text="""%(zbx_subject)s
%(zbx_body)s
"""%{"zbx_subject":zbx_subject, "zbx_body":zbx_body}

ret=room.send_text(text)
