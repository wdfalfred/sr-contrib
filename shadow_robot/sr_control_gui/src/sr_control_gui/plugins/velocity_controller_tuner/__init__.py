#!/usr/bin/env python
#
# Copyright 2011 Shadow Robot Company Ltd.
#
# This program is free software: you can redistribute it and/or modify it
# under the terms of the GNU General Public License as published by the Free
# Software Foundation, either version 2 of the License, or (at your option)
# any later version.
#
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or
# FITNESS FOR A PARTICULAR PURPOSE.  See the GNU General Public License for
# more details.
#
# You should have received a copy of the GNU General Public License along
# with this program.  If not, see <http://www.gnu.org/licenses/>.
#

import roslib; roslib.load_manifest('sr_control_gui')
import rospy

from generic_plugin import GenericPlugin
from control_toolbox.srv import SetPidGains
from sr_robot_msgs.srv import ForceController
from functools import partial
import threading, time, math

from sr_friction_compensation.u_map_computation_main import FrictionCompensation

from std_msgs.msg import Float64

from PyQt4 import QtCore, QtGui, Qt

class BaseMovement(object):
    def __init__(self, joint_name):
        self.joint_name = joint_name

        self.msg_to_send = Float64()
        self.msg_to_send.data = 0.0
        self.sleep_time = 0.0001

        topic = "/sh_"+ joint_name.lower() +"_velocity_controller/command"
        self.publisher = rospy.Publisher(topic, Float64)

    def publish(self, mvt_percentage):
        self.update(mvt_percentage)
        self.publisher.publish(self.msg_to_send)
        time.sleep(self.sleep_time)

    def update(self, mvt_percentage):
        pass

class SinusoidMovement(BaseMovement):
    def __init__(self, joint_name, amplitude = 1.):
        BaseMovement.__init__(self,joint_name)
        self.amplitude = amplitude

    def update(self, mvt_percentage):
        value = self.amplitude * math.sin(2.0*3.14159 * mvt_percentage/100.)
        self.msg_to_send.data = value

class StepMovement(BaseMovement):
    def __init__(self, joint_name, amplitude = 1.57, nb_steps = 50):
        BaseMovement.__init__(self,joint_name)
        self.amplitude = amplitude
        self.nb_steps  = nb_steps

        self.steps = []
        for i in range(0, int(nb_steps/2)):
            self.steps.append(2.*float(i)*float(self.amplitude / nb_steps))
        reversed_steps = self.steps[:]
        reversed_steps.reverse()
        self.steps += reversed_steps

    def update(self, mvt_percentage):
        index = int(self.nb_steps * mvt_percentage / 100.)
        if index >= len(self.steps):
            index = len(self.steps) - 1
        value = self.steps[ index ]
        self.msg_to_send.data = value


class FullMovement(threading.Thread):
    def __init__(self, joint_name):
        threading.Thread.__init__(self)
        self.moving = False
        self.joint_name = joint_name
        self.iterations = 10000
        self.movements = [SinusoidMovement(joint_name)]
        #self.movements = [StepMovement(joint_name),
        #                  SinusoidMovement(joint_name),
        #                  SinusoidMovement(joint_name),
        #                  StepMovement(joint_name, nb_steps = 10)]

    def run(self):
        while(True):
            for movement in self.movements:
                for mvt_percentage in range(0, self.iterations):
                    if self.moving == False:
                        return
                    else:
                        movement.publish(mvt_percentage/(self.iterations/100.))



class RunFriction(threading.Thread):
    def __init__(self, joint_name, parent):
        threading.Thread.__init__(self)
        self.parent = parent
        self.joint_name = joint_name
        self.stopped = False
        self.FC = FrictionCompensation(joint_name = "FFJ4", n = 15,P=0, I=0, D=0, shift=0)

    def run(self):
        self.FC.run()
        self.parent.friction_finished()


