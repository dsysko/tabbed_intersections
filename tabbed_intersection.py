#! /usr/bin/env python
'''
Generates Inkscape SVG paths containing line segments intended to add into
your laser cut design fo tabbed construction of arbitrary angle corners
taking kerf and clearance into account. I account for the interference
of the material in the corners assuming the pivot is the intersection of
the central planes of the 2 pieces(the centre of the material thickness),
with the defined offset relative to the end of the piece by the material
thickness. I also provide options for additional tab cut depth(for a window
behind the join, and additional tab(for extra tab length beyond the join).

This work is based on the excellent work of Elliot White. His original
copyright notice is:
Copyright (C) 2011 elliot white   elliot@twot.eu
This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

I extend Elliot's work under the same GPLv3 license:
Copyright (c) 2015 Dustin Sysko   dsysko@gmail.com

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <http://www.gnu.org/licenses/>.
'''
__version__ = "0.10" ### please report bugs, suggestions etc to dsysko@gmail.com ###

## unittouu method changed to InkScape 0.91 style ##
## this version will NOT work in InkScape 0.48    ##

import sys, inkex, simplestyle, gettext, datetime, math
_ = gettext.gettext
## sys.stdout=open('c:\\temp\\tabbed_intersection_log.txt', 'w')
## print datetime.datetime.now().strftime("%Y-%m-%dT%H:%M:%S%z")


