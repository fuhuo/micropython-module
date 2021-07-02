# micropython-module
collect or forked any module for [micropython](https://github.com/micropython/micropython)

最近在玩micropython的时候，由于micropython的原生方法缺失，导致某些纯python的模块也无法正常使用，  
于是就自己收集、fork或者手撸一些模块来使用.  
但是这些模块我只使用部分功能，不一定都能正常.有问题的话，提个[issue](https://github.com/fuhuo/micropython-module/issues/new).  
  
目前使用的版本（ESP32）：  
micropython version: 1.16  
  
[ping3.py](https://github.com/fuhuo/micropython-module/blob/main/libs/ping3.py): 基于ICMP协议的ping的模块. forked from https://github.com/kyan001/ping3  
[crc32.py](https://github.com/fuhuo/micropython-module/blob/main/libs/crc32.py): 计算crc32的模块. forked from https://github.com/slavaromanov/crc32/blob/master/src/python/crc32.py  
[queue.py](https://github.com/fuhuo/micropython-module/blob/main/libs/queue.py): 队列模块，目前仅实现了Queue方法. forked from standard python module  
[md5.py](https://github.com/fuhuo/micropython-module/blob/main/libs/md5.py): 计算md5的模块. forked from https://github.com/M-Taghizadeh/MD5_Algorithm/blob/master/md5_algorithm.py  
[picoweb](https://github.com/pfalcon/picoweb): 构建web服务的模块.  
[utelnetserver](https://github.com/cpopp/MicroTelnetServer): telnet服务端的模块.  
[uftp](https://github.com/robert-hh/FTP-Server-for-ESP8266-ESP32-and-PYBD): ftp服务模块.  

when I using micropython, I cannot find any module that i want.  
so i collect or fork any module for it.  
but i only test the function i want.  
if you found something wrong, pls commit an [issue](https://github.com/fuhuo/micropython-module/issues/new).  
  
micropython version: 1.16  
  
[ping3.py](https://github.com/fuhuo/micropython-module/blob/main/libs/ping3.py): a ping module. forked from https://github.com/kyan001/ping3  
[crc32.py](https://github.com/fuhuo/micropython-module/blob/main/libs/crc32.py): a calc crc32. forked from https://github.com/slavaromanov/crc32/blob/master/src/python/crc32.py  
[queue.py](https://github.com/fuhuo/micropython-module/blob/main/libs/queue.py): queue module, only Queue now. forked from standard python module  
[md5.py](https://github.com/fuhuo/micropython-module/blob/main/libs/md5.py): calc md5. forked from https://github.com/M-Taghizadeh/MD5_Algorithm/blob/master/md5_algorithm.py  
[picoweb](https://github.com/pfalcon/picoweb): web server module.  
[utelnetserver](https://github.com/cpopp/MicroTelnetServer): telnet server module.  
[uftp](https://github.com/robert-hh/FTP-Server-for-ESP8266-ESP32-and-PYBD): ftp server module.  