
Setup:
0. pip install matrix_client
1. Create zabbix account on matrix-server.
2. Create rooms for users and add users (who will be receive zabbix-alerts). Remember pars user-room_id
3. Accept invite from zabbix-account by each users.
4. cp config.py.example config.py
5. edit config.py.example - add zabbix accounts info (login and pass).
6. In zabbix add script as send-script. And for specificied user add his room_id as params for script.

for test, you may exec script manualy:

  ./matrix_send_message.py 'matrix_room_id' 'zabbix subject' 'zabbix event body text'
