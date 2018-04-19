#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
import smtplib, os
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email.mime.text import MIMEText
from email.utils import COMMASPACE, formatdate
from email import encoders
import socket

def sendmail(text="произошёл инцедент. Необходимо участие админа.", subj="важное сообщение", send_to='abuse@rsprim.ru' , server='172.21.254.5', port=25, send_from='root@gsm.rs.int', username='', password='', isTls=True, files=[] ):
    msg = MIMEMultipart()
    msg['From'] = send_from
	#msg['To'] = COMMASPACE.join(send_to)
    msg['To'] = send_to
    msg['Date'] = formatdate(localtime = True)
    msg['Subject'] = subj

	#msg.attach( MIMEText(text) )
    msg.attach( MIMEText(text, 'plain', 'UTF-8') )

    for f in files:
        part = MIMEBase('application', "octet-stream")
        part.set_payload( open(f,"rb").read() )
        encoders.encode_base64(part)
        part.add_header('Content-Disposition', 'attachment; filename="{0}"'.format(os.path.basename(f)))
        msg.attach(part)

    smtp = smtplib.SMTP(server, port)
    if isTls: smtp.starttls()
#   smtp.login(username,password)
    smtp.sendmail(send_from, send_to, msg.as_string())
    smtp.quit()


#sendmail(send_to="semenov@rsprim.ru",files=["README"])
