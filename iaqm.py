from __future__ import division								
""" 
v.e.s.

This script implements the whole intelligent AQM method. In this case, the FQ-CoDel scheme is used

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
import ecpredictor as ecp
import learner as lrn

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

	print '*** Running experiment: Intelligent AQM...'
	
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
	
	print '*** Gathering network data for retraining congestion predictor...'
	r1.cmd('settings=$(<./cap.ini) && tshark -i r1-eth1 $settings > ./traces.csv &')
		
	for i in range(1,n+1):
		a[i-1].cmd('netcat -l 12345 >/dev/null &')
		time.sleep(random.random()*2)								# Each transmission starts after a random delay between 0.2 and 2.0 secs
		MB = random.randint(3,630)									# Random amount of MB to transmit
		b[i-1].cmd('dd if=./file.test bs={}M count=1 | nc 10.0.0.{} 12345 &'.format(MB,i))

	time.sleep(6)													# Wait to make sure that six seconds of training data are gathered											

	ec_val, MSE, MAE = ecp.retrain()
	ec_pred = np.cumsum(ec_val, dtype=float)
	
	print '*** MSE and MAE of prediction based on re-training: %.2f %.2f' % (MSE, MAE)
		
	iter = 300
	S = 100												# Number of states: discrete levels of congestion [0, 100] in a period of 1 s			
	A = np.arange(50, 5050, 50)							# Set of actions: set value of target parameter in us
	epsilon = 0.5
	ind_action = len(A)-1								# Start with default target (5 ms)
	
	max_ec_pred = 0
	max_ec_observ = 0
	hist_r = np.zeros(iter)
	hist_rtt = np.zeros(iter)
	hist_tput = np.zeros(iter)
		
	m2.cmd('iperf -s &')								# Iperf server on m2 to measure throughput
	
	for i in range(iter):
		
		print '*** Interval number: %i' % i
		print '*** Value of target parameter: %i' % (A[ind_action])
		
		## Observing current state (past second):
		
		m_error = False
		target = A[ind_action]
		interval = int(target/(0.05*1000))											# Tipycally, target is 5% of interval
		r1.cmd('tc qdisc change dev r1-eth1 parent 1:1 handle 10:1 fq_codel limit 1000 target {}us interval {}ms'.format(target,interval)) # Change the parameters of AQM
		r1.cmd('tail -n 1000 ./traces.csv > ./tmp_traces.csv') # To load only the last 1000 traces. It was observed that 1 s capture produces about 500 lines with the configured filter
				
		data = pd.read_csv('./tmp_traces.csv', header=None, usecols=[0], engine='python', error_bad_lines=False, warn_bad_lines=False)
		
		## Making congestion prediction:
		
		data = data.sort_values(by=[0], ascending=False)
		n_ecep = ecp.count(data, t_limit=1)
		Xn, yn = ecp.pdata(pd.Series(n_ecep))
		yp, MSE, MAE = ecp.predict(Xn, yn)
		ec_pred = np.cumsum(yp, dtype=float)
		ec_observ = np.cumsum(yn, dtype=float)
		
		if ec_observ.max() > max_ec_observ:
			max_ec_observ = ec_observ.max()								# Stores the max value of observed EC
		
		if ec_pred.max() > max_ec_pred:
			max_ec_pred = ec_pred.max()									# Stores the max value of predicted EC
			
		ec_curr = int((ec_observ.max()/max_ec_observ)*S-1)
		ec_ahead = int((ec_pred.max()/max_ec_pred)*S-1)
		
		
		## Measuring RTT and throughput:
		
		m1.cmd('ping 10.0.1.2 -i 0.01 -w 1 -q | tail -1 > ./ping.out &')
		m1.cmd('iperf -c 10.0.1.2 -i 0.01 -t 1 | tail -1 > ./tput.out')
		
		#time.sleep(0.1)													# Wait while measurements are saved
		
		statinfo = os.stat('./ping.out')
		if statinfo.st_size < 10:
			print '*** No ping response'
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
		
		if m_error:
			R = 0
		else:
			R = hist_r[i]								# Reward is based on power function
		
		
		print '*** Power: %.3f' % R
		
		## Updating Q-values:
		
		Q = lrn.update(ec_curr, ind_action, R, ec_ahead)
		
		## Selecting action for next iteration:
		
		ind_action = lrn.action(ec_curr, epsilon)
				
		r1.cmd('tc -s -d qdisc show dev r1-eth1 >>./iaqm.stat')
		
		
	print '*** Saving Q-Table and historical rewards'
	
	np.save('./Rewards.npy',hist_r)
	np.save('./Q-Values.npy',Q)
	
	print '*** Stopping emulation'
	
	m1.cmd('rm -f ./*.out &')
	m1.cmd('rm -f ./*.csv &')
	
	net.stop()

	print '*** Experiment finished!'

if __name__ == "__main__":
  main()