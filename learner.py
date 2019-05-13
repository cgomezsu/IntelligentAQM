""" 
v.e.s.

Tuner based on the Q-Learning algorithm.


MIT License

Copyright (c) 2019 Cesar A. Gomez

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.

"""

import random
import numpy as np

random.seed(7)										# For reproducibility

## Initializing learning parameters:

S = 100												# States
A = len(np.arange(50, 5050, 50))					# Actions
Q = np.zeros(shape=[S,A], dtype=np.float32)  		# Q-Table
gamma = 0.8
alpha = 0.5											

def update(state, ind_action, reward, nxt_state):
	
	max_nxt_action = max(Q[nxt_state,:])
	Q[state,ind_action] = (1-alpha)*Q[state,ind_action]+alpha*(reward+gamma*max_nxt_action)
	
	return Q
	
def action(state, epsilon=0.1):

	if random.random()<epsilon:
		action = random.randint(0,A-1)
	else:
		action = np.argmax(Q[state,:])
	
	return action