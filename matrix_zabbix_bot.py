#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# A simple chat client for matrix.
# This sample will allow you to connect to a room, and send/recieve messages.
# Args: host:port username password room
# Error Codes:
# 1 - Unknown problem has occured
# 2 - Could not find the server.
# 3 - Bad URL Format.
# 4 - Bad username/password.
# 11 - Wrong room format.
# 12 - Couldn't find room.

import sys
import logging
import time
import json
import os
import pickle
import re
import threading
#import MySQLdb as mdb
import traceback
import requests

from matrix_client.client import MatrixClient
from matrix_client.api import MatrixRequestError
from matrix_client.api import MatrixHttpLibError
from requests.exceptions import MissingSchema
import sendemail as mail
import matrix_bot_api as mba
import matrix_bot_logic as mbl
import config as conf

client = None
log = None
data={}
lock = None

def get_exception_traceback_descr(e):
  tb_str = traceback.format_exception(etype=type(e), value=e, tb=e.__traceback__)
  result=""
  for msg in tb_str:
    result+=msg
  return result

def create_room(db_con,matrix_uid):
  global log
  global client

  cur=db_con["cur"]
  con=db_con["con"]
  # сначала спрашиваем у сервера, есть ли такой пользователь (чтобы не создавать просто так комнату):
  try:
    response = client.api.get_display_name(matrix_uid)
  except MatrixRequestError as e:
    log.error(get_exception_traceback_descr(e))
    log.error("Couldn't get user display name - may be no such user on server? username = '%s'"%matrix_uid)
    log.error("skip create room for user '%s' - need admin!"%matrix_uid)
    return False
  log.debug("Success get display name '%s' for user '%s' - user exist. Try create room for this is user"%(response,matrix_uid))

  try:
    room=client.create_room(is_public=False, invitees=None)
  except MatrixRequestError as e:
    log.error(get_exception_traceback_descr(e))
    log.debug(e)
    if e.code == 400:
      log.error("Room ID/Alias in the wrong format")
      return False
    else:
      log.error("Couldn't create room.")
      return False
  log.debug("New room created. room_id='%s'"%room.room_id)

  # приглашаем пользователя в комнату:
  try:
    response = client.api.invite_user(room.room_id,matrix_uid)
  except MatrixRequestError as e:
    log.debug(e)
    log.error("Can not invite user '%s' to room '%s'"%(matrix_uid,room.room_id))
    try:
      # Нужно выйти из комнаты:
      log.info("Leave from room: '%s'"%(room.room_id))
      response = client.api.leave_room(room.room_id)
    except:
      log.error("error leave room: '%s'"%(room.room_id))
      return False
    try:
      # И забыть её:
      log.info("Forgot room: '%s'"%(room.room_id))
      response = client.api.forget_room(room.room_id)
    except:
      log.error("error leave room: '%s'"%(room.room_id))
      return False
    return False
  log.debug("success invite user '%s' to room '%s'"%(matrix_uid,room.room_id))

  # обновляем базу:
  try:
    sql=u"insert into `matrix_rooms` (matrix_uid,user_room) VALUES ('%(matrix_uid)s','%(user_room)s')"\
      %{\
      "matrix_uid":matrix_uid,\
      "user_room":room.room_id\
      }
    log.debug("sql='%s'"%sql)
    cur.execute(sql)
    con.commit()
  except mdb.Error as e:
    log.error("Error %d: %s" % (e.args[0],e.args[1]))
    log.error(u"Ошибка работы с базой данных (%s: %s)" % (e.args[0],e.args[1]) )
    return False
  log.debug("create room '%s' and ivite user '%s' to this room"%(room.room_id,matrix_uid))

  # шлём help в комнаату:
  if mba.send_message(log,client,room.room_id,"Добро пожаловать в систему автоматического уведомления диспетчерских отключений АО \"ДРСК\"!")==False:
    log.error("mba.send_message()")
    return False
  return True
  
def connect_to_db():
  con=None
  cur=None
  try:
    con = mdb.connect(conf.send_db_host, conf.send_db_user, conf.send_db_passwd, conf.send_db_name, charset="utf8", use_unicode=True);
    cur = con.cursor()
  except mdb.Error as e:
    log.error("Error %d: %s" % (e.args[0],e.args[1]))
    log.error(u"Ошибка работы с базой данных (%s: %s)" % (e.args[0],e.args[1]) )
    return None
  result={}
  result["con"]=con
  result["cur"]=cur
  return result

