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
import traceback
import re
import requests
import matrix_bot_api as mba
import matrix_bot_logic_zabbix as mblz
import config as conf
from matrix_client.client import MatrixClient
from matrix_client.api import MatrixRequestError
from matrix_client.api import MatrixHttpLibError
from requests.exceptions import MissingSchema

client = None
log = None
logic={}
lock = None
memmory = {}

def get_exception_traceback_descr(e):
  tb_str = traceback.format_exception(etype=type(e), value=e, tb=e.__traceback__)
  result=""
  for msg in tb_str:
    result+=msg
  return result

def process_message(log,client,user,room,message,formated_message=None,format_type=None,reply_to_id=None,file_url=None,file_type=None):
  global logic
  global memmory
  source_message=None
  source_cmd=None

  # Проверяем сколько в комнате пользователей. Если более двух - то это не приватный чат и потому не отвечаем на команды:

  users = client.rooms[room].get_joined_members()
  if users == None:
    log.error("room.get_joined_members()")
    return False
  users_num = len(users)
  log.debug("in room %d users"%users_num)
  if users_num > 2:
    # публичная комната - не обрабатываем команды:
    log.debug("this is public room - skip proccess_commands")
    return True
  else:
    log.debug("this is private chat (2 users) - proccess commands")

  if reply_to_id!=None and format_type=="org.matrix.custom.html" and formated_message!=None:
    # разбираем, чтобы получить исходное сообщение и ответ
    source_message=re.sub('<mx-reply><blockquote>.*<\/a><br>','', formated_message)
    source_message=re.sub('</blockquote></mx-reply>.*','', source_message)
    source_cmd=re.sub(r'.*</blockquote></mx-reply>','', formated_message.replace('\n',''))
    log.debug("source=%s"%source_message)
    log.debug("cmd=%s"%source_cmd)
    message=source_cmd

  # обработка по логике
  log.debug("get cmd: %s"%message)
  log.debug("user=%s"%user)
  if user == conf.matrix_username or "@%s:"%conf.matrix_username in user:
    log.debug("message from us - skip")
    return True
  state=get_state(log,user)
  if state==None:
    log.error("get_state(log,%s)"%user)
    return False

  for cmd in state:
    if message.lower() == u"отмена" or message.lower() == "cancel" or message.lower() == "0":
      # Стандартная команда отмены - перехода в начальное меню:
      set_state(user,logic)
      text="Переход в начало меню. Наберите 'помощь' или 'help' для спрвки по командам"
      if mba.send_message(log,client,room,text) == False:
        log.error("send_message() to user")
        log.error("cur state:")
        log.error(state)
        return False
      return True

    if check_equal_cmd(state,message.lower(),cmd) or cmd == "*":
      data=state[cmd]
      # Шлём стандартное для этого состояния сообщение:
      if "message" in data:
        # поддержка переменных в сообщениях:
        text=replace_env2val(log,user,data["message"])
        if text==None:
          text=data["message"]
        if "message_type" in data and data["message_type"]=="html":
          if mba.send_html(log,client,room,text) == False:
            log.error("send_html() to user %s"%user)
            log.error("cur state:")
            log.error(state)
            return False
        else:
          if mba.send_message(log,client,room,text) == False:
            log.error("send_message() to user")
            log.error("cur state:")
            log.error(state)
            return False
      # Устанавливаем переданный пользователем текст, как переменную (если так описано в правиле логики бота):
      if "set_env" in data:
        set_env(user,data["set_env"],message)
      # Устанавливаем статическую переменную (значение может содержать переменную в {}):
      if "set_static_keys" in data:
        for key in data["set_static_keys"]:
          val=data["set_static_keys"][key]
          # в цикле заменяем значения переменной
          val=replace_env2val(log,user,val)
          if val == None:
            log.error("replace_env2val()")
            bot_fault(log,client,room)
            log.error("cur state:")
            log.error(state)
            return False
          set_env(user,key,val)
      # Проверяем, что должны сделать:
      # Отмена:
      if data["type"]=="sys_cmd_cancel":
        set_state(user,logic)
        return True
      # Обычная команда:
      if data["type"]=="cmd":
        set_state(user,data["answer"])
        return True

      # Отправка файла с данными из url:
      if data["type"]=="url_to_file":
        set_state(user,logic)
        # Подготовка URL:
        if "url" not in data:
          log.error("rule file has error logic: 'type':'url_to_file' have no 'url'")
          bot_fault(log,client,room)
          log.error("cur state:")
          log.error(state)
          return False
        url=data["url"]
        # Заменяем параметры:
        url=replace_env2val(log,user,url)
        if url == None:
          log.error("replace_env2val()")
          bot_fault(log,client,room)
          log.error("cur state:")
          log.error(state)
          return False
        file_name=get_env(user,"file_name")
        if file_name == None:
          log.error("not set file_name env")
          bot_fault(log,client,room)
          log.error("cur state:")
          log.error(state)
          return False
        content_type=get_env(user,"content_type")
        if content_type == None:
          log.error("not set content_type env")
          bot_fault(log,client,room)
          log.error("cur state:")
          log.error(state)
          return False
        log.debug("send file. Data get from url: '%s'"%url)
        if send_report(log,client,user,room,url,content_type=content_type,file_name=file_name) == False:
          log.error("send_report(user=%(user)s, url='%(url)')"%{"user":user,"url":url})
          return False
        # Очищаем все переменные у пользователя
        memmory[user]["env"]={}
        set_state(user,logic)
        return True


      #=========================== zabbix =====================================
      if data["type"]=="zabbix_check_login":
        log.debug("message=%s"%message)
        log.debug("cmd=%s"%cmd)
        zabbix_user_name=get_env(user,"zabbix_login")
        if zabbix_user_name == None:
          log.error("get_env('zabbix_login')")
          if mba.send_message(log,client,room,"Внутренняя ошибка бота") == False:
            log.error("send_message() to user")
            return False
        zabbix_login=mblz.zabbix_check_login(log,zabbix_user_name)
        if zabbix_login == None:
          if mba.send_message(log,client,room,"Некорректный zabbix_login - попробуйте ещё раз") == False:
            log.error("send_message() to user")
            return False
          return True
        else:
          set_state(user,logic)
          set_env(user,"zabbix_login",zabbix_login)
          if mblz.zabbix_update_hosts_groups_of_user(log,user) == False:
            log.error('error save groups of user')
            if mba.send_message(log,client,room,"error save groups of user") == False:
              log.error("send_message() to user")
              return False
          if mba.send_message(log,client,room,"сохранил zabbix_login '%s' для вас. Теперь вы будет получать статистику из групп, в которые входит этот пользователь\nВернулся в основное меню"%zabbix_login) == False:
            log.error("send_message() to user")
            return False
          return True
          
      if data["type"]=="zabbix_get_version":
        log.debug("message=%s"%message)
        log.debug("cmd=%s"%cmd)
        return mblz.zabbix_get_version(log,logic,client,room,user,data,message,cmd)
      if data["type"]=="zabbix_show_stat":
        log.debug("message=%s"%message)
        log.debug("cmd=%s"%cmd)
        return mblz.zabbix_show_stat(log,logic,client,room,user,data,message,cmd)
      if data["type"]=="zabbix_show_triggers":
        log.debug("message=%s"%message)
        log.debug("cmd=%s"%cmd)
        return mblz.zabbix_show_triggers(log,logic,client,room,user,data,message,cmd)
      #=========================== zabbix  - конец =====================================

  if get_state(log,user) == logic:
    # Пользователь пишет что попало в самом начале диалога:
    if mba.send_message(log,client,room,"Не понял Вас. Пожалуйста, введите 'помощь' или 'help' для справки по известным мне командам") == False:
      log.error("send_message() to user")
      return False
  else:
    if mba.send_message(log,client,room,"Не распознал команду - похоже я её не знаю... Пожалуйста, введите варианты описанные выше или 'отмена' или '0'") == False:
      log.error("send_message() to user")
      return False
  return True

