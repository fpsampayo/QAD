# -*- coding: latin1 -*-
"""
/***************************************************************************
 QAD Quantum Aided Design plugin

 comando INSERT per inserire un simbolo
 
                              -------------------
        begin                : 2013-12-31
        copyright            : (C) 2013 IREN Acqua Gas SpA
        email                : geosim.dev@irenacquagas.it
        developers           : roberto poltini (roberto.poltini@irenacquagas.it)
 ***************************************************************************/

/***************************************************************************
 *                                                                         *
 *   This program is free software; you can redistribute it and/or modify  *
 *   it under the terms of the GNU General Public License as published by  *
 *   the Free Software Foundation; either version 2 of the License, or     *
 *   (at your option) any later version.                                   *
 *                                                                         *
 ***************************************************************************/
"""


# Import the PyQt and QGIS libraries
from PyQt4.QtCore import *
from PyQt4.QtGui import *
from qgis.core import *


import qad_debug
import qad_utils
from qad_generic_cmd import QadCommandClass
import qad_layer
from qad_getpoint import *
from qad_getdist_cmd import QadGetDistClass
from qad_getangle_cmd import QadGetAngleClass
from qad_textwindow import *
from qad_msg import QadMsg


# Classe che gestisce il comando INSERT
class QadINSERTCommandClass(QadCommandClass):

   def getName(self):
      return QadMsg.translate("Command_list", "INSER")

   def connectQAction(self, action):
      QObject.connect(action, SIGNAL("triggered()"), self.plugIn.runINSERTCommand)
   
   def getIcon(self):
      return QIcon(":/plugins/qad/icons/insert.png")

   def getNote(self):
      # impostare le note esplicative del comando
      return QadMsg.translate("Command_INSERT", "Inserisce un simbolo.")
   
   def __init__(self, plugIn):
      QadCommandClass.__init__(self, plugIn)
      self.insPt = None
      self.scale = self.plugIn.lastScale
      self.rot = self.plugIn.lastRot
      self.GetDistClass = None
      self.GetAngleClass = None

   def __del__(self):
      QadCommandClass.__del__(self)
      if self.GetDistClass is not None:
         del self.GetDistClass
      if self.GetAngleClass is not None:
         del self.GetAngleClass

   def getPointMapTool(self, drawMode = QadGetPointDrawModeEnum.NONE):
      # quando si � in fase di richiesta distanza (scala)
      if self.step == 2:
         return self.GetDistClass.getPointMapTool()
      # quando si � in fase di richiesta rotazione
      elif self.step == 3:
         return self.GetAngleClass.getPointMapTool()
      else:
         return QadCommandClass.getPointMapTool(self, drawMode)
        
   def addFeature(self, layer):
      #qad_debug.breakPoint()
      transformedPoint = self.mapToLayerCoordinates(layer, self.insPt)
      g = QgsGeometry.fromPoint(transformedPoint)
      f = QgsFeature()
      f.setGeometry(g)
      # Add attribute fields to feature.
      fields = layer.pendingFields()
      f.setFields(fields)
      
      # assegno i valori di default
      provider = layer.dataProvider()
      for field in fields.toList():
         i = fields.indexFromName(field.name())
         f[field.name()] = provider.defaultValue(i)
      
      # se la scala dipende da un campo 
      scaleFldName = qad_layer.get_symbolScaleFieldName(layer)
      if len(scaleFldName) > 0:
         f.setAttribute(scaleFldName, self.scale)
      
      # se la rotazione dipende da un campo 
      rotFldName = qad_layer.get_symbolRotationFieldName(layer)
      if len(rotFldName) > 0:
         f.setAttribute(rotFldName, qad_utils.toDegrees(self.rot))
      
      return qad_layer.addFeatureToLayer(self.plugIn, layer, f)               
      
      
   def run(self, msgMapTool = False, msg = None):
      if self.plugIn.canvas.mapRenderer().destinationCrs().geographicFlag():
         self.showMsg(QadMsg.translate("QAD", "\nIl sistema di riferimento del progetto deve essere un sistema di coordinate proiettate.\n"))
         return True # fine comando
      
      currLayer, errMsg = qad_layer.getCurrLayerEditable(self.plugIn.canvas, QGis.Point)
      if currLayer is None:
         self.showMsg(errMsg)
         return True # fine comando

      if qad_layer.isSymbolLayer(currLayer) == False:
         errMsg = QadMsg.translate("QAD", "\nIl layer corrente non � di tipo simbolo.")
         errMsg = errMsg + QadMsg.translate("QAD", "\nUn layer simbolo � un layer vettoriale di tipo punto senza etichetta.\n")
         self.showMsg(errMsg)         
         return True # fine comando

               
      #=========================================================================
      # RICHIESTA PUNTO DI INSERIMENTO
      if self.step == 0: # inizio del comando
         self.waitForPoint() # si appresta ad attendere un punto
         self.step = self.step + 1
         return False
      
      #=========================================================================
      # RISPOSTA ALLA RICHIESTA PUNTO DI INSERIMENTO
      elif self.step == 1: # dopo aver atteso un punto si riavvia il comando
         if msgMapTool == True: # il punto arriva da una selezione grafica
            # la condizione seguente si verifica se durante la selezione di un punto
            # � stato attivato un altro plugin che ha disattivato Qad
            # quindi stato riattivato il comando che torna qui senza che il maptool
            # abbia selezionato un punto            
            if self.getPointMapTool().point is None: # il maptool � stato attivato senza un punto
               if self.getPointMapTool().rightButton == True: # se usato il tasto destro del mouse
                  return True # fine comando
               else:
                  self.setMapTool(self.getPointMapTool()) # riattivo il maptool
                  return False

            pt = self.getPointMapTool().point
         else: # il punto arriva come parametro della funzione
            pt = msg

         self.insPt = QgsPoint(pt)
         self.plugIn.setLastPoint(self.insPt)
         
         # se la scala dipende da un campo 
         scaleFldName = qad_layer.get_symbolScaleFieldName(currLayer)
         if len(scaleFldName) > 0:
            # si appresta ad attendere la scala                      
            self.GetDistClass = QadGetDistClass(self.plugIn)
            prompt = QadMsg.translate("Command_INSERT", "Specificare la scala del simbolo <{0}>: ")
            self.GetDistClass.msg = prompt.format(str(self.scale))
            self.GetDistClass.dist = self.scale
            self.GetDistClass.inputMode = QadInputModeEnum.NOT_NEGATIVE | QadInputModeEnum.NOT_ZERO
            self.GetDistClass.startPt = self.insPt
            self.step = 2
            self.GetDistClass.run(msgMapTool, msg)
            return False
         else: 
            # se la rotazione dipende da un campo 
            rotFldName = qad_layer.get_symbolRotationFieldName(currLayer)
            if len(rotFldName) > 0:
               if self.GetAngleClass is not None:
                  del self.GetAngleClass                  
               # si appresta ad attendere l'angolo di rotazione                      
               self.GetAngleClass = QadGetAngleClass(self.plugIn)
               prompt = QadMsg.translate("Command_INSERT", "Specificare la rotazione del simbolo <{0}>: ")
               self.GetAngleClass.msg = prompt.format(str(qad_utils.toDegrees(self.rot)))
               self.GetAngleClass.angle = self.rot
               self.GetAngleClass.startPt = self.insPt               
               self.step = 3
               self.GetAngleClass.run(msgMapTool, msg)               
               return False
            else:
               self.addFeature(currLayer)

         return True
      
      #=========================================================================
      # RISPOSTA ALLA RICHIESTA SCALA (da step = 1)
      elif self.step == 2:
         if self.GetDistClass.run(msgMapTool, msg) == True:
            if self.GetDistClass.dist is not None:
               self.scale = self.GetDistClass.dist
               self.plugIn.setLastScale(self.scale)
               del self.GetDistClass
               self.GetDistClass = None
                
               # se la rotazione dipende da un campo 
               rotFldName = qad_layer.get_symbolRotationFieldName(currLayer)
               if len(rotFldName) > 0:
                  if self.GetAngleClass is not None:
                     del self.GetAngleClass                  
                  # si appresta ad attendere l'angolo di rotazione                      
                  self.GetAngleClass = QadGetAngleClass(self.plugIn)
                  prompt = QadMsg.translate("Command_INSERT", "Specificare la rotazione del simbolo <{0}>: ")
                  self.GetAngleClass.msg = prompt.format(str(qad_utils.toDegrees(self.rot)))
                  self.GetAngleClass.angle = self.rot
                  self.GetAngleClass.startPt = self.insPt               
                  self.step = 3
                  self.GetAngleClass.run(msgMapTool, msg)         
                  return False
               else:
                  self.addFeature(currLayer)               
                  return True   
            else:
               return True   
         return False
      
      #=========================================================================
      # RISPOSTA ALLA RICHIESTA ROTAZIONE (da step = 1 o 2)
      elif self.step == 3:
         if self.GetAngleClass.run(msgMapTool, msg) == True:
            if self.GetAngleClass.angle is not None:
               self.rot = self.GetAngleClass.angle
               self.plugIn.setLastRot(self.rot)
               self.addFeature(currLayer)
               return True # fine comando
            else:
               return True
         return False
