#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import requests
from requests.exceptions import MissingSchema
import sys
import time
import traceback
import logging
from logging import handlers
import configparser
import os

log = None
config=None

def loadConfig(file_name):
  try:
    if not os.path.exists(file_name):
      print("no file: %s"%file_name)
      return None
    config = configparser.ConfigParser()
    config.read(file_name)
    return config
  except Exception as e:
    print(get_exception_traceback_descr(e))
    return None

def get_exception_traceback_descr(e):
  tb_str = traceback.format_exception(etype=type(e), value=e, tb=e.__traceback__)
  result=""
  for msg in tb_str:
    result+=msg
  return result

def send_json(url,json_data):
  global log
  try:
    log.debug("try send to '%s'"%url)
    time_execute=time.time()
    response = requests.post(url, json=json_data, verify=False)
    log.debug("response=%s"%response)
    if response.status_code != 200:
      log.error("response != 200 (OK)")
      return None
    else:
      log.info("send_json return code = 200 (OK)")
    data = response.text 
    log.debug("response.text=%s"%str(data))
    response_json = response.json()
    log.debug("response.json=%s"%response_json)
    log.debug("execute function time=%f"%(time.time()-time_execute))
    return response_json
  except Exception as e:
    log.error(get_exception_traceback_descr(e))
    return None

def main():
  try:
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
    config_api_url = config["sender_api"]["url"]
    config_api_key = config["sender_api"]["api_key"]
    config_edit_support = config["sendig_options"]["edit_support"]

    if len(sys.argv)<4:
      log.error("need 4 param: matrix_address_to subject message_to_send")
      sys.exit(1)

    zbx_to = sys.argv[1]
    zbx_subject = sys.argv[2]
    zbx_body = sys.argv[3]

    log.debug("zbx_to=%s"%zbx_to)
    log.debug("zbx_subject=%s"%zbx_subject)
    log.debug("zbx_body=%s"%zbx_body)

    # находим UID проблемы, т.к. передать его из zabbix-а не получается через параметр
    # https://www.zabbix.com/documentation/3.0/ru/manual/config/notifications/media/script
    zbx_problem_uid = None
    try:
      lines = zbx_body.split('\n')
      for line in lines:
        if "UID проблемы" in line or \
        "Original problem ID" in line:
          zbx_problem_uid = line.split(':')[1].strip()
          log.debug("success extract zbx_problem_uid='%s' from zbx_body"%zbx_problem_uid)
          break
    except Exception as e:
      log.warning(get_exception_traceback_descr(e))
      log.warning("get zbx_problem_uid from zbx_body - skip set zbx_problem_uid")

    keys=zbx_subject.split(';')
    if len(keys) > 1:
      status=keys[0].strip()
      severity=keys[1].strip()
      trigger_name=keys[2].strip()
      if status in status_types and severity in severity_types:
        zbx_subject = status + "; " + severity_types[severity] + "; " + trigger_name

    text=None
    try:
      text="""%(zbx_subject)s
%(zbx_body)s"""%{"zbx_subject":zbx_subject, "zbx_body":zbx_body}
    except Exception as e:
      log.error(get_exception_traceback_descr(e))
      sys.exit(2)

    json_data={\
      "api_key":config_api_key,\
      "message":text,\
      "type":"text",\
      "address_im":zbx_to\
      }

    if zbx_problem_uid is not None:
      json_data["sender_uniq_id"]=zbx_problem_uid

    if config_edit_support.lower() == "yes" or\
       config_edit_support.lower() == "true":
      json_data["edit_previouse"] = True

    ret = send_json(config_api_url,json_data)
    if ret == None:
      log.error("unknown error in send_json(%s)"%config_api_url)
      sys.exit(3)

    if 'status' in ret and ret["status"]=='success' and 'message_id' in ret:
      log.info("SUCCESS send message. Message ID=%s"%ret["message_id"])
    else:
      log.error("ERROR send message!")
      if 'description' in ret:
        log.error("description from api-service: %s"%ret["description"])
      sys.exit(4)
    return True
  except Exception as e:
    log.error(get_exception_traceback_descr(e))
    sys.exit(5)

if __name__ == '__main__':
  config_path = "/etc/zabbix/matrix_send_message_over_https.ini"
  config=loadConfig(config_path)
  if config == None:
    print("can not open config file at path: %s"%config_path)
    sys.exit(1)
  log=logging.getLogger("matrix_send_message_over_https")
  if config["logging"]["debug"].lower()=="yes":
    log.setLevel(logging.DEBUG)
  else:
    log.setLevel(logging.INFO)

  # create the logging file handler
  fh = logging.handlers.TimedRotatingFileHandler(config["logging"]["log_path"], when=config["logging"]["log_backup_when"], backupCount=int(config["logging"]["log_backup_count"]), encoding='utf-8')
  formatter = logging.Formatter('%(asctime)s - %(name)s - %(filename)s:%(lineno)d - %(funcName)s() %(levelname)s - %(message)s')
  fh.setFormatter(formatter)

  if config["logging"]["debug"].lower()=="yes":
    # логирование в консоль:
    #stdout = logging.FileHandler("/dev/stdout")
    stdout = logging.StreamHandler(sys.stdout)
    stdout.setFormatter(formatter)
    log.addHandler(stdout)

  # add handler to logger object
  log.addHandler(fh)

  log.info("Program started")
  if main()==False:
    log.error("error main()")
    sys.exit(6)
  log.info("Program SUCCESS exit")