def lock_table(db_con):
  cur=db_con["cur"]
  con=db_con["con"]
  # Блокируем базу для учёта обработки двумя роботами:
  try:
    sql=u"LOCK TABLES telegram WRITE"
    log.debug("sql: %s" % sql )
    cur.execute(sql)
  except mdb.Error as e:
    log.error("Error %d: %s" % (e.args[0],e.args[1]))
    log.error("Ошибка работы с базой данных (%s: %s)" % (e.args[0],e.args[1]) )
    return False
  return True

def unlock_table(db_con):
  cur=db_con["cur"]
  con=db_con["con"]
  # Блокируем базу для учёта обработки двумя роботами:
  try:
    sql=u"UNLOCK TABLES"
    log.debug("sql: %s" % sql )
    cur.execute(sql)
  except mdb.Error as e:
    log.error("Error %d: %s" % (e.args[0],e.args[1]))
    log.error("Ошибка работы с базой данных (%s: %s)" % (e.args[0],e.args[1]) )
    return False
  return True

def update_status_messages(db_con,room_id,matrix_uid,time_stamp):
  global log
  global lock
  cur=db_con["cur"]
  con=db_con["con"]
  
  time_string=time.strftime("%Y-%m-%d %T",time.localtime(time_stamp))
  log.debug("update_status_messages(): time_read=%s"%time_string)
  # проверяем, что у нас есть такое соответствие:
  data=None
  try:
    sql=u"select matrix_uid from `matrix_rooms` where matrix_uid='%(matrix_uid)s' and user_room='%(room_id)s'"\
      %{\
      "matrix_uid":matrix_uid,\
      "room_id":room_id\
      }
    log.debug("sql='%s'"%sql)
    cur.execute(sql)
    data=cur.fetchall()
  except mdb.Error as e:
    log.error("Error %d: %s" % (e.args[0],e.args[1]))
    log.error("Ошибка работы с базой данных (%s: %s)" % (e.args[0],e.args[1]) )
    return False
  if data==None:
    log.warning(u"У нас нет информации о таком пользователе (%s) в такой комнате: %s" % (matrix_uid,room_id) )
    return False
  # Известная связка комната-пользователь.
  # Выставляем статусы о прочтении:
  # Одним запросом не получилось, т.к. нельзя обновлять таблицу и тут же делать из неё выборку,
  # поэтому делаем в цикле по массиву идентификаторов:
  if lock_table(db_con)==False:
    log.error("lock_table()")
    return False
  data=None
  try:
    sql=u"select id from telegram where matrix_address='%(matrix_uid)s' and status='sent_by_matrix' and time_send<='%(time_string)s'"\
      %{\
      "matrix_uid":matrix_uid,\
      "time_string":time_string\
      }
    log.debug("sql='%s'"%sql)
    cur.execute(sql)
    data=cur.fetchall()
  except mdb.Error as e:
    log.error("Error %d: %s" % (e.args[0],e.args[1]))
    log.error(u"Ошибка работы с базой данных (%s: %s)" % (e.args[0],e.args[1]) )
    unlock_table(db_con);
    return False
  if data!=None:
    for item in data:
      uid=int(item[0])
      try:
        sql=u"update telegram set status='readed_by_matrix',time_read='%(time_string)s' where id=%(id)d"\
          %{\
          "time_string":time_string,\
          "id":uid\
          }
        log.debug("sql='%s'"%sql)
        cur.execute(sql)
        con.commit()
      except mdb.Error as e:
        log.error("Error %d: %s" % (e.args[0],e.args[1]))
        log.error(u"Ошибка работы с базой данных (%s: %s)" % (e.args[0],e.args[1]) )
        unlock_table(db_con);
        return False

  unlock_table(db_con);
  return True

