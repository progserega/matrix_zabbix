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
import datetime
import json
import os
import re
import requests
import traceback
import matrix_bot_api as mba
import matrix_bot_logic as mbl
import config as conf
from matrix_client.api import MatrixRequestError
from pyzabbix import ZabbixAPI

def zabbix_test(log):
  zapi = zabbix_init(log)
  if zapi == None:
    log.error("zabbix_init()")
    return False

  # группы пользователя:
  print("группы пользователя semenov_sv:")
  groups=zabbix_get_user_groups_by_user(log,zapi,"semenov_sv")
  print("groups=",groups)
  print("groups len=",len(groups))
  groups_names=zabbix_get_user_groups_names(log,zapi,groups)

  print("groups_names=",groups_names)
  print("groups_names len=",len(groups_names))

  # группы хостов пользователя:
  print("группы хостов пользователя semenov_sv, к которым он имеет доступ:")
  groups=zabbix_get_hosts_groups_by_user(log,zapi,"semenov_sv")
  print("groups=",groups)
  print("groups len=",len(groups))
  groups_names=zabbix_get_hosts_groups_names(log,zapi,groups)

  print("groups_names=",groups_names)
  print("groups_names len=",len(groups_names))
  sys.exit(0)

  #Get List of problems
  problems = zapi.problem.get(\
      groupids=groups,\
#groupids=[19],\
#      hostids=[10410],\
      output=['eventid','objectid','clock','ns','name','severity'],\
      source=0,\
      object=0, # тип проблем - триггеры\
      sortfield=['eventid'], preservekeys=1,limit=100,recent=1,evaltype=0,\
      severities=[2,3,4,5],\
      sortorder='DESC',\
      selectSuppressionData=['maintenanceid','suppress_until']\
      )
  if problems == None:
    log.debug("error zapi.problems.get() - return to main menu")
    return False

  triggerids=[]
  for problemid in problems:
    problem=problems[problemid]
    triggerids.append(problem['objectid'])
    

  #Get List of triggers
  triggers = zapi.trigger.get(\
      output=['priority','expression','recovery_mode','recovery_expression','comments','url'],\
      selectHosts=['hostid'],\
      triggerids=triggerids,\
      monitored=1,skipDependent=1,preservekeys=1,\
      selectItems=['itemid','hostid','name','key_','value_type','units','valuemapid']\
      )
  if triggers==None:
    log.debug("error zapi.trigger.get() - return to main menu")
    return False

  hostids=[]
  for triggerid in triggers:
    trigger=triggers[triggerid]
    for item in trigger['hosts']:
      hostids.append(item['hostid'])

  #Get List of hosts
  hosts = zapi.host.get(hostids=hostids,output=['hostid','name','maintenanceid','maintenance_status','maintenance_type'])
  if hosts==None:
    log.debug("error zapi.host.get() - return to main menu")
    return False
    
  index=1
  for problemid in problems:
    problem=problems[problemid]
    triggerid=problem['objectid']
    if triggerid not in triggers:
#      log.debug("skip unknown trigger")
      continue
    trigger=triggers[triggerid]
#    print("trigger=",trigger)
    hostid=int(trigger['hosts'][0]['hostid'])
#    print("hostid=%d"%hostid)
#print("problem struct=",problems[problem])
    host=get_host_by_id(log,hosts,hostid)
    if host == None:
#      log.debug("skip unknown host")
      print("hosts=",hosts)
      continue
    data=get_time_str_from_unix_time(problem['clock'])
    period=get_period_str_from_ns(problem['clock'])
    print("номер: %d, дата наступления события: %s (продолжительность: %s), описание: '%s', хост: '%s'"%(index,data,period,problem['name'],host['name']))
    index+=1
  print("num problems=%d"%len(problems))

  return True
  for item in problems:
    log.debug(json.dumps(item, indent=4, sort_keys=True,ensure_ascii=False))
    sys.exit()

  #ret=zapi.user.get(output='extend',search={'alias':'semenov_sv'})
  ret=zapi.problem.get(output='extend',groupids=ret)
  print("ret=",ret)
  return True
  #ret_json=json.loads(ret)
  userid=ret[0]["userid"]
  #ret=zapi.user.get(search={'alias':'svc_ZBXT_340-00'})
  #ret=zapi.mediatype.get(output='extend',userids=[10])
  ret=zapi.usergroup.get(output='extend',userids=[userid])
  print("ret=",ret)
  return True

