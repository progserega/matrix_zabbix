#!/bin/bash
if [ -z "$2" ]
then
  echo "Необходимо два параметра: скрипт, который запускаем, и файл дампа, в котоый пишем вывод команды и сохраняем его в случае ошибки!"
  exit 1
fi
exec_file="$1"
error_dump_file="$2"

while /bin/true
do
  $exec_file &> ${error_dump_file}
  if [ $? != 0 ] 
  then
    cp "${error_dump_file}" "${error_dump_file}_error_save_`date +%Y.%m.%d-%T`"
  fi
  sleep 120
done
