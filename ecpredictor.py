
"""
v.e.s.

Script for congestion prediction on data captured during experiments. The pre-trained LSTM model is re-trained with data from six-seconds emulations

@author: Cesar A. Gomez

"""

import pandas as pd
import numpy as np
from sklearn.preprocessing import MinMaxScaler
from sklearn.metrics import mean_squared_error, mean_absolute_error
from keras.models import load_model
import warnings
import tensorflow as tf

warnings.filterwarnings("ignore")
tf.logging.set_verbosity(tf.logging.ERROR)
np.random.seed(7)										# Only for reproducibility

model = load_model('./CongestPredict.h5')				# Load pre-trained model

def count(data, t_limit):
	## Counting the number of ECE packets per time interval:
	
	data['iat'] = np.absolute((pd.to_datetime(data[0]).diff()))/np.timedelta64(1,'s')	# Calculate inter-arrival time of packets in seconds
	data.iloc[0,1] = 0																	# Replace first value of IAT with 0
	data['e_time'] = data['iat'].cumsum()

	sample = data[data.e_time<=t_limit]
	t_final = sample.e_time.max()
	
	if t_limit == 1:																	# When extracting data for predictions (last samples)									
		sample['e_time']=t_final-sample.e_time.values
		
	print '*** Trace data extracted for %f seconds' % t_final
	
	sample = sample.sort_values(by=[0])					# To make sure that traces are sorted by time
		
	t_interv = 0.001									# Time interval to determine the number of ECE packets (in secs)	 		   
	m = int(np.ceil(t_final/t_interv))					# Max. number of intervals
	n_ecep = np.zeros(m,dtype=int)					  	# Array for number of ECE packets in each interval
	ecep = 0
	n_interv = 1
	i = 0

	while i<len(sample):	
		if sample.iloc[i,2]<=t_interv*n_interv:				# Elapsed time info is in column 2 of dataframe
			ecep += 1							  			# Counts ECE-marked packets
		else:
			n_ecep[n_interv-1] = ecep				   		# Stores the number of ECE packets per interval
			ecep = 0
			n_interv += 1
			i -= 1									  		# To take into account packets in previous time
		i += 1
	
	return n_ecep

def pdata(n_ecep, window=10):
	
	dfinal = []
	seq = window+1
	pkt = len(n_ecep)
	for index in range(0,pkt-seq):					  		# Extract data based on window and number of packets
		dfinal.append(n_ecep[index:index+seq])
	dfinal = np.array(dfinal)
	X_train = dfinal[:,:-1]							 
	y_train = dfinal[:,-1]				

	scaler = MinMaxScaler(feature_range=(0, 1))						
	Xn_train = scaler.fit_transform(X_train)
	yn_train = scaler.fit_transform(y_train.reshape(-1,1))
	
	## Reshaping input data in the form of samples (training sequences), sequence length (time steps), and features for the LSTM network:

	Xn_train = np.reshape(Xn_train, (Xn_train.shape[0], Xn_train.shape[1], 1))		
		
	return Xn_train, yn_train

def predict(Xn, yn):
	
	yp = model.predict(Xn)
	
	# Calculating error scores:

	mse = np.sqrt(mean_squared_error(yn, yp))
	mae = mean_absolute_error(yn, yp)

	## Amplifying prediction datapoints:

	factor = 50
	yf = yp-yp.mean()
	yf[yf < 0] = 0						
	yf = yf*factor
	yf[yf > 1] = 1						
	
	return yf, mse, mae
	
	
def retrain():
	
	data = pd.read_csv('./traces.csv', header=None, usecols=[0], engine='python', error_bad_lines=False, warn_bad_lines=False)
	n_ecep = count(data, t_limit=6)	

	## Getting train and test subsets and normalizing them:

	window = 10														  	# Window size for the sequence to be considered
	Xn_train, yn_train = pdata(pd.Series(n_ecep),window)

	## Loading the pre-trained LSTM network and retraining it:
	
	model.fit(Xn_train, yn_train, batch_size=30, epochs=1, verbose=0)
	yp, mse, mae = predict(Xn_train, yn_train) 							# Making prediction
	
	return yp, mse, mae