class IntersectionMaker(inkex.Effect):
  def __init__(self):
      # Call the base class constructor.
      inkex.Effect.__init__(self)
      # Define options
      self.OptionParser.add_option('--unit', action='store', type='string',
        dest='unit', default='mm', help='Measurement Units')
      self.OptionParser.add_option('--length', action='store', type='float',
        dest='length', default=100, help='Length of intersection')
      self.OptionParser.add_option('--angle', action='store', type='float',
        dest='angle', default=90.0, help='Interior angle of intersection')
      self.OptionParser.add_option('--depth_plus', action='store', type='float',
        dest='depth_plus', default=100, help='Additional depth of cut')
      self.OptionParser.add_option('--tab_plus', action='store', type='float',
        dest='tab_plus', default=100, help='Additional length of tabs past intersection')
      self.OptionParser.add_option('--tab', action='store', type='float',
        dest='tab', default=25, help='Nominal Tab Width')
      self.OptionParser.add_option('--tab_width_fixed', action='store', type='int',
        dest='tab_width_fixed', default=0, help='Tab width fixed or auto')
      self.OptionParser.add_option('--equal', action='store', type='int',
        dest='equal', default=0, help='Fixed or Automatic Tabs')
      self.OptionParser.add_option('--odd_even_tabs', action='store', type='int',
        dest='odd_even_tabs', default=0, help='Odd/even tab # per side(0 = auto)')
      self.OptionParser.add_option('--tab_count', action='store', type='int',
        dest='tab_count', default=0, help='Tab Count(0 = auto)')
      self.OptionParser.add_option('--thickness', action='store', type='float',
        dest='thickness', default=10, help='Material Thickness')
      self.OptionParser.add_option('--kerf', action='store', type='float',
        dest='kerf', default=0.5, help='Kerf (width) of cut')
      self.OptionParser.add_option('--clearance', action='store', type='float',
        dest='clearance', default=0.01, help='Clearance of joints')
      self.OptionParser.add_option('--style', action='store', type='int',
        dest='style', default=25, help='Layout/Style')
      self.OptionParser.add_option('--spacing', action='store', type='float',
        dest='spacing', default=25, help='Part Spacing')

  def effect(self):
    global parent, nomTab, equalTabs, thickness, correction, error

        # Get access to main SVG document element and get its dimensions.
    svg = self.document.getroot()

        # Get the attibutes:
    docWidth  = self.unittouu(svg.get('width'))
    docHeight = self.unittouu(svg.get('height'))

        # Create a new layer.
    layer = inkex.etree.SubElement(svg, 'g')
    layer.set(inkex.addNS('label', 'inkscape'), 'newlayer')
    layer.set(inkex.addNS('groupmode', 'inkscape'), 'layer')

    parent=self.current_layer

        # Get script's option values.
    unit=self.options.unit
    X = self.unittouu( str(self.options.length)  + unit )
    Y = 100 # I'd like to make this zero, but 0 or 1 cause a div/0 error on line 195
                                        #(gapWidth=(length-tabs*nomTab)/(divs-tabs))
    Z = 100 # same as for Y
    thickness = self.unittouu( str(self.options.thickness)  + unit )
    nomTab = self.unittouu( str(self.options.tab) + unit )
    equalTabs=self.options.equal
    kerf = self.unittouu( str(self.options.kerf)  + unit )
    clearance = self.unittouu( str(self.options.clearance)  + unit )
    layout=self.options.style
    spacing = self.unittouu( str(self.options.spacing)  + unit )

    correction=kerf-clearance

    # check input values mainly to avoid python errors
    # TODO restrict values to *correct* solutions
    error=0

    if X==0:
      inkex.errormsg(_('Error: Dimensions must be non zero'))
      error=1
    if X>max(docWidth, docHeight)*10: # crude test
      inkex.errormsg(_('Error: Dimensions Too Large'))
      error=1
    if X<3*nomTab:
      inkex.errormsg(_('Error: Tab size too large'))
      error=1
    if nomTab<thickness:
      inkex.errormsg(_('Error: Tab size too small'))
      error=1
    if thickness==0:
      inkex.errormsg(_('Error: Thickness is zero'))
      error=1
    if thickness>X/3: # crude test
      inkex.errormsg(_('Error: Material too thick'))
      error=1
    if correction>X/3: # crude test
      inkex.errormsg(_('Error: Kerf/Clearence too large'))
      error=1
    if spacing>X*10: # crude test
      inkex.errormsg(_('Error: Spacing too large'))
      error=1
    if spacing<kerf:
      inkex.errormsg(_('Error: Spacing too small'))
      error=1

    if error: exit()

    # layout format:(rootx), (rooty), Xlength, Ylength, tabInfo
    # root= (spacing, X,Y)
    # tabInfo= tab calc type
    if   layout==1: # Side-by-side Layout
      pieces=[[(2, 0,0, 1), (3, 0,0, 1), X,Y, 0b1010],\
        [(1, 0,0, 0), (2, 1,0, 1), X,Y, 0b0101]]
    elif layout==2: # In-line(compact) Layout
      pieces=[[(1, 0,0, 0), (1, 0,0, 0), X,Y, 0b1010],\
        [(2, 1,0, 0), (1, 0,0, 0), X,Y, 0b0101]]
    '''
    if   layout==1: # Side-by-side Layout
      pieces=[[(2, 0,0, 1), (3, 0,1, 1), X,Z, 0b1010],\
          [(1, 0,0, 0), (2, 0,0, 1), Z,Y, 0b1111],
        [(2, 0,0, 1), (2, 0,0, 1), X,Y, 0b0000],\
          [(3, 1,0, 1), (2, 0,0, 1), Z,Y, 0b1111],
        [(4, 1,0, 2), (2, 0,0, 1), X,Y, 0b0000],\
          [(2, 0,0, 1), (1, 0,0, 0), X,Z, 0b1010]]
    elif layout==2: # In-line(compact) Layout
      pieces=[[(1, 0,0, 0), (1, 0,0, 0), X,Y, 0b0000],\
          [(2, 1,0, 0), (1, 0,0, 0), X,Y, 0b0000],
        [(3, 2,0, 0), (1, 0,0, 0), Z,Y, 0b0101],\
          [(4, 2,0, 1), (1, 0,0, 0), Z,Y, 0b0101],
        [(5, 2,0, 2), (1, 0,0, 0), X,Z, 0b1111],\
          [(6, 3,0, 2), (1, 0,0, 0), X,Z, 0b1111]]
    '''

    for piece in pieces: # generate and draw each piece of the box
      (xs, xx, xy, xz)=piece[0]
      (ys, yx, yy, yz)=piece[1]
      x=xs*spacing+xx*X+xy*Y+xz*Z  # root x co-ord for piece
      y=ys*spacing+yx*X+yy*Y+yz*Z  # root y co-ord for piece
      dx=piece[2]
      dy=piece[3]
      tabs=piece[4]
      a=tabs>>3&1; b=tabs>>2&1; c=tabs>>1&1; d=tabs&1 # extract tab status for each side

      # generate and draw the two interface sides
      drawInterface(side((x, y), (d, a), (-b, a), -thickness if a else thickness, dx, (1, 0), a))          # side a

    if error: inkex.errormsg(_('Warning: Box may be impractical'))

def drawInterface(XYstring):         # Draw lines from a list
  name='part'
  style = { 'stroke': '#000000', 'fill': 'none' }
  drw = {'style':simplestyle.formatStyle(style), inkex.addNS('label', 'inkscape'):name, 'd':XYstring}
  inkex.etree.SubElement(parent, inkex.addNS('path', 'svg'), drw )
  return

