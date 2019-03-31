#!/usr/bin/env python
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
import re
import requests
import matrix_bot_api as mba
import matrix_bot_logic as mbl
import config as conf
from matrix_client.api import MatrixRequestError
from pyzabbix import ZabbixAPI

def zabbix_get_version(log,logic,client,room,user,data,source_message,cmd):
  log.info("zabbix_get_version()")
  z = ZabbixAPI(conf.zabbix_server, user=conf.zabbix_user, password=conf.zabbix_passwd)
  answer = z.do_request('apiinfo.version')
  log.debug("zabbix version: %s"%answer['result'])
  if mba.send_message(log,client,room,u"Версия ZABBIX: %s"%answer['result']) == False:
    log.error("send_message() to user")
    mbl.bot_fault(log,client,room)
    return False
  mbl.go_to_main_menu(log,logic,client,room,user)
  return True

def zabbix_show_stat(log,logic,client,room,user,data,source_message,cmd):
  log.info("zabbix_show_triggers()")
  zabbix_groupid=mbl.get_env(user,"zabbix_groupid")
  if zabbix_groupid==None:
    log.debug("error get_env zabbix_groupid - return to main menu")
    mbl.bot_fault(log,client,room)
    mbl.go_to_main_menu(log,logic,client,room,user)
    return False

  if mba.send_notice(log,client,room,u"формирую статистику...") == False:
    log.error("send_notice() to user %s"%user)
    return False

  z = ZabbixAPI(conf.zabbix_server, user=conf.zabbix_user, password=conf.zabbix_passwd)

  triggers = z.trigger.get(groupids=[zabbix_groupid],only_true="1",active="1",min_severity=3,output="extend",selectFunctions="extend",expandDescription="True")
  if triggers==None:
    log.debug("error z.trigger.get() - return to main menu")
    mbl.bot_fault(log,client,room)
    mbl.go_to_main_menu(log,logic,client,room,user)
    return False
  priority_3_num=len(triggers)

  triggers = z.trigger.get(groupids=[zabbix_groupid],only_true="1",active="1",min_severity=4,output="extend",selectFunctions="extend",expandDescription="True")
  if triggers==None:
    log.debug("error z.trigger.get() - return to main menu")
    mbl.bot_fault(log,client,room)
    mbl.go_to_main_menu(log,logic,client,room,user)
    return False
  priority_4_num=len(triggers)

  triggers = z.trigger.get(groupids=[zabbix_groupid],only_true="1",active="1",min_severity=5,output="extend",selectFunctions="extend",expandDescription="True")
  if triggers==None:
    log.debug("error z.trigger.get() - return to main menu")
    mbl.bot_fault(log,client,room)
    mbl.go_to_main_menu(log,logic,client,room,user)
    return False
  priority_5_num=len(triggers)

  sev_5_num=priority_5_num
  sev_4_num=priority_4_num-sev_5_num
  sev_3_num=priority_3_num-priority_4_num

  text=u"""<p><strong>Список активных триггеров выбранной важности:</strong></p>
  <ui>
  """
  text+=u"<li>1. Критических проблем - %d шт.</li> "%sev_5_num
  text+=u"<li>2. Важных проблем - %d шт.</li> "%sev_4_num
  text+=u"<li>3. Средних проблем - %d шт.</li> "%sev_3_num
  text+=u"</ui>"
  if mba.send_html(log,client,room,text) == False:
    log.error("send_html() to user %s"%user)
    return False
  # Завершаем текущий этап и ждём ответа от пользователя:
  mbl.set_state(user,data["answer"])
  return True
   