def update_users_without_rooms(db_con):
  global log
  # проверяем, созданы ли комнаты для пользователей, у которых есть matrix ID.
  # если не созданы, то создаём и приглашаем их в эти комнаты.
  items=None
  cur=db_con["cur"]
  con=db_con["con"]

  # Берём matrix ID-ы у которых нет комнат
  try:
    sql=u"select matrix_uid from u_users where u_users.matrix_uid not in (select matrix_uid from matrix_rooms) and matrix_uid is not NULL and matrix_uid!=''"
    #log.debug("sql: %s" % sql )
    cur.execute(sql)
    items = cur.fetchall()
    if items==None:
      # все есть:
      return True
  except mdb.Error as e:
    log.error("Error %d: %s" % (e.args[0],e.args[1]))
    log.error(u"Ошибка работы с базой данных (%s: %s)" % (e.args[0],e.args[1]) )
    return False
  for item in items:
    matrix_id=item[0].strip().lower()
    if create_room(db_con,matrix_id.strip())==False:
      error=u"Ошибка создания комнаты для связи с пользователем '%s'" % matrix_id
      log.error(error)
  return True


# Called when a message is recieved.
def on_message(event):
    global client
    global log
    global lock
    log.debug("%s"%(json.dumps(event, indent=4, sort_keys=True,ensure_ascii=False)))
    if event['type'] == "m.room.member":
        if event['content']['membership'] == "join":
            log.info("{0} joined".format(event['content']['displayname']))
    elif event['type'] == "m.room.message":
        if event['content']['msgtype'] == "m.text":
            reply_to_id=None
            if "m.relates_to" in  event['content']:
              # это ответ на сообщение:
              try:
                reply_to_id=event['content']['m.relates_to']['m.in_reply_to']['event_id']
              except:
                log.error("bad formated event reply - skip")
                mba.send_message(log,client,event['room_id'],"Внутренняя ошибка разбора сообщения - обратитесь к разработчику")
                return False
            formatted_body=None
            format_type=None
            if "formatted_body" in event['content'] and "format" in event['content']:
              formatted_body=event['content']['formatted_body']
              format_type=event['content']['format']
            log.debug("{0}: {1}".format(event['sender'], event['content']['body']))
            log.debug("try lock before mbl.process_message()")
            with lock:
              log.debug("success lock before mbl.process_message()")
              if mbl.process_message(\
                  log,client,event['sender'],\
                  event['room_id'],\
                  event['content']['body'],\
                  formated_message=formatted_body,\
                  format_type=format_type,\
                  reply_to_id=reply_to_id,\
                  file_url=None,\
                  file_type=None\
                ) == False:
                log.error("error process command: '%s'"%event['content']['body'])
                mba.send_message(log,client,event['room_id'],"Внутренняя бота - обратитесь к разработчику")
                return False
        elif event['content']['msgtype'] == "m.image":
          try:
            file_type=event['content']['info']['mimetype']
            file_url=event['content']['url']
          except:
            log.error("bad formated event reply - skip")
            mba.send_message(log,client,event['room_id'],"Внутренняя ошибка разбора сообщения - обратитесь к разработчику")
            return False
          log.debug("{0}: {1}".format(event['sender'], event['content']['body']))
          log.debug("try lock before mbl.process_message()")
          with lock:
            log.debug("success lock before mbl.process_message()")
            if mbl.process_message(\
                log,client,event['sender'],\
                event['room_id'],\
                event['content']['body'],\
                formated_message=None,\
                format_type=None,\
                reply_to_id=None,\
                file_url=file_url,\
                file_type=file_type\
              ) == False:
              log.error("error process command: '%s'"%event['content']['body'])
              return False

    else:
      log.debug(event['type'])
    return True

def on_event(event):
    global log
    db_con=None
    cur=None
    con=None

    log.debug("event:")
    log.debug(event)
    log.debug(json.dumps(event, indent=4, sort_keys=True,ensure_ascii=False))
    for i in range(1,10):
      db_con=connect_to_db()
      if db_con == None:
        log.error("on_event(): connect_to_db()")
        log.info("on_event(): wait 120 seconds for reconnect...")
        time.sleep(120)
        continue
      else:
        break
    if db_con==None:
      log.error("on_event(): failed connect_to_db()")
      log.error("process on_event - failed: can not connect to mysql in connect_to_db()")
      return False
    else:
      cur=db_con["cur"]
      con=db_con["con"]
      

    if event['type'] == "m.receipt":
      for room_id in event['content']:
        if "m.read" in event['content'][room_id]:
          for matrix_uid in event['content'][room_id]["m.read"]:
            time_stamp=int(int(event['content'][room_id]["m.read"][matrix_uid]["ts"])/1000)
            time_string=time.strftime("%Y-%m-%d %T",time.localtime(time_stamp))
            log.info(u"Пришло уведомление о прочтении польльзователем '%s' сообщений ранее: %s"%(matrix_uid,time_string))
            if update_status_messages(db_con,room_id,matrix_uid,time_stamp) == False:
              log.warning(u"ошибка обновления статуса о прочтении -  update_status_messages(room_id=%s, matrix_uid=%s, time_stamp=%d) == False"%(room_id,matrix_uid,time_stamp))
              continue
    else:
      log.debug(event['type'])
    con.close()
    return True