class JointPidSetter(QtGui.QFrame):
    """
    Set the force PID settings for a given joint.
    """

    def __init__(self, joint_name, parent):
        """
        """
        QtGui.QFrame.__init__(self)

        self.friction = False
        self.friction_thread = None

        self.parent = parent
        self.joint_name = joint_name

        #/sh_ffj0_velocity_controller/set_gains
        service_name = "/sh_"+ joint_name.lower()+"_velocity_controller/set_gains"
        self.pid_service = rospy.ServiceProxy(service_name, SetPidGains)

        self.layout_ = QtGui.QHBoxLayout()

        label = QtGui.QLabel("<font color=red>"+joint_name+"</font>")
        self.layout_.addWidget( label )

        self.ordered_params = ["p",
                               "i",
                               "d",
                               "iclamp"]

        self.parameters = {}
        for param in self.ordered_params:
            #a parameter contains:
            #   - the value
            #   - a QLineEdit to be able to modify the value
            #   - an array containing the min/max
            self.parameters[param] = [0,0,[-10230,10230]]

        for parameter_name in self.ordered_params:
            parameter = self.parameters[parameter_name]
            label = QtGui.QLabel(parameter_name)
            self.layout_.addWidget( label )

            text_edit = QtGui.QLineEdit()
            text_edit.setFixedHeight(30)
            text_edit.setFixedWidth(50)
            text_edit.setText( str(parameter[0]) )

            validator = QtGui.QIntValidator(parameter[2][0], parameter[2][1], self)
            text_edit.setValidator(validator)


            parameter[1] = text_edit
            self.layout_.addWidget(text_edit)
            plus_minus_frame = QtGui.QFrame()
            plus_minus_layout = QtGui.QVBoxLayout()

            plus_btn = QtGui.QPushButton()
            plus_btn.setText("+")
            plus_btn.setFixedWidth(20)
            plus_btn.setFixedHeight(20)
            plus_btn.clicked.connect(partial(self.plus, parameter_name))
            plus_minus_layout.addWidget(plus_btn)

            minus_btn = QtGui.QPushButton()
            minus_btn.setText("-")
            minus_btn.setFixedWidth(20)
            minus_btn.setFixedHeight(20)
            minus_btn.clicked.connect(partial(self.minus, parameter_name))
            plus_minus_layout.addWidget(minus_btn)

            plus_minus_frame.setLayout(plus_minus_layout)

            self.layout_.addWidget(plus_minus_frame)

        btn = QtGui.QPushButton()
        btn.setText("SET")
        btn.setToolTip("Sends the current PID parameters to the joint.")
        self.connect(btn, QtCore.SIGNAL('clicked()'),self.set_pid)
        self.layout_.addWidget(btn)

        self.moving = False
        self.full_movement = None

        self.btn_move = QtGui.QPushButton()
        self.btn_move.setText("Move")
        self.btn_move.setToolTip("Move the joint through a continuous movement, press again to stop.")
        self.connect(self.btn_move, QtCore.SIGNAL('clicked()'),self.move_clicked)
        self.layout_.addWidget(self.btn_move)

        btn_automatic_pid = QtGui.QPushButton()
        btn_automatic_pid.setText( "Automatic" )
        btn_automatic_pid.setToolTip("Finishes the PID tuning automatically using a genetic algorithm.")
        self.connect(btn_automatic_pid, QtCore.SIGNAL('clicked()'),self.automatic_tuning)
        self.layout_.addWidget(btn_automatic_pid)

        self.btn_friction_compensation = QtGui.QPushButton()
        self.btn_friction_compensation.setText( "Friction" )
        self.btn_friction_compensation.setToolTip("Computes the Friction Compensation umap")
        self.connect(self.btn_friction_compensation, QtCore.SIGNAL('clicked()'),self.friction_compensation)
        self.layout_.addWidget(self.btn_friction_compensation)

        self.setLayout(self.layout_)

    def friction_compensation(self):
        if self.friction:
            self.btn_friction_compensation.setIcon(self.green_icon)
            self.friction_thread.tuning = False
            self.friction_thread.FC.stop()
            self.friction_thread.join()
            self.friction_thread = None

            self.btn_friction_compensation.setIcon(self.green_icon)
            self.friction = False
            self.btn_move.setEnabled(True)

        else:
            if self.moving:
                self.full_movement.moving = False
                self.moving = False
                self.full_movement.join()
                self.full_movement = None
                self.btn_move.setIcon(self.green_icon)
                self.btn_move.setEnabled(False)

            self.friction_thread = RunFriction(self.joint_name, self)
            self.friction_thread.start()

            self.friction = True
            self.btn_friction_compensation.setIcon(self.red_icon)

    def friction_finished(self):
        #TODO: add a popup to tell people the friction finished properly,
        # may be we should display the points + the line
        self.btn_friction_compensation.setIcon(self.green_icon)
        self.friction_thread.tuning = False
        self.friction_thread.FC.stop()
        self.friction_thread = None

        self.btn_friction_compensation.setIcon(self.green_icon)
        self.friction = False
        self.btn_move.setEnabled(True)


    def automatic_tuning(self):
        print "Automatic PID Tuning"

    def plus(self, param_name):
        param = self.parameters[param_name]

        value = param[1].text().toInt()[0]
        value += 1
        if value > param[2][1]:
            value = param[2][1]

        param[1].setText( str( value ) )

    def minus(self, param_name):
        param = self.parameters[param_name]

        value = param[1].text().toInt()[0]
        value -= 1
        if value < param[2][0]:
            value = param[2][0]
        param[1].setText( str( value ) )

    def move_clicked(self):
        if self.moving:
            self.full_movement.moving = False
            self.moving = False
            self.full_movement.join()
            self.full_movement = None
            self.btn_move.setIcon(self.green_icon)
        else:
            self.moving = True
            self.full_movement = FullMovement(self.joint_name)
            self.full_movement.moving = True
            self.full_movement.start()
            self.btn_move.setIcon(self.red_icon)

    def set_pid(self):
        for param in self.parameters.items():
            param[1][0] = param[1][1].text().toInt()[0]
        try:
            self.pid_service( self.parameters["p"][0], self.parameters["i"][0],
                              self.parameters["d"][0], self.parameters["iclamp"][0] )
        except:
            print "Failed to set pid."

    def activate(self):
        self.green_icon = QtGui.QIcon(self.parent.parent.parent.parent.rootPath + '/images/icons/colors/green.png')
        self.red_icon = QtGui.QIcon(self.parent.parent.parent.parent.rootPath + '/images/icons/colors/red.png')
        self.btn_move.setIcon(self.green_icon)
        self.btn_friction_compensation.setIcon(self.green_icon)


    def on_close(self):
        if self.full_movement != None:
            self.full_movement.moving = False
            self.moving = False
            self.full_movement.join()