def replace_env2val(log,user,val):
  all_env=get_env_list(user)
  if all_env == None:
    # Нет переменных, возвращаем неизменную строку:
    return val
  for env_name in all_env:
    env_val=get_env(user,env_name)
    if env_val == None:
      return None
    if type(env_val) == str: # or type(env_val) == unicode:
      val=val.replace("{%s}"%env_name,env_val,100)
    elif type(env_val) == float:
      val=val.replace("{%s}"%env_name,"%f"%env_val,100)
    elif type(env_val) == int:
      val=val.replace("{%s}"%env_name,"%d"%env_val,100)
    else:
      log.warning("unsupported type of env. env_name=%s, type=%s"%(env_name,type(env_val)))
  return val


def bot_fault(log,client,room):
  if mba.send_message(log,client,room,"Внутренняя ошибка бота - пожалуйста, обратитесь в отдел ИТ") == False:
    log.error("send_message() to user")
    log.error("cur state:")
    log.error(state)
    return False
  return True

def go_to_main_menu(log,logic,client,room,user):
  log.debug("go_to_main_menu()")
  log.info("return to main menu in logic")
  if mba.send_notice(log,client,room,u"возвращаюсь в начальное меню. Отправьте 'помощь' или '1' для получения справки.") == False:
    log.error("send_notice() to user %s"%user)
  reset_user_memmory(user)
  set_state(user,logic)
  return True