def get_period_str_from_ns(clock):
  now = datetime.datetime.now()
  begin = datetime.datetime.fromtimestamp(int(clock))
  delta= now - begin
  line = re.sub(r"\.[0-9]+$","",str(delta)) # убираем доли секунд
  return line

def get_time_str_from_unix_time(clock):
  return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(int(clock)))

def get_host_by_id(log,hosts,hostid):
  for host in hosts:
    if int(host['hostid'])==int(hostid):
      return host
  return None

def zabbix_get_problems_of_groups(log,zapi,groups):
  try:
    ret=zapi.problem.get(output='extend',groupids=groups)
    return ret
  except Exception as e:
    log.error(get_exception_traceback_descr(e))
    return None

def zabbix_check_login(log,username):
  try:
    zapi = zabbix_init(log)
    if zapi == None:
      log.error("zabbix_init()")
      return None
    ret=zapi.user.get(output='extend',search={'alias':username})
    log.debug(json.dumps(ret, indent=4, sort_keys=True,ensure_ascii=False))
    if len(ret) != 1:
      log.warning("users not one")
      return None
    else:
      return ret[0]['alias']
  except Exception as e:
    log.error(get_exception_traceback_descr(e))
    return None

def zabbix_get_hosts_groups_names(log,zapi,groups):
  try:
    ret=zapi.hostgroup.get(output='extend',groupids=groups)
    groups_names=[]
    for item in ret:
      groups_names.append(item['name'])
    return groups_names
  except Exception as e:
    log.error(get_exception_traceback_descr(e))
    return None

def zabbix_get_user_groups_names(log,zapi,groups):
  try:
    ret=zapi.usergroup.get(output=['usrgrpid','name'],usrgrpids=groups)
    groups_names={}
    for item in ret:
      groups_names[item['usrgrpid']]=item['name']
    return groups_names
  except Exception as e:
    log.error(get_exception_traceback_descr(e))
    return None

def zabbix_get_hosts_groups_by_user(log,zapi,username):
  try:
    ret=zapi.user.get(output='extend',search={'alias':username})
    if len(ret) != 1:
      log.warning("users not one")
      return None
    userid=int(ret[0]["userid"])
    log.debug("userid of %s = %d"%(username, userid))
    ret=zapi.usergroup.get(userids=userid,selectRights="yes")
    groups=[]
    for user_group in ret:
      for host_group in user_group['rights']:
        if host_group['permission'] != 0: # не запрещён доступ
          groups.append(host_group['id'])
    result=list(set(groups)) # исключаем дубли
    return result
  except Exception as e:
    log.error(get_exception_traceback_descr(e))
    return None

def zabbix_get_user_groups_by_user(log,zapi,username):
  try:
    ret=zapi.user.get(output='extend',search={'alias':username})
    if len(ret) != 1:
      log.warning("users not one")
      return None
    userid=int(ret[0]["userid"])
    log.debug("userid of %s = %d"%(username, userid))
    ret=zapi.usergroup.get(output=['usrgrpid'],userids=userid)
    groups=[]
    for item in ret:
      groups.append(item['usrgrpid'])
    result=list(set(groups)) # исключаем дубли
    return result
  except Exception as e:
    log.error(get_exception_traceback_descr(e))
    return None

def get_exception_traceback_descr(e):
  tb_str = traceback.format_exception(etype=type(e), value=e, tb=e.__traceback__)
  result=""
  for msg in tb_str:
    result+=msg
  return result

def zabbix_init(log,server=conf.zabbix_server,user=conf.zabbix_user,passwd=conf.zabbix_passwd):
  try:
    #stream = logging.StreamHandler(sys.stdout)
    #if conf.debug:
    #  stream.setLevel(logging.DEBUG)
    #else:
    #  stream.setLevel(logging.ERROR)
    #log_zabbix = logging.getLogger('pyzabbix')
    #log_zabbix.addHandler(stream)
    #if conf.debug:
    #  log_zabbix.setLevel(logging.DEBUG)
    #else:
    #  log_zabbix.setLevel(logging.ERROR)

    z = ZabbixAPI(server)
    z.login(user,passwd)
    return z
  except Exception as e:
    log.error(get_exception_traceback_descr(e))
    return None