def zabbix_show_triggers(log,logic,client,room,user,data,source_message,cmd):
  log.info("zabbix_show_triggers()")
  zabbix_priority=mbl.get_env(user,"zabbix_priority")
  if zabbix_priority==None:
    log.debug("error get_env zabbix_priority - return to main menu")
    mbl.bot_fault(log,client,room)
    mbl.go_to_main_menu(log,logic,client,room,user)
    return False
  zabbix_groupid=mbl.get_env(user,"zabbix_groupid")
  if zabbix_groupid==None:
    log.debug("error get_env zabbix_groupid - return to main menu")
    mbl.bot_fault(log,client,room)
    mbl.go_to_main_menu(log,logic,client,room,user)
    return False

  if mba.send_notice(log,client,room,u"формирую статистику...") == False:
    log.error("send_notice() to user %s"%user)
    return False

  z = ZabbixAPI(conf.zabbix_server, user=conf.zabbix_user, password=conf.zabbix_passwd)

  #Get List of available groups
  triggers = z.trigger.get(groupids=[zabbix_groupid],only_true="1",active="1",min_severity=zabbix_priority,output="extend",selectFunctions="extend",expandDescription="True")
  if triggers==None:
    log.debug("error z.trigger.get() - return to main menu")
    mbl.bot_fault(log,client,room)
    mbl.go_to_main_menu(log,logic,client,room,user)
    return False

  priority=u"среднего"
  if zabbix_priority == "5":
    priority=u"критического"
  elif zabbix_priority == "4":
    priority=u"важного"

  text=u"""<p>Список активных триггеров <strong>%s</strong> уровня:</p>
  <ui>
  """%priority
  index=1
  for trigger in triggers:
    if trigger["priority"] != zabbix_priority:
      continue
    text+="<li>"
    text+="%d. "%index
    text+=trigger['description']
    text+="</li>"
    #text+="\n"
    index+=1
    #print(trigger)
  text+="</ui>"
  if mba.send_html(log,client,room,text) == False:
    log.error("send_html() to user %s"%user)
    return False
  
  #mbl.go_to_main_menu(log,logic,client,room,user)
  if mba.send_notice(log,client,room,u"можете выбрать просмотр триггеров иной важности (1 - критические, 2 - важные, 3 - средние) или 0 - для выхода") == False:
    log.error("send_notice() to user %s"%user)
    return False
  return True
    

def rm_show_type_images(log,logic,client,room,user,data,source_message,cmd):
  log.info("rm_show_type_images()")

  # показываем текущее описание требуемых картинок:
  if rm_show_descr_images(log,logic,client,room,user)==False:
    log.error("rm_show_type_images()")
    mbl.bot_fault(log,client,room)
    mbl.go_to_main_menu(log,logic,client,room,user)
    return False

  # Получаем результат текущего требуемого типа фотографий:
  rm_current_need_photo_type=mbl.get_env(user,"rm_current_need_photo_type")
  if rm_current_need_photo_type==None:
    log.debug("error get_env rm_current_need_photo_type - return to main menu")
    mbl.bot_fault(log,client,room)
    mbl.go_to_main_menu(log,logic,client,room,user)
    return False

  if rm_current_need_photo_type != "end":
    log.info("switch to state rm_wait_images")
    # Переключаемся на получение команд от пользователя:
    mbl.set_state(user,data["answer"])
    return True
  else:
    if mba.send_message(log,client,room,u"Данная заявка НЕ требует установку ни наземлений ни охранных зон. Выхожу в главное меню.") == False:
      log.error("send_message() to user")
    mbl.go_to_main_menu(log,logic,client,room,user)
    return True

def rm_show_descr_images(log,logic,client,room,user):
  log.info("rm_show_descr_images()")
  rm_need_zazemlenie=mbl.get_env(user,"rm_need_zazemlenie")
  if rm_need_zazemlenie==None:
    log.debug("error get_env rm_need_zazemlenie - return to main menu")
    mbl.bot_fault(log,client,room)
    mbl.go_to_main_menu(log,logic,client,room,user)
    return False
  rm_need_ograzhdenie=mbl.get_env(user,"rm_need_ograzhdenie")
  if rm_need_ograzhdenie==None:
    log.debug("error get_env rm_need_ograzhdenie - return to main menu")
    mbl.bot_fault(log,client,room)
    mbl.go_to_main_menu(log,logic,client,room,user)
    return False
  if rm_need_zazemlenie == "need":
    if mba.send_html(log,client,room,u"Данная заявка требует установку <strong>заземлений</strong>. Отправьте мне фотографии <strong>заземлений</strong>:") == False:
      log.error("send_html() to user")
    mbl.set_env(user,"rm_need_zazemlenie","wait_images")
    mbl.set_env(user,"rm_current_need_photo_type","rm_need_zazemlenie")
    return True
  elif rm_need_ograzhdenie == "need":
    if mba.send_html(log,client,room,u"Данная заявка требует установку <strong>ограждений</strong>. Отправьте мне фотографии <strong>ограждений</strong>:") == False:
      log.error("send_html() to user")
    mbl.set_env(user,"rm_need_ograzhdenie","wait_images")
    mbl.set_env(user,"rm_current_need_photo_type","rm_need_ograzhdenie")
    return True
  else:
    mbl.set_env(user,"rm_current_need_photo_type","end")
    log.info("rm_show_descr_images() end photo receive")
    return True
  return True