def check_equal_cmd(state,message,key):
  global logic
  if message == key:
    return True
  if "aliases" in state[key]:
    for alias in state[key]["aliases"]:
      if message == alias:
        return True
  return False

def get_env(user,env_name):
  global memmory
  if user not in memmory:
    return None
  if "env" not in memmory[user]:
    return None
  if env_name not in memmory[user]["env"]:
    return None
  return memmory[user]["env"][env_name]

def get_env_list(user):
  global memmory
  if user not in memmory:
    return None
  if "env" not in memmory[user]:
    return None
  return memmory[user]["env"]

def set_env(user,env_name,env_val):
  global memmory
  if user not in memmory:
    memmory[user]={}
  if "env" not in memmory[user]:
    memmory[user]["env"]={}
  memmory[user]["env"][env_name]=env_val
  return True

def set_state(user,state):
  global memmory
  global logic
  if user not in memmory:
    memmory[user]={}
  memmory[user]["state"]=state
  return True

def reset_user_memmory(user):
  global memmory
  if user in memmory:
    del memmory[user]
  return True

def get_state(log,user):
  global memmory
  global logic
  if user in memmory:
    if "state" not in memmory[user]:
      log.error("memmory corrupt for user %s - can not find 'state' struct"%user)
      return None
    else:
      return memmory[user]["state"]
  else:
    # Иначе возвращаем начальный статус логики:
    return logic

def init(log,rule_file):
  global logic
  try:
    json_data=open(rule_file,"r",encoding="utf-8").read()
  except Exception as e:
    log.error("open file")
    log.error(get_exception_traceback_descr(e))
    return None
  try:
    logic = json.loads(json_data)
  except Exception as e:
    log.error("parse logic rule file: %s"%e)
    log.error(get_exception_traceback_descr(e))
    return False
  return True