def side((rx, ry), (sox, soy), (eox, eoy), tabVec, length, (dirx, diry), isTab):
  #       root startOffset endOffset tabVec length  direction  isTab

  divs=int(length/nomTab)  # divisions
  if not divs%2: divs-=1   # make divs odd
  divs=float(divs)
  tabs=(divs-1)/2          # tabs for side

  if equalTabs:
    gapWidth=tabWidth=length/divs
  else:
    tabWidth=nomTab
    gapWidth=(length-tabs*nomTab)/(divs-tabs)

  if isTab:                 # kerf correction
    gapWidth-=correction
    tabWidth+=correction
    first=correction/2
  else:
    gapWidth+=correction
    tabWidth-=correction
    first=-correction/2

  s=[]
  firstVec=0; secondVec=tabVec
  dirxN=0 if dirx else 1 # used to select operation on x or y
  diryN=0 if diry else 1
  (Vx, Vy)=(rx+sox*thickness, ry+soy*thickness)
  (VxTemp, VyTemp)=(Vx, Vy)
  s='M '+str(Vx)+', '+str(Vy)+' '

  if dirxN: Vy=ry # set 'correct' line start
  if diryN: Vx=rx

  # generate line as tab or hole using:
  #   last co-ord:Vx, Vy ; tab dir:tabVec  ; direction:dirx, diry ; thickness:thickness
  #   divisions:divs ; gap width:gapWidth ; tab width:tabWidth

  for n in range(1, int(divs)):
    if n%2:
      Vx=Vx+dirx*gapWidth+dirxN*firstVec+first*dirx
      Vy=Vy+diry*gapWidth+diryN*firstVec+first*diry
      if first and ((min(abs(Vx-VxTemp), abs(Vy-VyTemp)))<thickness) : error=1
      s+='L '+str(Vx)+', '+str(Vy)+' '
      Vx=Vx+dirxN*secondVec
      Vy=Vy+diryN*secondVec
      s+='L '+str(Vx)+', '+str(Vy)+' '
    else:
      Vx=Vx+dirx*tabWidth+dirxN*firstVec
      Vy=Vy+diry*tabWidth+diryN*firstVec
      s+='L '+str(Vx)+', '+str(Vy)+' '
      Vx=Vx+dirxN*secondVec
      Vy=Vy+diryN*secondVec
      s+='L '+str(Vx)+', '+str(Vy)+' '
    (secondVec, firstVec)=(-secondVec, -firstVec) # swap tab direction
    first=0
  s+='L '+str(rx+eox*thickness+dirx*length)+', '+str(ry+eoy*thickness+diry*length)+' '
  error=1
  return s

def GetTabDepth():
  floatTabDepth = FALSE
  return floatTabDepth

