import sys
import platform
import numpy as np


# GUI FILE
from PyQt5 import QtCore, QtGui, QtWidgets
from PyQt5.QtCore import (QCoreApplication, QPropertyAnimation, QDate, QDateTime, QMetaObject, QObject, QPoint, QRect, QSize, QTime, QUrl, Qt, QEvent, QTimer)
from PyQt5.QtGui import (QBrush, QColor, QConicalGradient, QCursor, QFont, QFontDatabase, QIcon, QKeySequence, QLinearGradient, QPalette, QPainter, QPixmap, QRadialGradient, QImage)
from PyQt5.QtWidgets import *
from ui_main2 import Ui_MainWindow

# Raspi Sensors and Actuators
from ui_functions import *




try:
    import RPi.GPIO as gpio
    on_RPi = True
    import raspi_function as rpi
    print("work on raspberry pi")
except (ImportError, RuntimeError):
    on_RPi = False

from utils.vision_helper import draw_box_name

import cv2
import imutils
from imutils.video import VideoStream
from imutils.video import FPS
from utils.centroidtracker import CentroidTracker
from collections import OrderedDict

import time
import datetime


# global variabel

bulan = ['Jan', 'Feb', 'Mar', 'Apr', 'Mei', 
         'Jun', 'Jul', 'Aug', 'Okt', 'Sep',
         'Nov', 'Dec']

arrayTherm = np.zeros((240,240,3))
suhu = '0 C'
ct = CentroidTracker(maxDisappeared=16)
getData = False


futureObj = set()
myPeople = OrderedDict()

obj_center = {}
obj_bbox = {}