def on_invite(room, event):
    global client
    global log

    if conf.debug:
      log.debug("invite:")
      log.debug("room_data:")
      log.debug(room)
      log.debug("event_data:")
      log.debug(event)
      log.debug(json.dumps(event, indent=4, sort_keys=True,ensure_ascii=False))

    # По приглашению не вступаем с точки зрения безопасности. Только мы можем приглашать в комнаты, а не нас:
    # Просматриваем сообщения:
#    for event_item in event['events']:
#      if event_item['type'] == "m.room.join_rules":
#        if event_item['content']['join_rule'] == "invite":
#          # Приглашение вступить в комнату:
#          log.debug("join to room: %s"%room)
#          room = client.join_room(room)
#          room.send_text("Спасибо за приглашение! Недеюсь быть Вам полезным. :-)")
#          room.send_text("Для справки по доступным командам - неберите: '!help' (или '!?', или '!h')")

def matrix_connect():
    global log
    global lock

    client = MatrixClient(conf.matrix_server)
    try:
        token = client.login(username=conf.matrix_username, password=conf.matrix_password,device_id=conf.matrix_device_id)
    except MatrixRequestError as e:
        log.error(e)
        log.debug(e)
        if e.code == 403:
            log.error("Bad username or password.")
            return None
        else:
            log.error("Check your sever details are correct.")
            return None
    except MatrixHttpLibError as e:
        log.error(e)
        return None
    except MissingSchema as e:
        log.error("Bad URL format.")
        log.error(e)
        log.debug(e)
        return None
    except:
        log.error("unknown error at client.login()")
        return None
    return client

def exception_handler(e):
  global log
  log.error("exception_handler(): main listener thread except. He must retrying...")
  log.error(e)
  log.info("exception_handler(): wait 5 second before retrying...")
  time.sleep(5)

def main():
    global client
    global data
    global log
    global lock

    con=None
    cur=None

    lock = threading.RLock()

    #log.debug("try lock before main load_data()")
    #with lock:
    #  log.debug("success lock before main load_data()")
    for i in range(1,10):
      client = matrix_connect()
      if client==None:
        log.error("matrix_connect() - try reconnect")
#time.sleep(120)
        time.sleep(1)
        continue
      else:
        break
    if client == None:
      log.error("matrix_connect() fault! - exit")
      sys.exit(1)
     
    client.add_listener(on_message)
    #############FIXME
#    client.add_ephemeral_listener(on_event)
    #############FIXME
    client.add_invite_listener(on_invite)

    #client.start_listener_thread()
    client.start_listener_thread(exception_handler=exception_handler)
    #client.listen_forever(timeout_ms=30000, exception_handler=exception_handler,bad_sync_timeout=5)

    while True:
      #log.debug("try lock before main loop")
      ##################FIXME
      log.debug("new step")
      time.sleep(30)
      continue
      ##################FIXME
      db_con=connect_to_db()
      if db_con == None:
        log.error("connect_to_db()")
        log.info("wait 120 seconds for reconnect...")
        time.sleep(120)
        continue
      cur=db_con["cur"]
      con=db_con["con"]

      if update_users_without_rooms(db_con) == False:
        log.error("update_users_without_rooms()")
      con.close()
#      log.debug("new step")
      time.sleep(30)


if __name__ == '__main__':
  log=logging.getLogger("matrix_disp_bot")
  log_lib=logging.getLogger("matrix_client.client")
  if conf.debug:
    log.setLevel(logging.DEBUG)
  else:
    log.setLevel(logging.INFO)

  # create the logging file handler
  fh = logging.FileHandler(conf.log_path)
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