def GetTabwidthDetail(floatIntersectionLength, floatTabWidth, blnTabWidthFixed, blnOddTabs, intTabCount, floatMinTabWidth):
  arrTabDetail = {}
  arrTabDetail['floatEndTabWidth'] = FALSE
  arrTabDetail['floatInternalTabWidth'] = FALSE
  arrTabDetail['intTabCount'] = FALSE
  arrTabDetail['arrTabs'] = {}
  # define the individual tab transitions here as points along the line from the origin
  # we will define the actual tab dimensions later to include kerf, fit, etc.

  #case when tab width, parity, and count are auto:
  if blnTabWidthFixed == 0 and blnOddTabs == 0 and intTabCount == 0:
    arrTabDetail['intTabCount'] = math.floor(floatIntersectionLength, floatMinTabWidth)
    arrTabDetail['floatInternalTabWidth'] = floatMinTabWidth
    arrTabDetail['floatEndTabWidth'] = arrTabDetail['floatInternalTabWidth'] + math.fmod(floatIntersectionLength, arrTabDetail['floatInternalTabWidth']) / 2

  #case when tab width and parity are auto, and count is set:
  elif blnTabWidthFixed == 0 and blnOddTabs == 0 and intTabCount != 0:
    arrTabDetail['intTabCount'] = intTabCount
    arrTabDetail['floatInternalTabWidth'] = floatIntersectionLength / intTabCount
    arrTabDetail['floatEndTabWidth'] = arrTabDetail['floatInternalTabWidth']

  #case when tab width, count are auto, and parity is set:
  elif blnTabWidthFixed == 0 and blnOddTabs != 0 and intTabCount == 0:
    intTmpTabCount = math.floor(floatIntersectionLength, floatMinTabWidth)
    if blnOddTabs == 2 and intTmpTabCount % 2 == 1:
      intTmpTabCount = intTmpTabCount - 1
    arrTabDetail['intTabCount'] = intTmpTabCount
    arrTabDetail['floatInternalTabWidth'] = floatIntersectionLength / intTabCount
    arrTabDetail['floatEndTabWidth'] = arrTabDetail['floatInternalTabWidth'] + (floatIntersectionLength - (arrTabDetail['floatInternalTabWidth'] * arrTabDetail['intTabCount'])) / 2

  #case when parity, and count are auto, and width is set:
  elif blnTabWidthFixed != 0 and blnOddTabs == 0 and intTabCount == 0:
    arrTabDetail['floatInternalTabWidth'] = floatTabWidth
    arrTabDetail['intTabCount'] = math.floor(floatIntersectionLength, arrTabDetail['floatInternalTabWidth'])
    arrTabDetail['floatEndTabWidth'] = arrTabDetail['floatInternalTabWidth'] + math.fmod(floatIntersectionLength, arrTabDetail['floatInternalTabWidth']) / 2

  #case when tab width, parity are set and count is auto:
  elif blnTabWidthFixed != 0 and blnOddTabs != 0 and intTabCount == 0:
    intTmpTabCount = math.floor(floatIntersectionLength, floatTabWidth)
    if blnOddTabs == 2 and intTmpTabCount % 2 == 1:
      intTmpTabCount = intTmpTabCount - 1
    arrTabDetail['intTabCount'] = intTmpTabCount
    arrTabDetail['floatInternalTabWidth'] = floatTabWidth
    arrTabDetail['floatEndTabWidth'] = arrTabDetail['floatInternalTabWidth'] + (floatIntersectionLength - (arrTabDetail['floatInternalTabWidth'] * arrTabDetail['intTabCount'])) / 2

  #case when tab width, count are set and parity is auto:
  elif blnTabWidthFixed != 0 and blnOddTabs == 0 and intTabCount != 0:
    arrTabDetail['floatInternalTabWidth'] = floatTabWidth
    arrTabDetail['intTabCount'] = intTabCount
    arrTabDetail['floatEndTabWidth'] = arrTabDetail['floatInternalTabWidth'] + (floatIntersectionLength - (arrTabDetail['floatInternalTabWidth'] * arrTabDetail['intTabCount'])) / 2

  #case when tab count, parity, are set and width is auto:
  elif blnTabWidthFixed == 0 and blnOddTabs != 0 and intTabCount != 0:
    if blnOddTabs == 1 and intTabCount % 2 != 1:
      inkex.errormsg(_('Error: Odd tab count specified with even tab total count!'))
      return FALSE
    arrTabDetail['intTabCount'] = intTabCount
    arrTabDetail['floatInternalTabWidth'] = math.floor(floatIntersectionLength, floatMinTabWidth)
    arrTabDetail['floatEndTabWidth'] = arrTabDetail['floatInternalTabWidth'] + math.fmod(floatIntersectionLength, floatMinTabWidth)
  #case when tab width, parity, and count are set:
  elif blnTabWidthFixed != 0 and blnOddTabs != 0 and intTabCount != 0:
    if blnOddTabs == 1 and intTabCount % 2 != 1:
      inkex.errormsg(_('Error: Odd tab count specified with even tab total count!'))
      return FALSE
    arrTabDetail['intTabCount'] = math.floor(floatIntersectionLength / floatMinTabWidth)
    arrTabDetail['floatInternalTabWidth'] = floatMinTabWidth
    arrTabDetail['floatEndTabWidth'] = arrTabDetail['floatInternalTabWidth'] + math.fmod(floatIntersectionLength, floatMinTabWidth)



  #final tests:
  if arrTabDetail['floatInternalTabWidth'] > floatIntersectionLength or \
        arrTabDetail['floatEndTabWidth'] > floatIntersectionLength or \
        (arrTabDetail['floatEndTabWidth'] * 2 + \
                (arrTabDetail['floatInternalTabWidth'] * (arrTabDetail['intTabCount'] - 2)) \
        ) > floatIntersectionLength:
    inkex.errormsg(_('Error: The tabs add up to longer than the total length!'))
    return FALSE


  if blnTabWidthFixed == TRUE:
    if floatTabWidth < floatMinTabWidth:
      inkex.errormsg(_('Error: Tab width specified is less than minimum width ' + floatMinTabWidth))
      return FALSE
    elif floatTabWidth > floatIntersectionLength:
      inkex.errormsg(_('Error: Tab width specified is greater than the entire intersection length'))
      return FALSE
  elif intTabCount > 0 and (floatTabWidth * intTabCount) > floatIntersectionLength:
      inkex.errormsg(_('Error: Tab width and count specified is greater than the entire intersection length'))
      return FALSE

  return arrTabDetail

# Create effect instance and apply it.
effect = IntersectionMaker()
effect.affect()