def send_statistic(log,client,user,room,statistic_about,statistic_days):
  log.debug("send_statistic(%s,%s,%s,%s)"%(user,room,statistic_about,statistic_days))
  num=0
  mba.send_message(log,client, room,u"Формирую статистику...")
  # подключаемся к базе рассылок:
  try:
    con = mdb.connect(conf.send_db_host, conf.send_db_user, conf.send_db_passwd, conf.send_db_name, charset="utf8", use_unicode=True);
    cur = con.cursor()
  except mdb.Error as e:
    log.error("send_statistic(): error connect to db (%d: %s)" % (e.args[0],e.args[1]))
    return False
  # получаем статистику:
  about_text="всех пользователей"
  where_about=""
  if statistic_about == 'current_user':
    about_text=u"Вас"
    mail_address=""
    telegram_number=""
    sms_number=""
    # мало указать только адрес матрицы - запросы на отправку для пользователя могли быть в те времена, когда матрицы ещё не было:
    try:
      sql=u"select mail_address,telegram_number,sms_number from u_users where matrix_uid='%s'"%user
      log.debug("send_statistic(): sql: %s" % sql )
      cur.execute(sql)
      user_data = cur.fetchone()
      mail_address=user_data[0]
      telegram_number=user_data[1]
      sms_number=user_data[2]
    except mdb.Error as e:
      log.error("send_statistic(): sql error (%d: %s)" % (e.args[0],e.args[1]))
      return False
    or_where=""
    if mail_address != "" and mail_address != None:
      or_where+=" or email_address='%s' "%mail_address
    if telegram_number != "" and telegram_number != None:
      or_where+=" or address='%s' "%telegram_number
    if or_where=="":
      where_about=" and matrix_address='%s'"%user
    else:
      where_about=" and ( matrix_address='%s' "%user + or_where + ") "
  else:
    # для всех:
    about_text=u"всех пользователей"
    where_about="" 
  # временной лимит: 
  time_now=time.time()
  time_offset=time_now-int(statistic_days)*24*3600
  where_days="time_create > '%s'"%time.strftime('%Y-%m-%d %T',time.localtime(time_offset))

  count_all=0
  count_sent_by_matrix=0
  count_readed_by_matrix=0
  count_success_matrix=0
  count_success_telegram=0
  count_success_email=0
  count_success_with_errors=0
  count_errors=0
  count_fault=0
  # всего задач на отправку:
  try:
    sql=u"select count(*) from telegram where %s %s"%(where_days,where_about)
    log.debug("send_statistic(): sql: %s" % sql )
    cur.execute(sql)
    count_all = cur.fetchone()[0]
  except mdb.Error as e:
    log.error("send_statistic(): sql error (%d: %s)" % (e.args[0],e.args[1]))
    return False
  log.debug("count_all=%d"%count_all)
  # успешно отправлено через MATRIX:
  try:
    sql=u"select count(*) from telegram where status='sent_by_matrix' and %s %s"%(where_days,where_about)
    log.debug("send_statistic(): sql: %s" % sql )
    cur.execute(sql)
    count_sent_by_matrix = cur.fetchone()[0]
  except mdb.Error as e:
    log.error("send_statistic(): sql error (%d: %s)" % (e.args[0],e.args[1]))
    return False
  log.debug("count_sent_by_matrix=%d"%count_sent_by_matrix)
  # успешно прочитано через MATRIX:
  try:
    sql=u"select count(*) from telegram where status='readed_by_matrix' and %s %s"%(where_days,where_about)
    log.debug("send_statistic(): sql: %s" % sql )
    cur.execute(sql)
    count_readed_by_matrix = cur.fetchone()[0]
  except mdb.Error as e:
    log.error("send_statistic(): sql error (%d: %s)" % (e.args[0],e.args[1]))
    return False
  log.debug("count_readed_by_matrix=%d"%count_readed_by_matrix)

  # успешно через MATRIX:
  count_success_matrix=count_sent_by_matrix+count_readed_by_matrix
  log.debug("count_success_matrix=%d"%count_success_matrix)

  # успешно прочитано через Telegram:
  try:
    sql=u"select count(*) from telegram where status='sent_by_telegram' and %s %s"%(where_days,where_about)
    log.debug("send_statistic(): sql: %s" % sql )
    cur.execute(sql)
    count_success_telegram = cur.fetchone()[0]
  except mdb.Error as e:
    log.error("send_statistic(): sql error (%d: %s)" % (e.args[0],e.args[1]))
    return False
  log.debug("count_success_telegram=%d"%count_success_telegram)

  # успешно прочитано через почту:
  try:
    sql=u"select count(*) from telegram where status='sent_by_email' and %s %s"%(where_days,where_about)
    log.debug("send_statistic(): sql: %s" % sql )
    cur.execute(sql)
    count_success_email = cur.fetchone()[0]
  except mdb.Error as e:
    log.error("send_statistic(): sql error (%d: %s)" % (e.args[0],e.args[1]))
    return False
  log.debug("count_success_email=%d"%count_success_email)

  # пока ещё не отправлено (не было попыток отправить):
  try:
    sql=u"select count(*) from telegram where status='new' and %s %s"%(where_days,where_about)
    log.debug("send_statistic(): sql: %s" % sql )
    cur.execute(sql)
    count_new = cur.fetchone()[0]
  except mdb.Error as e:
    log.error("send_statistic(): sql error (%d: %s)" % (e.args[0],e.args[1]))
    return False
  log.debug("count_new=%d"%count_new)

  # отправка не удалась, но попытки продолжаются:
  try:
    sql=u"select count(*) from telegram where status='error' and %s %s"%(where_days,where_about)
    log.debug("send_statistic(): sql: %s" % sql )
    cur.execute(sql)
    count_errors = cur.fetchone()[0]
  except mdb.Error as e:
    log.error("send_statistic(): sql error (%d: %s)" % (e.args[0],e.args[1]))
    return False
  log.debug("count_errors=%d"%count_errors)

  # отправка не удалась, и попытки отправить прекращены:
  try:
    sql=u"select count(*) from telegram where status='fault' and %s %s"%(where_days,where_about)
    log.debug("send_statistic(): sql: %s" % sql )
    cur.execute(sql)
    count_fault = cur.fetchone()[0]
  except mdb.Error as e:
    log.error("send_statistic(): sql error (%d: %s)" % (e.args[0],e.args[1]))
    return False
  log.debug("count_fault=%d"%count_fault)

  # отправка удалась, но не с первого раза:
  try:
    sql=u"select count(*) from telegram where status like '%%sent%%' and retry_num > 1 and %s %s"%(where_days,where_about)
    log.debug("send_statistic(): sql: %s" % sql )
    cur.execute(sql)
    count_success_with_errors = cur.fetchone()[0]
  except mdb.Error as e:
    log.error("send_statistic(): sql error (%d: %s)" % (e.args[0],e.args[1]))
    return False
  log.debug("count_success_with_errors=%d"%count_success_with_errors)

  if con:    
    con.close()
  report=u"""<p><strong>Статистика по рассылке для %(about_text)s</strong></p>
<p>Всего за последние %(statistic_days)s дней было %(count_all)d запросов на рассылку для %(about_text)s. Из них:</p>
  <ul>
    <li>Ещё не отправлялись (я ещё не пробовал отправить): <strong>%(count_new)d</strong></li>
    <li>Успешно отправлено через MATRIX: <strong>%(count_success_matrix)d</strong> сообщений, из них прочитано %(count_readed_by_matrix)d сообщений</li>
    <li>Успешно отправлено через Telegram: <strong>%(count_success_telegram)d</strong> сообщений</li>
    <li>Успешно отправлено через почту: <strong>%(count_success_email)d</strong> сообщений</li>
    <li>Отправлено, но не с первого раза (либо не было связи, либо не указаны учётные данные по основным системам): <strong>%(count_success_with_errors)d</strong> сообщений</li>
    <li>Не получилось отправить, но попытки отправить всё ещё продолжаются: <strong>%(count_errors)d</strong> сообщений</li>
    <li>Не получилось отправить совсем (система прекратила попытки отправить): <strong>%(count_fault)d</strong> сообщений</li>
  </ul>
<p><em>Всего хорошего, с уважением служба ИТ.</em></p>
"""%{\
  "statistic_days":statistic_days,\
  "about_text":about_text,\
  "count_new":count_new,\
  "count_all":count_all,\
  "count_success_matrix":count_success_matrix,\
  "count_readed_by_matrix":count_readed_by_matrix,\
  "count_success_telegram":count_success_telegram,\
  "count_success_email":count_success_email,\
  "count_success_with_errors":count_success_with_errors,\
  "count_errors":count_errors,\
  "count_fault":count_fault\
}
  if mba.send_html(log,client,room,report) == False:
    log.error("send_statistic(): error mba.send_html()")
    return False

  return True