class MainWindow(QMainWindow):
    def __init__(self):
        QMainWindow.__init__(self)
        self.ui = Ui_MainWindow()
        self.ui.setupUi(self)
        path_cam = 'rtsp://admin:aiti12345@11.11.11.81:554/Streaming/channels/101'
        if on_RPi:
            path_cam1 = 'http://11.11.11.12:8555' 
            self.cap = VideoStream(src=path_cam1).start()
        else:
            print('TEST')
            path_cam1 = 0
            self.cap = VideoStream(src=path_cam1, usePiCamera=False).start()

        self.detector = cv2.CascadeClassifier('haarcascade_frontalface_default.xml')

        time.sleep(2.0)

        # self.cap = cv2.VideoCapture(path_cam1)
        # time.sleep(1)

        # vision opetarion
        self.streamCamera = QTimer()
        self.streamCamera.start(20)
        self.streamCamera.timeout.connect(self.stream_camera_on)

        # input operation
        self.streamSensors = QTimer()
        self.streamSensors.start(10)
        self.streamSensors.timeout.connect(self.processing_sensors)

        # output operation
        #self.streamActuators = QTimer()
        #self.streamActuators.start(5)
        #self.streamActuators.timeout.connect(self.processing_output)


        # for update time on display
        self.streamDate = QTimer()
        self.streamDate.setInterval(1000)
        self.streamDate.timeout.connect(self.showTime)

        self.streamDate.start()
        self.count_FPS = 0

        # MOVE WINDOW
        def moveWindow(event):
            # RESTORE BEFORE MOVE
            if UIFunctions.returnStatus() == 1:
                UIFunctions.maximize_restore(self)

            # IF LEFT CLICK MOVE WINDOW
            if event.buttons() == Qt.LeftButton:
                self.move(self.pos() + event.globalPos() - self.dragPos)
                self.dragPos = event.globalPos()
                event.accept()

        # SET TITLE BAR
        self.ui.fr_jam.mouseMoveEvent = moveWindow

        ## ==> SET UI DEFINITIONS
        UIFunctions.uiDefinitions(self)


        ## SHOW ==> MAIN WINDOW
        self.show()

    ## APP EVENTS
    def mousePressEvent(self, event):
        self.dragPos = event.globalPos()

    def visionThermal(self,image):
        arrayTherm = rpi.thermalCam.getThermal()
        # -------- overlay thermal ----------
        y_offset=image.shape[0]-arrayTherm.shape[0]
        x_offset=0

        alpha = 0.5
        output = image[y_offset:y_offset+arrayTherm.shape[0], x_offset:x_offset+arrayTherm.shape[1]] 
        cv2.addWeighted(arrayTherm, alpha, output, 1 - alpha, 0, output)
        image[y_offset:y_offset+arrayTherm.shape[0], x_offset:x_offset+arrayTherm.shape[1]] = output
        return image

    def stream_camera_on(self):
        global arrayTherm, suhu, ct, myPeople, getData, futureObj

        # read image in BGR format
        image = self.cap.read()
        start_time = time.time()

        image = imutils.resize(image, width=400) # for face

        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) # for face
        image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)

        rects = self.detector.detectMultiScale(gray, scaleFactor=1.1, 
            minNeighbors=5, minSize=(30, 30),
            flags=cv2.CASCADE_SCALE_IMAGE)

        boxes = [[x, y, x + w, y + h] for (x, y, w, h) in rects]

        h_img, w_img, ch = image.shape

        # ------- Function for Doorlock --------
        if on_RPi:
            if self.count_FPS % 7 == 0 :
                arrayTherm, suhu = rpi.thermalCam.getThermal()

                # -------- overlay thermal ----------
                y_offset=image.shape[0]-arrayTherm.shape[0]
                x_offset=0

                alpha = 0.5
                output = image[y_offset:y_offset+arrayTherm.shape[0], x_offset:x_offset+arrayTherm.shape[1]] 
                cv2.addWeighted(arrayTherm, alpha, output, 1 - alpha, 0, output)
                image[y_offset:y_offset+arrayTherm.shape[0], x_offset:x_offset+arrayTherm.shape[1]] = output

            else:
                y_offset=image.shape[0]-arrayTherm.shape[0]
                x_offset=0
                alpha = 0.5

                output = image[y_offset:y_offset+arrayTherm.shape[0], x_offset:x_offset+arrayTherm.shape[1]] 
                cv2.addWeighted(arrayTherm, alpha, output, 1 - alpha, 0, output)
                image[y_offset:y_offset+arrayTherm.shape[0], x_offset:x_offset+arrayTherm.shape[1]] = output
            
            self.count_FPS+=1

            obj_center, obj_bbox = ct.update(boxes)
            
            list_bboxes, dict_name = rpi.main_vision()
            # print('\n>>>>>>>>\n main2.py dict_name:', dict_name, obj_bbox, '\n>>>>>>>>')
            if list_bboxes is not None:
                obj_center, obj_bbox = ct.update(list_bboxes) # ---- TRACKING update
                # print('\n>>>>>>>>\n main2.py list_bboxes:', list_bboxes, obj_bbox, '\n>>>>>>>>')
                for (objectID, single_bbox) in obj_bbox.items():
                    id_name = int(np.array(single_bbox).sum())
                    if id_name in list(dict_name.keys()):
                        single_name = dict_name[id_name]
                        myPeople[objectID] = [single_name, suhu]
                        self.insert_list(single_name)
                getData = True
        else:
            pred_name='face'
            suhu = 36.8
        
        # ---- TRACKING
        
        if (self.count_FPS % 1 == 0) or start_time-time.time() < 3:
            obj_center, obj_bbox = ct.update(boxes)
            self.deleteExpireObject(myPeople, obj_center)
            print('# Global Tracking', obj_center)


        print("HEYY", myPeople, obj_center, boxes)
        # draw bbox
        for (objectID, centroid), single_bbox in zip(obj_center.items(), obj_bbox.values()):
            print("test", myPeople, objectID)
            if objectID in myPeople.keys():
                print("in 1 : ada kotak dan nama")
                draw_box_name(single_bbox, myPeople[objectID][0], image, suhu=myPeople[objectID][1])
            elif len(boxes) != 0:
                print("in 2 : ada kotak, nama tidak ada")
                draw_box_name(single_bbox, '_', image, suhu=suhu)
            else:
                print("in 3 : ", len(boxes))
                continue
                #myPeople[objectID] = ['ga kenal', 'ERR']
                #draw_box_name(single_bbox, myPeople[objectID][0], image, suhu=myPeople[objectID][1])


        FPS =  1/ (time.time()-start_time)     
        cv2.putText(image, "FPS: {:.2f}".format(FPS), (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 0, 0), 2)
        if self.count_FPS == 70:
            self.count_FPS = 0
            # tanda commit terbaru
        

        # get image infos
        height, width, channel = image.shape
        step = channel * width
        # create QImage from image
        qImg = QImage(image.data, width, height, step, QImage.Format_RGB888)
        # show image in img_label
        self.ui.lbl_video.setPixmap(QPixmap.fromImage(qImg))
    
    def getNewObject(self, myObj, trackingObj):
        futureObject = set(trackingObj.keys()).difference(myObj.keys())
        for i in futureObject:
            myObj[i] = ['ga kenal', 'ERR']

        return futureObject, myObj

    def deleteExpireObject(self, myObj, trackingObj):
        diff = set(myObj.keys()).difference(trackingObj.keys())
        for i in diff:
            del myObj[i]

    def processing_sensors(self):
        if on_RPi:
            rpi.main_input()

    def showTime(self):
        str_time = str(datetime.datetime.now().strftime("%H:%M"))
        self.ui.lbl_jam.setText("{}".format(str_time))
        hari=str(datetime.datetime.now().strftime("%A")) 
        tanggal=str(datetime.datetime.now().strftime("%d")) 
        idx_bulan=int(datetime.datetime.now().strftime("%m")) 
        bulan_name = bulan[idx_bulan-1]
        # hari = hari[:3]
        self.ui.lbl_tanggal.setText(f"{hari}, {tanggal} {bulan_name}")
    
    def insert_list(self,nama):
        time_masuk = "%s" % (str(datetime.datetime.now().strftime("%H:%M:%S"))) #:%S
        self.ui.lbl_name_recog.setText("{} @ {}".format(nama, time_masuk) )

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    # threadThermal = threading.Thread(target=MainWindow.visionThermal, args=image)
    # threadThermal.start()
    if on_RPi:
        window.showFullScreen()
    sys.exit(app.exec_())