class FingerPIDSetter(QtGui.QFrame):
    """
    set the PID settings for the finger.
    """

    def __init__(self, finger_name, joint_names, parent):
        QtGui.QFrame.__init__(self)
        self.parent = parent
        self.setFrameShape(QtGui.QFrame.Box)

        self.finger_name = finger_name
        self.joint_names = joint_names

        self.layout_ = QtGui.QVBoxLayout()

        self.joint_pid_setter = []
        for joint_name in self.joint_names:
            self.joint_pid_setter.append( JointPidSetter(joint_name, self) )

        for j_pid_setter in self.joint_pid_setter:
            self.layout_.addWidget( j_pid_setter )

        self.setLayout(self.layout_)

    def activate(self):
        for jps in self.joint_pid_setter:
            jps.activate()

    def on_close(self):
        for j_pid_setter in self.joint_pid_setter:
            j_pid_setter.on_close()


class VelocityControllerTuner(GenericPlugin):
    """
    A plugin to easily tune the force controller on the etherCAT hand.
    """
    name = "Velocity Controller Tuner"

    def __init__(self):
        GenericPlugin.__init__(self)

        self.frame = QtGui.QFrame()
        self.layout = QtGui.QVBoxLayout()

        self.joints = {"FF": ["FFJ0", "FFJ3", "FFJ4"],
                       "MF": ["MFJ0", "MFJ3", "MFJ4"],
                       "RF": ["RFJ0", "RFJ3", "RFJ4"],
                       "LF": ["LFJ0", "LFJ3", "LFJ4", "LFJ5"],
                       "TH": ["THJ1", "THJ2", "THJ3", "THJ4", "THJ5"]}
        self.finger_pid_setters = []

        for finger in self.joints.items():
            self.finger_pid_setters.append( FingerPIDSetter(finger[0], finger[1], self) )

        self.qtab_widget = QtGui.QTabWidget()
        for f_pid_setter in self.finger_pid_setters:
            self.qtab_widget.addTab(f_pid_setter, f_pid_setter.finger_name)

        self.layout.addWidget( self.qtab_widget )

        self.frame.setLayout(self.layout)
        self.window.setWidget(self.frame)

    def activate(self):
        GenericPlugin.activate(self)

        for fps in self.finger_pid_setters:
            fps.activate()

        self.set_icon(self.parent.parent.rootPath + '/images/icons/iconHand.png')

    def on_close(self):
        GenericPlugin.on_close(self)
        for f_pid_setter in self.finger_pid_setters:
            f_pid_setter.on_close()























