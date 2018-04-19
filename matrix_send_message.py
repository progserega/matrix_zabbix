#!/usr/bin/env python
# -*- coding: utf-8 -*-
import config as conf
from matrix_client.client import MatrixClient
from matrix_client.api import MatrixRequestError
from requests.exceptions import MissingSchema
import sys
import sendemail as mail


def log(send_email=False,text=u"Произошёл сбой в скрипте %s" % sys.argv[0]):
	f=open(conf.log_path, "a" )
	log_text=u"%(time)s: %(prog)s: %(text)s" % {"text":text,"prog":sys.argv[0], "time":time.strftime("%Y-%m-%d %H:%M:%S", time.localtime( time.time() ) )}
	f.write(log_text.encode('utf-8') + "\n")
	if conf.DEBUG:
		print(log_text.encode('utf-8'))
	f.close()
	if send_email:
		# Отправляем получателям:
		for email_to in conf.email_admin:
			mail.sendmail(text=text, subj=u"ОШИБКА при обработке СМС Диспетчеров!", send_to=email_to, server=conf.email_server, files=[conf.log_path] , send_from=u"matrix@zabbix.rs.int")

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
  status=keys[0].strip()
  severity=keys[1].strip()
  trigger_name=keys[2].strip()
  if status in status_types and severity in severity_types:
    zbx_subject = status_types[status] + "; " + severity_types[severity] + "; " + trigger_name

client = MatrixClient(conf.server)

# New user
#token = client.register_with_password(username=conf.username, password=conf.password)

token=None
# Existing user
try:
  token = client.login_with_password(username=conf.username, password=conf.password)
except MatrixRequestError as e:
  print(e)
  if e.code == 403:
    log(text="Bad username or password.")
    sys.exit(4)
  else:
    log(text="Check your sever details are correct.")
    sys.exit(2)
except MissingSchema as e:
  log(text="Bad URL format.")
  print(e)
  sys.exit(3)


text="""%(zbx_subject)s
%(zbx_body)s
"""%{"zbx_subject":zbx_subject, "zbx_body":zbx_body}

ret=room.send_text(text)