def zabbix_get_version(log,logic,client,room,user,data,source_message,cmd):
  try:
    log.info("zabbix_get_version()")
    zapi = zabbix_init(log)
    if zapi == None:
      log.error("zabbix_init()")
      return False
    answer = zapi.do_request('apiinfo.version')
    log.debug("zabbix version: %s"%answer['result'])
    if mba.send_message(log,client,room,u"Версия ZABBIX: %s"%answer['result']) == False:
      log.error("send_message() to user")
      mbl.bot_fault(log,client,room)
      return False
    mbl.go_to_main_menu(log,logic,client,room,user)
  except Exception as e:
    log.error(get_exception_traceback_descr(e))
    return False
  return True

def zabbix_update_hosts_groups_of_user(log,user):
  try:
    groups=[59] # по-умолчанию - ВЭФ ИБП
    zabbix_login=mbl.get_env(user,"zabbix_login")
    if zabbix_login!=None:
      zapi = zabbix_init(log)
      if zapi == None:
        log.error("zabbix_init()")
        return False
      groups=zabbix_get_hosts_groups_by_user(log,zapi,zabbix_login)
      if groups==None:
        log.error("error zabbix_get_hosts_groups_by_user('%s')"%zabbix_login)
        return False
    mbl.set_env(user,"zabbix_groups",groups)
    return True
  except Exception as e:
    log.error(get_exception_traceback_descr(e))
    return False

def get_default_groups(log,client,room,user,zapi):
  try:
    groups=mbl.get_env(user,"zabbix_groups")
    if groups != None:
      return groups

    groups=[59] # по-умолчанию - ВЭФ ИБП
    zabbix_login=mbl.get_env(user,"zabbix_login")
    if zabbix_login!=None:
      groups=zabbix_get_hosts_groups_by_user(log,zapi,zabbix_login)
      if groups==None:
        log.error("error zabbix_get_hosts_groups_by_user('%s')"%zabbix_login)
        mbl.bot_fault(log,client,room)
        mbl.go_to_main_menu(log,logic,client,room,user)
        return None
    else:
      if mba.send_notice(log,client,room,u"По умолчанию формирую статистику для группы ВЭФ ИБП (установите zabbix_login для индивидуальных настроек в главном меню)") == False:
        log.error("send_notice() to user %s"%user)
        return None
    mbl.set_env(user,"zabbix_groups",groups)
    return groups
  except Exception as e:
    log.error(get_exception_traceback_descr(e))
    return False

def zabbix_show_groups(log,logic,client,room,user,data,source_message,cmd):
  try:
    log.info("zabbix_show_groups()")

    zapi = zabbix_init(log)
    if zapi == None:
      log.error("zabbix_init()")
      mbl.bot_fault(log,client,room)
      mbl.go_to_main_menu(log,logic,client,room,user)
      return False

    groups=get_default_groups(log,client,room,user,zapi)
    if groups==None:
      log.debug("error get_default_groups() - return to main menu")
      mbl.bot_fault(log,client,room)
      mbl.go_to_main_menu(log,logic,client,room,user)
      return False

    groups_names=zabbix_get_hosts_groups_names(log,zapi,groups)
    if groups_names==None:
      log.debug("error zabbix_get_hosts_groups_names() - return to main menu")
      mbl.bot_fault(log,client,room)
      mbl.go_to_main_menu(log,logic,client,room,user)
      return False

    zabbix_login=mbl.get_env(user,"zabbix_login")
    if zabbix_login == None:
      zabbix_login="не выбрано"
    text="<p>Текущий пользователь: <strong>%s</strong></p>"%zabbix_login
    text+="<p><strong>Список текущих групп:</strong></p><ol>"
    for name in groups_names:
      text+="<li>%s</li> "%name
    text+="</ol>"
    if mba.send_html(log,client,room,text) == False:
      log.error("send_html() to user %s"%user)
      return False
    # Завершаем текущий этап и переходим в главное меню:
    mbl.go_to_main_menu(log,logic,client,room,user)
    return True
  except Exception as e:
    log.error(get_exception_traceback_descr(e))
    return False

