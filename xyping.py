#!/usr/bin/env python
#coding:utf-8
import os, sys, socket, struct, select, time , json
# From /usr/include/linux/icmp.h; your milage may vary.
ICMP_ECHO_REQUEST = 8 # Seems to be the same on Solaris.
def checksum(source_string):
  """
  I'm not too confident that this is right but testing seems
  to suggest that it gives the same answers as in_cksum in ping.c
  """
  sum = 0
  countTo = (len(source_string)/2)*2
  count = 0
  while count<countTo:
    thisVal = ord(source_string[count + 1])*256 + ord(source_string[count])
    sum = sum + thisVal
    sum = sum & 0xffffffff # Necessary?
    count = count + 2
  if countTo<len(source_string):
    sum = sum + ord(source_string[len(source_string) - 1])
    sum = sum & 0xffffffff # Necessary?
  sum = (sum >> 16) + (sum & 0xffff)
  sum = sum + (sum >> 16)
  answer = ~sum
  answer = answer & 0xffff
  # Swap bytes. Bugger me if I know why.
  answer = answer >> 8 | (answer << 8 & 0xff00)
  return answer
def receive_one_ping(my_socket, ID, timeout):
  """
  receive the ping from the socket.
  """
  timeLeft = timeout
  while True:
    startedSelect = time.time()
    whatReady = select.select([my_socket], [], [], timeLeft)
    howLongInSelect = (time.time() - startedSelect)
    if whatReady[0] == []: # Timeout
      return
    timeReceived = time.time()
    recPacket, addr = my_socket.recvfrom(1024)
    icmpHeader = recPacket[20:28]
    type, code, checksum, packetID, sequence = struct.unpack(
      "bbHHh", icmpHeader
    )
    if packetID == ID:
      bytesInDouble = struct.calcsize("d")
      timeSent = struct.unpack("d", recPacket[28:28 + bytesInDouble])[0]
      return timeReceived - timeSent
    timeLeft = timeLeft - howLongInSelect
    if timeLeft <= 0:
      return
def send_one_ping(my_socket, dest_addr, ID):
  """
  Send one ping to the given >dest_addr<.
  """
  dest_addr = socket.gethostbyname(dest_addr)
  # Header is type (8), code (8), checksum (16), id (16), sequence (16)
  my_checksum = 0
  # Make a dummy heder with a 0 checksum.
  header = struct.pack("bbHHh", ICMP_ECHO_REQUEST, 0, my_checksum, ID, 1) #压包
  #a1 = struct.unpack("bbHHh",header)  #my test
  bytesInDouble = struct.calcsize("d")
  data = (192 - bytesInDouble) * "Q"
  data = struct.pack("d", time.time()) + data
  # Calculate the checksum on the data and the dummy header.
  my_checksum = checksum(header + data)
  # Now that we have the right checksum, we put that in. It's just easier
  # to make up a new header than to stuff it into the dummy.
  header = struct.pack("bbHHh", ICMP_ECHO_REQUEST, 0, socket.htons(my_checksum), ID, 1)
  packet = header + data
  my_socket.sendto(packet, (dest_addr, 1)) # Don't know about the 1
def do_one(dest_addr, timeout):
  """
  Returns either the delay (in seconds) or none on timeout.
  """
  icmp = socket.getprotobyname("icmp")
  try:
    my_socket = socket.socket(socket.AF_INET, socket.SOCK_RAW, icmp)
  except socket.error, (errno, msg):
    if errno == 1:
      # Operation not permitted
      msg = msg + (
        " - Note that ICMP messages can only be sent from processes"
        " running as root."
      )
      raise socket.error(msg)
    raise # raise the original error
  my_ID = os.getpid() & 0xFFFF
  send_one_ping(my_socket, dest_addr, my_ID)
  delay = receive_one_ping(my_socket, my_ID, timeout)
  my_socket.close()
  return delay
def verbose_ping(dest_addr, timeout = 2, count = 100):
  for i in xrange(count):
    print "ping %s..." % dest_addr,
    try:
      delay = do_one(dest_addr, timeout)
    except socket.gaierror, e:
      print "failed. (socket error: '%s')" % e[1]
      break
    if delay == None:
      print "failed. (timeout within %ssec.)" % timeout
    else:
      delay = delay * 1000
      print int(delay)
      print "get ping in %0.4fms" % delay
    time.sleep(1)
def write_file(path,bytes,type='wb'):
    #filedir = os.path.split(path)[0]
    #if not os.path.exists(filedir):
    #    os.makedirs(filedir)
	with open(path,type) as f:
		f.write(bytes)
		f.flush()
		f.close()
import datetime
def stime():
    return datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')  # 现在
def ping(dest_addr, timeout = 2, count = 100,max_ms = 150):
    high_ms_num = 0
    timeout_num = 0
    max_ping_ms = 0
    mix_ping_ms = 0
    for i in xrange(count):
        try:
            delay = do_one(dest_addr, timeout)
        except socket.gaierror, e:
            timeout_num += 1
            continue
        if delay == None:
            timeout_num += 1
        else:
            delay = int(delay * 1000)
            if mix_ping_ms == 0 :
                mix_ping_ms = delay
            if delay > max_ms:       #记录高延时次数
                high_ms_num  += 1
            if delay>max_ping_ms:    #记录最高延迟
                max_ping_ms = delay
            if delay < mix_ping_ms:  #记录最低延迟
                mix_ping_ms = delay
        time.sleep(1)
    return {"high_ms_num":high_ms_num,"timeout_num":timeout_num,"max_ping_ms":max_ping_ms,"mix_ping_ms":mix_ping_ms}
def look_node(host,max_ms=100,logname='ping'):
    while True:
        try:
			is_log = False
			num = 10
			ret = ping(host,1,10,max_ms)
			if ret['timeout_num']>num/2:
				is_log = True
			if ret['high_ms_num']>num/2:
				is_log = True
			if is_log:
				write_file(logname+'.log',stime()+':'+json.dumps(ret)+'\r\n','a+')
        except Exception, e:
            print('look_node err:' + str(e))
        print stime()+':'+json.dumps(ret)
        time.sleep(1*60)
    pass

import argparse,os
if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='ping script')
    parser.add_argument("-ip", type=str, default="127.0.0.1")
    parser.add_argument("-ms", type=int, default=100)
    parser.add_argument("-log", type=str, default="ping")
    args = parser.parse_args()
    print args
    host = args.ip              #IP地址
    max_ms = args.ms            #最大延迟
    logname = args.log           #日志名
    if logname == 'ping':
        logname = host
    os.system("title ["+host+"]["+logname+"]")
    look_node(host,max_ms,logname)
