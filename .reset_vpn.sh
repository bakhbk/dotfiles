#!/bin/bash

# Остановка всех активных VPN-подключений
VPN_LIST=$(scutil --nc list | grep 'Connected' | awk -F'"' '{print $2}')
for VPN in $VPN_LIST; do
  echo "Отключаем VPN: $VPN"
  scutil --nc stop "$VPN"
done

# Сброс сетевого интерфейса (Wi-Fi)
INTERFACE="en0" # en0 - Wi-Fi, en1 - Ethernet

echo "Перезапускаем сетевой интерфейс $INTERFACE"
sudo ifconfig $INTERFACE down
sudo ifconfig $INTERFACE up

# Перезапуск сетевого стека
echo "Перезапуск сетевого стека"
sudo killall -HUP mDNSResponder

# Сброс маршрутизации
echo "Сброс таблицы маршрутизации"
sudo route -n flush

# Отключение и включение Wi-Fi
echo "Перезапуск Wi-Fi"
networksetup -setnetworkserviceenabled Wi-Fi off
sleep 2
networksetup -setnetworkserviceenabled Wi-Fi on

# Очистка DNS-кэша
echo "Очистка DNS-кэша"
sudo dscacheutil -flushcache
sudo killall -HUP mDNSResponder

echo "Сеть сброшена. Проверьте подключение."