def zabbix_show_stat(log,logic,client,room,user,data,source_message,cmd):
  try:
    log.info("zabbix_show_triggers()")

    zapi = zabbix_init(log)
    if zapi == None:
      log.error("zabbix_init()")
      mbl.bot_fault(log,client,room)
      mbl.go_to_main_menu(log,logic,client,room,user)
      return False

    groups=get_default_groups(log,client,room,user,zapi)
    if groups==None:
      log.debug("error get_default_groups() - return to main menu")
      mbl.bot_fault(log,client,room)
      mbl.go_to_main_menu(log,logic,client,room,user)
      return False

    if mba.send_notice(log,client,room,u"формирую статистику...") == False:
      log.error("send_notice() to user %s"%user)
      return False

    triggers = zapi.trigger.get(groupids=groups,only_true="1",active="1",min_severity=3,output="extend",selectFunctions="extend",expandDescription="True")
    if triggers==None:
      log.debug("error zapi.trigger.get() - return to main menu")
      mbl.bot_fault(log,client,room)
      mbl.go_to_main_menu(log,logic,client,room,user)
      return False
    priority_3_num=len(triggers)

    triggers = zapi.trigger.get(groupids=groups,only_true="1",active="1",min_severity=4,output="extend",selectFunctions="extend",expandDescription="True")
    if triggers==None:
      log.debug("error zapi.trigger.get() - return to main menu")
      mbl.bot_fault(log,client,room)
      mbl.go_to_main_menu(log,logic,client,room,user)
      return False
    priority_4_num=len(triggers)

    triggers = zapi.trigger.get(groupids=groups,only_true="1",active="1",min_severity=5,output="extend",selectFunctions="extend",expandDescription="True")
    if triggers==None:
      log.debug("error zapi.trigger.get() - return to main menu")
      mbl.bot_fault(log,client,room)
      mbl.go_to_main_menu(log,logic,client,room,user)
      return False
    priority_5_num=len(triggers)

    sev_5_num=priority_5_num
    sev_4_num=priority_4_num-sev_5_num
    sev_3_num=priority_3_num-priority_4_num

    zabbix_login=mbl.get_env(user,"zabbix_login")
    if zabbix_login == None:
      zabbix_login="не выбрано"
    text="<p>Текущий пользователь: <strong>%s</strong></p>"%zabbix_login
    text+="<p><strong>Список проблем для выбранных групп, сгруппированных по важности:</strong></p><br><ol>"
    text+="<li>Критических проблем - %d шт.</li> "%sev_5_num
    text+="<li>Важных проблем - %d шт.</li> "%sev_4_num
    text+="<li>Средних проблем - %d шт.</li> "%sev_3_num
    text+="</ol>"
    if mba.send_html(log,client,room,text) == False:
      log.error("send_html() to user %s"%user)
      return False
    # Завершаем текущий этап и ждём ответа от пользователя:
    mbl.set_state(user,data["answer"])
    return True
  except Exception as e:
    log.error(get_exception_traceback_descr(e))
    return False

