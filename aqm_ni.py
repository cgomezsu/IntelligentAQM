from __future__ import division								
""" 
v.e.s.

This script runs the experiment with no intelligence. In this case, the FQ-CoDel scheme is used

@author: Cesar A. Gomez

"""
																				 
from mininet.topo import Topo
from mininet.net import Mininet
from mininet.link import TCLink
from mininet.util import dumpNodeConnections
from mininet.log import setLogLevel
import time, random
import pandas as pd
import numpy as np
import substring as ss
import os


random.seed(7)												# For reproducibility

class CreateTopo(Topo):
	
	def build(self, n=2):
		r1 = self.addSwitch('r1')
		r2 = self.addSwitch('r2')
		self.addLink(r1, r2, bw=10)
		
		for h in range(1,n+1):
			
			host_a = self.addHost('a%s' % h)						
			d = str(random.randint(1,21))+'ms'				# Each client has a random propagation delay (between 5 and 50 ms) on the link connected to r1
			bw = random.randint(1,6)						# Each client has a random rate limit (between 100 and 500 Mbps) on the link connected to r1
			self.addLink(host_a, r2, bw=bw, delay=d)	  	

			host_b = self.addHost('b%s' % h)
			d = str(random.randint(1,21))+'ms'				# Each client has a random propagation delay (between 5 and 50 ms) on the link connected to r1
			bw = random.randint(100,501)					# Each client has a random rate limit (between 100 and 500 Mbps) on the link connected to r1
			self.addLink(host_b, r1, bw=bw, delay=d)	
		
		monitor = self.addHost('m1', ip='10.0.1.1')			# There are two monitor hosts for probing
		self.addLink(monitor, r1)
		monitor = self.addHost('m2', ip='10.0.1.2')
		self.addLink(monitor, r2)

		
def main():

	print '*** Running experiment: AQM with no intelligence...'
	
	## Setting up the emulation environment:
			
	setLogLevel('info')   											# Shows Mininet info
	n=20					  										# Number of hosts on the left
	topo = CreateTopo(n)					
	net = Mininet(topo, link=TCLink, autoSetMacs=True)			  # we use Traffic Control links (to limit bandwidth and propagation delay)
	net.start()

	a = []
	b = []

	for i in range(1,n+1):
		a.append(net['a%s' % i])
		b.append(net['b%s' % i])
		
	r1 = net['r1']
	m1 = net['m1']
	m2 = net['m2']

	print '*** Testing connectivity between pairs'

	for i in range(n):
		net.ping(hosts=[a[i],b[i]])

	net.ping(hosts=[m1,m2])	


	## Changing the queue discipline on interface r1-eth1, which is the bottleneck from r1 to r2

	print '*** Setting up AQM in R1 and ECN in hosts'
	r1.cmd('tc qdisc del dev r1-eth1 root')													# Clear current qdisc
	r1.cmd('tc qdisc add dev r1-eth1 root handle 1:0 htb default 1')						# Set the name of the root as 1:, for future references. The default class is 1
	r1.cmd('tc class add dev r1-eth1 classid 1:1 htb rate 10mbit')							# Create class 1:1 as direct descendant of root (the parent is 1:) with rate limiting of 10 Mbps
	r1.cmd('tc qdisc add dev r1-eth1 parent 1:1 handle 10:1 fq_codel limit 1000')			# Create qdisc with ID (handle) 10 of class 1. Its parent class is 1:1. Queue size limited to 1000 pkts

	## Enabling ECN in hosts:

	for i in range(n):
		a[i].cmd('sysctl -w net.ipv4.tcp_ecn=1')
		b[i].cmd('sysctl -w net.ipv4.tcp_ecn=1')
		
	m1.cmd('sysctl -w net.ipv4.tcp_ecn=1')
	m2.cmd('sysctl -w net.ipv4.tcp_ecn=1')
	
		
	for i in range(1,n+1):
		a[i-1].cmd('netcat -l 12345 >/dev/null &')
		time.sleep(random.random()*2)								# Each transmission starts after a random delay between 0.2 and 2.0 secs
		MB = random.randint(3,630)									# Random amount of MB to transmit
		b[i-1].cmd('dd if=./file.test bs={}M count=1 | nc 10.0.0.{} 12345 &'.format(MB,i))

		
	iter = 300
	
	hist_r = np.zeros(iter)
	hist_rtt = np.zeros(iter)
	hist_tput = np.zeros(iter)
		
	m2.cmd('iperf -s &')								# Iperf server on m2 to measure throughput
	
	for i in range(iter):
					
		print '*** Interval number: %i' % i
		## Measuring RTT and throughput:
		
		m1.cmd('ping 10.0.1.2 -i 0.01 -w 1 -q | tail -1 > ./ping.out &')
		m1.cmd('iperf -c 10.0.1.2 -i 0.01 -t 1 | tail -1 > ./tput.out')
		
		#time.sleep(0.1)													# Wait for a moment while measurements are saved
		
		statinfo = os.stat('./ping.out')
		if statinfo.st_size < 10:
			print '*** No ping response. Setting R = 0'
			m_error = True
			mRTT = hist_rtt.mean()
		else:
			din = open('./ping.out').readlines()
			slice = ss.substringByInd(din[0],26,39)
			text = (slice.split('/'))
			mRTT = float(text[1])
		
		hist_rtt[i] = mRTT
		
		
		print '*** mRTT: %.3f' % mRTT
		
		statinfo = os.stat('./tput.out')
		if statinfo.st_size < 10:
			print '*** No tput response. Setting R = 0'
			m_error = True
			tput = hist_tput.mean()
		else:
			din = open('./tput.out').readlines()
			tput = float(ss.substringByInd(din[0],34,37))
			unit = ss.substringByInd(din[0],39,39)
			if unit == 'K':
				tput = tput*0.001
		
		hist_tput[i] = tput
		
		
		print '*** Throughput: %.3f' % tput
		
			
		hist_r[i] = tput/mRTT	
		
		
		print '*** Power: %.3f' % hist_r[i]
		
		r1.cmd('tc -s -d qdisc show dev r1-eth1 >>./aqm_ni.stat')
		
		
	
	print '*** Saving historical values of power'
	
	np.save('./Power_ni.npy',hist_r)
	
	print '*** Stopping emulation'
	
	m1.cmd('rm -f ./*.out &')
	
	net.stop()

	print '*** Experiment finished!'

if __name__ == "__main__":
  main()