#!/usr/bin/env python
# -*- coding: utf-8 -*-
import config as conf
from matrix_client.client import MatrixClient
from matrix_client.api import MatrixRequestError
from requests.exceptions import MissingSchema
import sys
import time
import traceback
import logging
from logging import handlers

log = None

def get_exception_traceback_descr(e):
  tb_str = traceback.format_exception(etype=type(e), value=e, tb=e.__traceback__)
  result=""
  for msg in tb_str:
    result+=msg
  return result

def main():
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

  if conf.debug:
    log.debug(u"zbx_to=%s"%zbx_to)
    log.debug(u"zbx_subject=%s"%zbx_subject.decode('utf8'))
    log.debug(u"zbx_body=%s"%zbx_body.decode('utf8'))

  keys=zbx_subject.split(';')
  if len(keys) > 1:
    status=keys[0].strip()
    severity=keys[1].strip()
    trigger_name=keys[2].strip()
    if status in status_types and severity in severity_types:
      zbx_subject = status + "; " + severity_types[severity] + "; " + trigger_name

  client = MatrixClient(conf.matrix_server)

# New user
#token = client.register_with_password(username=conf.matrix_username, password=conf.matrix_password)

  token=None
# Existing user
  try:
    token = client.login(username=conf.matrix_username, password=conf.matrix_password,device_id=conf.matrix_device_id)
  except MatrixRequestError as e:
    log.error(get_exception_traceback_descr(e))
    if e.code == 403:
      log.error("Bad username or password.")
      sys.exit(4)
    else:
      log.error("Check your sever details are correct.")
      sys.exit(2)
  except MissingSchema as e:
    log.error(get_exception_traceback_descr(e))
    log.error("Bad URL format.")
    sys.exit(3)
  except:
    log.error("ERROR (unknown) login()!")
    sys.exit(5)

  room = None
  try:
    room = client.join_room(zbx_to)
  except MatrixRequestError as e:
    log.error(get_exception_traceback_descr(e))
    if e.code == 400:
      log.error("Room ID/Alias in the wrong format")
      sys.exit(11)
    else:
      log.error("Couldn't find room.")
      sys.exit(12)
  except:
    log.error("ERROR (unknown) join_room()!")
    sys.exit(13)

  text=None
  try:
    text="""%(zbx_subject)s
  %(zbx_body)s
  """%{"zbx_subject":zbx_subject, "zbx_body":zbx_body}
  except:
    log.error("ERROR (unknown) format message!")
    sys.exit(14)

  try:
    ret=room.send_text(text)
  except MatrixRequestError as e:
    log.error(get_exception_traceback_descr(e))
    log.error("ERROR send message!")
    sys.exit(15)
  except:
    log.error("ERROR (unknown) send message!")
    sys.exit(16)

  if 'event_id' in ret:
    if conf.debug:
      log.info("SUCCESS send message. Message ID=%s"%ret["event_id"])
  else:
    log.error("ERROR send message!")
    sys.exit(17)
      

if __name__ == '__main__':
  log=logging.getLogger("matrix_send_message")
  log_lib=logging.getLogger("matrix_client.client")
  if conf.debug:
    log.setLevel(logging.DEBUG)
  else:
    log.setLevel(logging.INFO)

  # create the logging file handler
  fh = logging.handlers.TimedRotatingFileHandler(conf.log_path_send_message, when=conf.log_backup_when, backupCount=conf.log_backup_count)
  formatter = logging.Formatter('%(asctime)s - %(name)s - %(filename)s:%(lineno)d - %(funcName)s() %(levelname)s - %(message)s')
  fh.setFormatter(formatter)

  if conf.debug:
    # логирование в консоль:
    #stdout = logging.FileHandler("/dev/stdout")
    stdout = logging.StreamHandler(sys.stdout)
    stdout.setFormatter(formatter)
    log.addHandler(stdout)
    log_lib.addHandler(stdout)

  # add handler to logger object
  log.addHandler(fh)
  log_lib.addHandler(fh)

  log.info("Program started")
  if mbl.init(log,conf.matrix_bot_logic_file)==False:
    log.error("error matrix_bot_logic.init()")
    sys.exit(1)

  if main()==False:
    log.error("error main()")
    sys.exit(1)
  log.info("Program exit!")