def zabbix_show_triggers(log,logic,client,room,user,data,source_message,cmd):
  try:
    log.info("zabbix_show_triggers()")
    zabbix_priority=mbl.get_env(user,"zabbix_priority")
    if zabbix_priority==None:
      log.debug("error get_env zabbix_priority - return to main menu")
      mbl.bot_fault(log,client,room)
      mbl.go_to_main_menu(log,logic,client,room,user)
      return False

    zapi = zabbix_init(log)
    if zapi == None:
      log.error("zabbix_init()")
      mbl.bot_fault(log,client,room)
      mbl.go_to_main_menu(log,logic,client,room,user)
      return False

    groups=get_default_groups(log,client,room,user,zapi)
    if groups==None:
      log.debug("error get_default_groups() - return to main menu")
      mbl.bot_fault(log,client,room)
      mbl.go_to_main_menu(log,logic,client,room,user)
      return False

    if mba.send_notice(log,client,room,u"формирую статистику...") == False:
      log.error("send_notice() to user %s"%user)
      return False

    #Get List of problems
    problems = zapi.problem.get(\
        groupids=groups,\
        output=['eventid','objectid','clock','ns','name','severity'],\
        source=0,\
        object=0, # тип проблем - триггеры\
        sortfield=['eventid'], preservekeys=1,limit=100,recent=1,evaltype=0,\
        severities=zabbix_priority,\
        sortorder='DESC',\
        selectSuppressionData=['maintenanceid','suppress_until']\
        )
    if problems == None:
      log.error("error zapi.problems.get() - return to main menu")
      mbl.bot_fault(log,client,room)
      mbl.go_to_main_menu(log,logic,client,room,user)
      return False

    triggerids=[]
    for problemid in problems:
      problem=problems[problemid]
      triggerids.append(problem['objectid'])

    #Get List of triggers
    triggers = zapi.trigger.get(\
        output=['priority','expression','recovery_mode','recovery_expression','comments','url'],\
        selectHosts=['hostid'],\
        triggerids=triggerids,\
        monitored=1,skipDependent=1,preservekeys=1,\
        selectItems=['itemid','hostid','name','key_','value_type','units','valuemapid']\
        )
    if triggers==None:
      log.error("error zapi.trigger.get() - return to main menu")
      mbl.bot_fault(log,client,room)
      mbl.go_to_main_menu(log,logic,client,room,user)
      return False

    hostids=[]
    for triggerid in triggers:
      trigger=triggers[triggerid]
      for item in trigger['hosts']:
        hostids.append(item['hostid'])

    #Get List of hosts
    hosts = zapi.host.get(hostids=hostids,output=['hostid','name','maintenanceid','maintenance_status','maintenance_type'])
    if hosts==None:
      log.error("error zapi.host.get() - return to main menu")
      mbl.bot_fault(log,client,room)
      mbl.go_to_main_menu(log,logic,client,room,user)
      return False

    priority=u"среднего"
    if zabbix_priority == "5":
      priority=u"критического"
    elif zabbix_priority == "4":
      priority=u"важного"

    text="<p>Список активных триггеров <strong>%s</strong> уровня:</p><ol>"%priority
    for problemid in problems:
      problem=problems[problemid]
      triggerid=problem['objectid']
      if triggerid not in triggers:
        continue
      trigger=triggers[triggerid]
      hostid=int(trigger['hosts'][0]['hostid'])
      host=get_host_by_id(log,hosts,hostid)
      if host == None:
#log.debug("skip unknown host")
#        log.debug(hosts)
        continue
      data=get_time_str_from_unix_time(problem['clock'])
      period=get_period_str_from_ns(problem['clock'])
#  print("номер: %d, дата наступления события: %s (продолжительность: %s), описание: '%s', хост: '%s'"%(index,data,period,problem['name'],host['name']))

      text+="<li>"
      text+="<strong>" + problem['name'] + "</strong>"
      text+=", <em>устройство:</em> <strong>%s</strong>"%host['name']
      text+=", <em>время события:</em> <strong>%s</strong>"%data
      text+=", <em>продолжительность:</em> <strong>%s</strong>"%period
      text+="</li>"
    text+="</ol>"
    if mba.send_html(log,client,room,text) == False:
      log.error("send_html() to user %s"%user)
      return False
    
    #mbl.go_to_main_menu(log,logic,client,room,user)
    if mba.send_notice(log,client,room,u"можете выбрать просмотр триггеров иной важности (1 - критические, 2 - важные, 3 - средние) или 0 - для выхода") == False:
      log.error("send_notice() to user %s"%user)
      return False
    return True
  except Exception as e:
    log.error(get_exception_traceback_descr(e))
    return False
    

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


if __name__ == '__main__':
  log=logging.getLogger("matrix_bot_logic_zabbix")
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

  # add handler to logger object
  log.addHandler(fh)

  log.info("Program started")

  if zabbix_test(log) == False:
    log.error("error zabbix_test()")
    sys.exit(1)
  log.info("Program exit!")