def send_report(log,client,user,room,report_url,content_type="application/vnd.ms-excel",file_name="Отчёт.xlsx"):
  log.debug("send_report(%s,%s,%s)"%(user,room,report_url))
  time_now=time.time()
  num=0
  mba.send_message(log,client, room,u"Формирую файл...")

  try:
    response = requests.get(report_url, stream=True)
    data = response.content      # a `bytes` object
  except:
    log.error("fetch report data from url: %s"%report_url)
    mba.send_message(log,client, room,u"Внутренняя ошибка сервера (не смог получить данные отчёта с сервера отчётов) - обратитесь к администратору")
    return False
    
#send_message(client, room,u"Файл готов, загружаю...")
  mxc_url=mba.upload_file(log,client,data,content_type)
  if mxc_url == None:
    log.error("uload file to matrix server")
    mba.send_message(log,client, room,u"Внутренняя ошибка сервера (не смог загрузить файл отчёта на сервер MATRIX) - попробуйте позже или обратитесь к администратору")
    return False
  log.debug("send file 1")
  if mba.send_file(log,client,room,mxc_url,file_name) == False:
    log.error("send file to room")
    mba.send_message(log,client, room,u"Внутренняя ошибка сервера (не смог отправить файл в комнату пользователю) - попробуйте позже или обратитесь к администратору")
    return False
  return True
