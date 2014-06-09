# -*- coding: latin1 -*-
"""
/***************************************************************************
 QAD Quantum Aided Design plugin

 classe per gestire il map tool in ambito dei comandi di quotatura
 
                              -------------------
        begin                : 2013-05-22
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


from PyQt4.QtCore import *
from PyQt4.QtGui import *
from qgis.core import *
from qgis.gui import *
import math


import qad_debug
import qad_utils
from qad_snapper import *
from qad_snappointsdisplaymanager import *
from qad_variables import *
from qad_getpoint import *
from qad_dim import *
from qad_rubberband import QadRubberBand


#===============================================================================
# Qad_dim_maptool_ModeEnum class.
#===============================================================================
class Qad_dim_maptool_ModeEnum():
   # noto niente si richiede il primo punto di quotatura
   NONE_KNOWN_ASK_FOR_FIRST_PT = 1     
   # noto il primo punto si richiede il secondo punto di quotatura
   FIRST_PT_KNOWN_ASK_FOR_SECOND_PT = 2     
   # noto i punti di quotatura si richiede la posizione della linea di quota lineare
   FIRST_SECOND_PT_KNOWN_ASK_FOR_LINEAR_DIM_LINE_POS = 3     
   # si richiede il testo di quota
   ASK_FOR_TEXT = 6
   # noto i punti di quotatura si richiede la posizione della linea di quota allineata
   FIRST_SECOND_PT_KNOWN_ASK_FOR_ALIGNED_DIM_LINE_POS = 7

   # noto il primo punto di estremit� diam si richiede il secondo punto di estremit� diam
   FIRST_DIAM_PT_KNOWN_ASK_FOR_SECOND_DIAM_PT = 8
   # noto niente si richiede l'entita del primo punto di tangenza
   NONE_KNOWN_ASK_FOR_FIRST_TAN = 9
   # nota l'entita del primo punto di tangenza si richiede quella del secondo punto di tangenza
   FIRST_TAN_KNOWN_ASK_FOR_SECOND_TAN = 10
   # note la prima e la seconda entita dei punti di tangenza si richiede il raggio
   FIRST_SECOND_TAN_KNOWN_ASK_FOR_RADIUS = 11
   # noto note la prima, la seconda entita dei punti di tangenza e il primo punto per misurare il raggio
   # si richiede il secondo punto per misurare il raggio
   FIRST_SECOND_TAN_FIRSTPTRADIUS_KNOWN_ASK_FOR_SECONDPTRADIUS = 12

#===============================================================================
# Qad_dim_maptool class
#===============================================================================
class Qad_dim_maptool(QadGetPoint):
    
   def __init__(self, plugIn):
      QadGetPoint.__init__(self, plugIn)

      dimStyle = None
      self.dimPt1 = None
      self.dimPt2 = None
      self.dimCircle = None
      
      self.forcedTextRot = None # rotazione del testo di quota
      self.measure = None # misura della quota (se None viene calcolato)
      self.preferredAlignment = QadDimStyleAlignmentEnum.HORIZONTAL # allineamento della linea di quota
      self.forcedDimLineAlignment = None # allineamento della linea di quota forzato
      self.forcedDimLineRot = 0.0 # rotazione della linea di quota forzato
      
      self.__rubberBand = QadRubberBand(self.canvas)      
                              
      
      self.centerPt = None
      self.radius = None
      self.dimPt1 = None
      self.dimPt2 = None
      self.firstDiamPt = None
      self.tan1 = None
      self.tan2 = None
      self.startPtForRadius = None
      self.geomType = QGis.Polygon

   def hidePointMapToolMarkers(self):
      QadGetPoint.hidePointMapToolMarkers(self)
      self.__rubberBand.hide()

   def showPointMapToolMarkers(self):
      QadGetPoint.showPointMapToolMarkers(self)
      self.__rubberBand.show()
                             
   def clear(self):
      QadGetPoint.clear(self)
      self.__rubberBand.reset()
      self.mode = None    
            

   def seDimLineAlignment(self, LinePosPt, horizLine1, horizLine2, verticalLine1, verticalLine2):
      # < 0 se a sinistra della linea
      sxOfHorizLine1 = True if qad_utils.leftOfLine(LinePosPt, horizLine1[0], horizLine1[1]) < 0 else False
      sxOfHorizLine2 = True if qad_utils.leftOfLine(LinePosPt, horizLine2[0], horizLine2[1]) < 0 else False
      
      sxOfVerticalLine1 = True if qad_utils.leftOfLine(LinePosPt, verticalLine1[0], verticalLine1[1]) < 0 else False
      sxOfVerticalLine2 = True if qad_utils.leftOfLine(LinePosPt, verticalLine2[0], verticalLine2[1]) < 0 else False
      
      # se LinePosPt � tra le linee di limite orizzontale e non � tra le linee di limite verticale      
      if sxOfHorizLine1 != sxOfHorizLine2 and sxOfVerticalLine1 == sxOfVerticalLine2:
         self.preferredAlignment = QadDimStyleAlignmentEnum.HORIZONTAL
      # se LinePosPt non � tra le linee di limite orizzontale ed � tra le linee di limite verticale      
      elif sxOfHorizLine1 == sxOfHorizLine2 and sxOfVerticalLine1 != sxOfVerticalLine2:
         self.preferredAlignment = QadDimStyleAlignmentEnum.VERTICAL
      
      return
            

   #============================================================================
   # setLinearDimPtsAndDimLineAlignmentOnCircle
   #============================================================================
   def setLinearDimPtsAndDimLineAlignmentOnCircle(self, LinePosPt, circle):
      pt1 = qad_utils.getPolarPointByPtAngle(circle.center, self.forcedDimLineRot, circle.radius)
      pt2 = qad_utils.getPolarPointByPtAngle(pt1, self.forcedDimLineRot + math.pi / 2, circle.radius)
      horizLine1 = [pt1, pt2]
      
      pt1 = qad_utils.getPolarPointByPtAngle(circle.center, self.forcedDimLineRot, -1 * circle.radius)
      pt2 = qad_utils.getPolarPointByPtAngle(pt1, self.forcedDimLineRot + math.pi / 2, circle.radius)
      horizLine2 = [pt1, pt2]
      
      pt1 = qad_utils.getPolarPointByPtAngle(circle.center, self.forcedDimLineRot + math.pi / 2, circle.radius)
      pt2 = qad_utils.getPolarPointByPtAngle(pt1, self.forcedDimLineRot, circle.radius)
      verticalLine1 = [pt1, pt2]
      
      pt1 = qad_utils.getPolarPointByPtAngle(circle.center, self.forcedDimLineRot + math.pi / 2, -1 * circle.radius)
      pt2 = qad_utils.getPolarPointByPtAngle(pt1, self.forcedDimLineRot, circle.radius)
      verticalLine2 = [pt1, pt2]
      
      # se non � stato impostato un allineamento forzato, lo calcolo in automatico
      if self.forcedDimLineAlignment is None:         
         self.seDimLineAlignment(LinePosPt, horizLine1, horizLine2, verticalLine1, verticalLine2)
      else:
         self.preferredAlignment = self.forcedDimLineAlignment
         
      if self.preferredAlignment == QadDimStyleAlignmentEnum.HORIZONTAL:
         self.dimPt1 = horizLine1[0]
         self.dimPt2 = horizLine2[0]
      else:
         self.dimPt1 = verticalLine1[0]
         self.dimPt2 = verticalLine2[0]
         

   #============================================================================
   # setLinearDimLineAlignmentOnDimPts
   #============================================================================
   def setLinearDimLineAlignmentOnDimPts(self, LinePosPt):      
      # se non � stato impostato un allineamento forzato, lo calcolo in automatico
      if self.forcedDimLineAlignment is None:         
         pt2 = qad_utils.getPolarPointByPtAngle(self.dimPt1, self.forcedDimLineRot + math.pi / 2, 1)
         horizLine1 = [self.dimPt1, pt2]
         
         pt2 = qad_utils.getPolarPointByPtAngle(self.dimPt2, self.forcedDimLineRot + math.pi / 2, 1)
         horizLine2 = [self.dimPt2, pt2]
         
         pt2 = qad_utils.getPolarPointByPtAngle(self.dimPt1, self.forcedDimLineRot, 1)
         verticalLine1 = [self.dimPt1, pt2]
         
         pt2 = qad_utils.getPolarPointByPtAngle(self.dimPt2, self.forcedDimLineRot, 1)
         verticalLine2 = [self.dimPt2, pt2]
         
         self.seDimLineAlignment(LinePosPt, horizLine1, horizLine2, verticalLine1, verticalLine2)
      else:
         self.preferredAlignment = self.forcedDimLineAlignment
            
            
   #============================================================================
   # canvasMoveEvent
   #============================================================================
   def canvasMoveEvent(self, event):
      #qad_debug.breakPoint()
      QadGetPoint.canvasMoveEvent(self, event)
      
      self.__rubberBand.reset()            
         
      items = []
      dimPtFeatures = [None, None]
      dimLineFeatures = [None, None]
      textFeature = None
      blockFeatures = [None, None]
      extLineFeatures = [None, None]
      txtLeaderLineFeature = None
      
      # noti i punti di quotatura si richiede la posizione della linea di quota lineare
      if self.mode == Qad_dim_maptool_ModeEnum.FIRST_SECOND_PT_KNOWN_ASK_FOR_LINEAR_DIM_LINE_POS:
         if self.dimCircle is not None:
            self.setLinearDimPtsAndDimLineAlignmentOnCircle(self.tmpPoint, self.dimCircle)
         else:
            self.setLinearDimLineAlignmentOnDimPts(self.tmpPoint)
                     
         dimPtFeatures, dimLineFeatures, textFeatureGeom, \
         blockFeatures, extLineFeatures, txtLeaderLineFeature = self.dimStyle.getLinearDimFeatures(self.canvas, \
                                                                                                   self.dimPt1, \
                                                                                                   self.dimPt2, \
                                                                                                   self.tmpPoint, \
                                                                                                   self.measure, \
                                                                                                   self.preferredAlignment, \
                                                                                                   self.forcedDimLineRot)
         textFeature = textFeatureGeom[0]
         textRectGeom = textFeatureGeom[1]
      # noti i punti di quotatura si richiede la posizione della linea di quota allineata
      elif self.mode == Qad_dim_maptool_ModeEnum.FIRST_SECOND_PT_KNOWN_ASK_FOR_ALIGNED_DIM_LINE_POS:                     
         dimPtFeatures, dimLineFeatures, textFeatureGeom, \
         blockFeatures, extLineFeatures, txtLeaderLineFeature = self.dimStyle.getAlignedDimFeatures(self.canvas, \
                                                                                                    self.dimPt1, \
                                                                                                    self.dimPt2, \
                                                                                                    self.tmpPoint, \
                                                                                                    self.measure)
         textFeature = textFeatureGeom[0]
         textRectGeom = textFeatureGeom[1]

         
      # punti di quotatura
      if dimPtFeatures[0] is not None:
         items.append([dimPtFeatures[0].geometry(), self.dimStyle.symbolLayer])
      if dimPtFeatures[1] is not None:
         items.append([dimPtFeatures[1].geometry(), self.dimStyle.symbolLayer])
      # linee di quota
      if dimLineFeatures[0] is not None:
         items.append([dimLineFeatures[0].geometry(), self.dimStyle.lineLayer])
      if dimLineFeatures[1] is not None:
         items.append([dimLineFeatures[1].geometry(), self.dimStyle.lineLayer])
      # testo di quota
      if textFeature is not None:
         items.append([textFeature.geometry(), self.dimStyle.textLayer])
         items.append([textRectGeom, self.dimStyle.textLayer])
      # simboli di quota
      if blockFeatures[0] is not None:
         items.append([blockFeatures[0].geometry(), self.dimStyle.symbolLayer])
      if blockFeatures[1] is not None:
         items.append([blockFeatures[1].geometry(), self.dimStyle.symbolLayer])
      # linee di estensione della quota
      if extLineFeatures[0] is not None:
         items.append([extLineFeatures[0].geometry(), self.dimStyle.lineLayer])
      if extLineFeatures[1] is not None:
         items.append([extLineFeatures[1].geometry(), self.dimStyle.lineLayer])
      # linea leader del testo di quota   
      if txtLeaderLineFeature is not None:
         items.append([txtLeaderLineFeature.geometry(), self.dimStyle.lineLayer])
         
      # noto il centro del cerchio si richiede il diametro
      #elif self.mode == Qad_dim_maptool_ModeEnum.CENTER_PT_KNOWN_ASK_FOR_DIAM:
      #   pass
      
      for item in items:         
         self.__rubberBand.addGeometry(item[0], item[1]) # geom e layer
    
   def activate(self):
      QadGetPoint.activate(self)            
      if self.__rubberBand is not None:
         self.__rubberBand.show()

   def deactivate(self):
      QadGetPoint.deactivate(self)
      if self.__rubberBand is not None:
         self.__rubberBand.hide()

   def setMode(self, mode):
      self.mode = mode
      # noto niente si richiede il primo punto di quotatura
      if self.mode == Qad_dim_maptool_ModeEnum.NONE_KNOWN_ASK_FOR_FIRST_PT:
         self.setDrawMode(QadGetPointDrawModeEnum.NONE)
      # noto il primo punto si richiede il secondo punto di quotatura
      elif self.mode == Qad_dim_maptool_ModeEnum.FIRST_PT_KNOWN_ASK_FOR_SECOND_PT:
         self.setDrawMode(QadGetPointDrawModeEnum.ELASTIC_LINE)
         self.setStartPoint(self.dimPt1)
      # noto i punti di quotatura si richiede la posizione della linea di quota
      elif self.mode == Qad_dim_maptool_ModeEnum.FIRST_SECOND_PT_KNOWN_ASK_FOR_LINEAR_DIM_LINE_POS:
         self.setDrawMode(QadGetPointDrawModeEnum.NONE)         
      # si richiede il testo di quota
      elif self.mode == Qad_dim_maptool_ModeEnum.ASK_FOR_TEXT:     
         self.setDrawMode(QadGetPointDrawModeEnum.NONE)         
      # noti i punti di quotatura si richiede la posizione della linea di quota allineata
      elif self.mode == Qad_dim_maptool_ModeEnum.FIRST_SECOND_PT_KNOWN_ASK_FOR_ALIGNED_DIM_LINE_POS:
         self.setDrawMode(QadGetPointDrawModeEnum.NONE)         
         
         
      # noto niente si richiede il primo punto di estremit� diam
      elif self.mode == Qad_dim_maptool_ModeEnum.NONE_KNOWN_ASK_FOR_FIRST_DIAM_PT:     
         self.setDrawMode(QadGetPointDrawModeEnum.NONE)                 
      # noto il primo punto di estremit� diam si richiede il secondo punto di estremit� diam
      elif self.mode == Qad_dim_maptool_ModeEnum.FIRST_DIAM_PT_KNOWN_ASK_FOR_SECOND_DIAM_PT:     
         self.setDrawMode(QadGetPointDrawModeEnum.NONE)
      # noto niente si richiede l'entita del primo punto di tangenza
      elif self.mode == Qad_dim_maptool_ModeEnum.NONE_KNOWN_ASK_FOR_FIRST_TAN:     
         self.setDrawMode(QadGetPointDrawModeEnum.NONE)
         self.setSelectionMode(QadGetPointSelectionModeEnum.ENTITY_SELECTION)
         self.forceSnapTypeOnce(QadSnapTypeEnum.TAN_DEF)         
      # nota l'entita del primo punto di tangenza si richiede quella del secondo punto di tangenza
      elif self.mode == Qad_dim_maptool_ModeEnum.FIRST_TAN_KNOWN_ASK_FOR_SECOND_TAN:     
         self.setDrawMode(QadGetPointDrawModeEnum.NONE)
         self.setSelectionMode(QadGetPointSelectionModeEnum.ENTITY_SELECTION)
         self.forceSnapTypeOnce(QadSnapTypeEnum.TAN_DEF)         
      # note la prima e la seconda entita dei punti di tangenza si richiede il raggio
      elif self.mode == Qad_dim_maptool_ModeEnum.FIRST_SECOND_TAN_KNOWN_ASK_FOR_RADIUS:     
         self.setDrawMode(QadGetPointDrawModeEnum.NONE)
         # siccome il puntatore era stato variato in ENTITY_SELECTION dalla selez precedente
         self.setSelectionMode(QadGetPointSelectionModeEnum.POINT_SELECTION)         
      # noto note la prima, la seconda entita dei punti di tangenza e il primo punto per misurare il raggio
      # si richiede il secondo punto per misurare il raggio
      elif self.mode == Qad_dim_maptool_ModeEnum.FIRST_SECOND_TAN_FIRSTPTRADIUS_KNOWN_ASK_FOR_SECONDPTRADIUS:     
         self.setDrawMode(QadGetPointDrawModeEnum.ELASTIC_LINE)
         self.setStartPoint(self.startPtForRadius)