def rm_goto_zayavka_num_enter(log,logic,client,room,user,data,message,cmd):
  log.info("rm_goto_zayavka_num_enter()")
  return_to_zayavka_enter=mbl.get_env(user,"return_to_zayavka_enter")
  if return_to_zayavka_enter!=None:
    log.debug("set return_to_zayavka_enter")
    mbl.set_state(user,return_to_zayavka_enter)
  else:
    log.debug("no return_to_zayavka_enter - reset state")
    if mba.send_notice(log,client,room,u"внутренняя ошибка бота - возвращаюсь в начальное меню. Отправьте 'помощь' или '1' для получения справки.") == False:
      log.error("send_notice() to user %s"%user)
    mbl.set_state(user,logic)
    return False

def rm_pre_select_zayavka(log,memmory,logic,client,room,user,data,message,cmd):
  log.debug("rm_pre_select_zayavka()")
  # сохраняем раздел для возможного повторного вопроса о номере заявки:
  state=mbl.get_state(log,user)
  if state==None:
    log.error("mbl.get_state(log,%s)"%user)
    return False
  log.debug("1: state=")
  log.debug(state)
  log.info("save cur_state to return_to_zayavka_enter")
  mbl.set_env(user,"return_to_zayavka_enter",state["answer"])
  return True
    
  if mba.send_notice(log,client,room,u"Перехожу в меню ввода номера заявки. Вы можете выбрать другой номер заявки или 0, для выхода в главное меню.") == False:
    log.error("send_notice() to user %s"%user)
    return False
  return True


def show_zayavka_detail(log,memmory,logic,client,room,user,data,message,cmd):
  log.debug("show_zayavka_detail()")
  # сохраняем раздел для возможного повторного вопроса о номере заявки:
  state=mbl.get_state(log,user)
  if state==None:
    log.error("mbl.get_state(log,%s)"%user)
    return False
  log.debug("1: state=")
  log.debug(state)
  log.info("save cur_state to return_to_zayavka_enter")
  mbl.set_env(user,"return_to_zayavka_enter",state)
  
  # Получаем номер заявки:
  try:
    zayavka_num=int(mbl.get_env(user,"rm_zayavka_num"))
  except:
    log.warning(u"user not enter num zayavka: user send: '%s'"%(mbl.get_env(user,"rm_zayavka_num")))
    if mba.send_message(log,client,room,u"Не смог распознать номер заявки. Пожалуйста, введите номер заявки числом") == False:
      log.error("send_message() to user")
    return False
  text="<strong>Детали заявки с номером %d:</strong>"%zayavka_num
  #TODO
  # TODO получить данные из АПИ:
  # Выставляем переменные:
  mbl.set_env(user,"rm_need_zazemlenie","need") # или not_need
  mbl.set_env(user,"rm_need_ograzhdenie","need")
  text+="<p>FIXME</p>"

  # выводим вопрос:
  text+="<p>Если всё верно - введите <strong>1</strong>,\nесли нет - введите <strong>2</strong>.</p>"

  if mba.send_html(log,client,room,text) == False:
    log.error("send_html() to user %s"%user)
    return False
  mbl.set_state(user,data["answer"])
  return True
