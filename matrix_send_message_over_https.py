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
    if not os.path.exists(path):
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
    #data = response.raw      # a `bytes` object
    response_json = response.json()
    log.debug("response.json=%s"%response_json)
    if response.status_code != 200:
      log.error("response != 200 (OK)")
      return None
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

    if len(sys.argv)<5:
      log.error("need 4 param: matrix_address_to problem_uid subject message_to_send")
      sys.exit(1)

    zbx_to = sys.argv[1]
    zbx_problem_uid = sys.argv[2]
    zbx_subject = sys.argv[3]
    zbx_body = sys.argv[4]

    log.debug("zbx_to=%s"%zbx_to)
    log.debug("zbx_problem_uid=%s"%zbx_problem_uid)
    log.debug("zbx_subject=%s"%zbx_subject)
    log.debug("zbx_body=%s"%zbx_body)

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
      "address_im":zbx_to,\
      "sender_uniq_id":zbx_problem_uid\
      }
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
