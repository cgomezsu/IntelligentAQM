# Intelligent Active Queue Management (AQM)

Code for the evaluation of an AQM method based on Machine Learning techniques, through experiments run in Mininet network emulator.

Dependencies:
•	Python 2.7
•	Mininet 2.2.2
•	Numpy 1.16.3
•	Pandas 0.24.2
•	Sklearn 0.20
•	TensorFlow 1.13.1-cp27
•	Keras 2.2.4
•	Substring 0.2

Instructions:
1.	Install all dependencies and save all script files in the same directory
2.	For the TCP transfer, have in the directory any file with the name file.test (we used one of ~630 MB).
3.	Execute run.sh as root: sudo bash run.sh
4.	For CoDel, use codel instead of fq_codel when setting the AQM in R1
5.	Power function results are saved in .npy files and AQM statistics in a .stat file

NOTE: This code is the software implementation of the method described in a manuscript that is under review. The rest of the scripts will be released once the review process is finished.
