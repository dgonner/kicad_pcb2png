#!/usr/bin/env python3

import os
import sys
from PIL import Image, ImageDraw, PngImagePlugin
import math
from pyparsing import *
import pprint

# some global config parameters
BORDER_MM = 0.5
PPI = 2000


#==============================================================================

class Segment:
	def __init__(self, param_list):	
		self.params = dict()
		del param_list[0] # remove the 'segment' element
		# transform the params into keys of the object
		for e in param_list:
			key = e[0]
			rest = e[1:]
			if len(rest) == 1:
				rest = rest[0]
			self.params[key] = rest
		return None	

class Via:
	def __init__(self, param_list):	
		self.params = dict()
		del param_list[0] # remove the 'via' element
		# transform the params into keys of the object
		for e in param_list:
			key = e[0]
			rest = e[1:]
			if len(rest) == 1:
				rest = rest[0]
			self.params[key] = rest
		return None	

class Module:
	def __init__(self, param_list):
		self.params = dict()
		del param_list[0] # remove the 'module' element
		param_list = list(filter(lambda f: type(f) is list, param_list)) # filter out all non-list items

		# transform the params into keys of the object
		for e in param_list:
			key = e[0]
			rest = e[1:]
			if len(rest) == 1:
				rest = rest[0]
			if key == 'at' or key == 'layer': # only store at and layer
				self.params[key] = rest

		# aggregate pads separately		
		raw_pads = list(filter(lambda f: f[0] == 'pad', param_list))
		pads = list()

		for p in raw_pads:
			pad = Pad(self.params['at'], p)
			pads.append(pad)

		self.params['pads'] = pads
		return None


class Pad:
	def __init__(self, module_location, param_list):	
		self.params = dict()
		del param_list[0] # remove the 'pad' element
		pad_type = param_list[1]
		shape = param_list[2]
		param_list = list(filter(lambda f: type(f) is list, param_list)) # filter out all non-list items

		# transform the params into keys of the object
		for e in param_list:
			key = e[0]
			rest = e[1:]
			if len(rest) == 1:
				rest = rest[0]
			if key == 'at' or key == 'size' or key == 'drill' or key == 'layers': # only store at, size and drill
				self.params[key] = rest

		self.params['pad_type'] = pad_type
		self.params['shape'] = shape
		self.params['offset'] = module_location
		return None


class Zone:
	def __init__(self, param_list):	
		self.params = dict()
		del param_list[0] # remove the 'zone' element
		layer = list(filter(lambda f: f[0] == 'layer', param_list))

		param_list = list(filter(lambda f: f[0] == 'filled_polygon', param_list)) # filter everythin out except 'filled_polygon'
		polygons = list()
		for p in param_list:
			poly = p[1][1:]
			poly = list(map(lambda f: f[1:], poly )) # iterate all coordiantes and strip the 'xy' (the first element)
			polygons.append(poly)

		self.params['polygons'] = polygons
		self.params['layer'] = layer[0][1]
		return None

class Outline:
	def __init__(self, param_list):	
		self.params = dict()
		if param_list[0] == 'gr_line':
			self.outline_type = 'line'
		elif param_list[0] == 'gr_arc':	
			self.outline_type = 'arc'
		else:
			print('ERR: Unknown outline type')
			exit()

		del param_list[0] # remove the 'gr_line' or 'gr_arg' element
		for e in param_list:
			key = e[0]
			rest = e[1:]
			if len(rest) == 1:
				rest = rest[0]
			self.params[key] = rest
		return None	


#==============================================================================


def mm2pix(mm, ppi):
	return int(round(mm/25.4*ppi))


def create_image(filename, dimensions, offset, ppi, border_mm, segments, modules, zones, vias, inverted=False, flipped=True, layer='B.Cu'):
	print('Generating image...', end="", flush=True)

	border = mm2pix(border_mm, ppi)       
	w = dimensions[0] + 2 * border
	h = dimensions[1] + 2 * border
	im = Image.new("RGB", (w,h))
	draw = ImageDraw.Draw(im)
	black = 0x000000
	white = 0xFFFFFF
	fill = white
	red = 0x0000FF

	if inverted:
		draw.rectangle( [0, 0, w, h], white)
		fill = black

	off_x = offset[0] - border
	off_y = offset[1] - border

	for z in zones:
		if z.params['layer'] == layer:
			for p in z.params['polygons']:
				poly = list(map(lambda f: tuple(( mm2pix(f[0], ppi) - off_x, h - (mm2pix(f[1], ppi) - off_y ))), p ))
				draw.polygon( poly, white, None)

	for s in segments:
		x1 = mm2pix(s.params['start'][0], ppi) - off_x
		y1 = mm2pix(s.params['start'][1], ppi) - off_y
		x2 = mm2pix(s.params['end'][0], ppi) - off_x
		y2 = mm2pix(s.params['end'][1], ppi) - off_y
		width = mm2pix(s.params['width'], ppi)

		if s.params['layer'] == layer:	
			draw.line( [x1, h-y1, x2, h-y2], fill, width)
			# draw circle on the start of the connection
			x = x1 - int(round(width / 2))
			y = h - (y1 + int(round(width / 2)))
			draw.ellipse( [ x+1, y-1, x + width, y + width], fill)
			# draw circle on the end of the connection
			x = x2 - int(round(width / 2))
			y = h - (y2 + int(round(width / 2)))
			draw.ellipse( [ x+1, y-1, x + width, y + width], fill)

	for m in modules:
		for p in m.params['pads']:
			# check if it's on the right layer
			if "*.Cu" in p.params['layers'] or layer in p.params['layers']:
				try:
					rotation = 360 - p.params['at'][2]
				except:
					rotation = 0	
				angle = math.radians(rotation)	
				rot_x = p.params['at'][0] * math.cos(angle) - p.params['at'][1] * math.sin(angle)
				rot_y = p.params['at'][0] * math.sin(angle) + p.params['at'][1] * math.cos(angle)

				center_x = mm2pix( rot_x + p.params['offset'][0], ppi) - off_x
				center_y = mm2pix( rot_y + p.params['offset'][1], ppi) - off_y
	
				width_x = mm2pix(p.params['size'][0], ppi)
				width_y = mm2pix(p.params['size'][1], ppi)
				shape = p.params['shape']

				if shape == 'oval':
					None

				if shape == 'circle':
					x = center_x - int(round(width_x / 2.0))
					y = h - (center_y + int(round(width_y / 2.0)))
					draw.ellipse( [ x, y, x+width_x, y+width_y], fill)

				if shape == 'rect':
					x = center_x - int(round(width_x / 2.0))
					y = h -(center_y + int(round(width_y / 2.0)))

					poly = [x, y, x+width_x, y, x+width_x, y+width_y, x, y+width_y]
					draw.polygon( poly, white, None)
#					draw.ellipse( [ x, y, x+width_x, y+width_y], fill)

				# check for drill hole in pad
				if 'drill' in p.params:
					drill = mm2pix(p.params['drill'], ppi)
					# draw circle for drill hole
					x = center_x - int(round(drill / 2.0))
					y = h - (center_y + int(round(drill / 2.0)))
					draw.ellipse( [ x, y, x + drill, y + drill], black)


	for v in vias:
		if layer in v.params['layers']:
			center_x = mm2pix( v.params['at'][0], ppi) - off_x
			center_y = mm2pix( v.params['at'][1], ppi) - off_y	

			width = mm2pix( v.params['size'], ppi) # vias are always round?

			x = center_x - int(round(width / 2.0))
			y = h - (center_y + int(round(width / 2.0)))
			draw.ellipse( [ x, y, x+width, y+width], fill)

			# check for drill hole in pad
			if 'drill' in v.params:
				drill = mm2pix(v.params['drill'], ppi)
				# draw circle for drill hole
				x = center_x - int(round(drill / 2.0))
				y = h - (center_y + int(round(drill / 2.0)))
				draw.ellipse( [ x, y, x + drill, y + drill], black)

	del draw

	print(' OK')
	print('Writing', filename, '...', end="", flush=True)
	im.save(filename, "PNG", dpi=(ppi,ppi))
	print(' OK')


#@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@


# def distance(x1, y1, x2, y2):
# 	return mat.sqrt(math.pow(math.abs(x2-x1),2) + math.pow(math.abs(y2-y1),2))


def create_outline_image(filename, dimensions, offset, ppi, border_mm, outlines, modules, vias):
	print('Generating image...', end="", flush=True)

	border = mm2pix(border_mm, ppi)       
	w = dimensions[0] + 2 * border
	h = dimensions[1] + 2 * border
	im = Image.new("RGB", (w,h))
	draw = ImageDraw.Draw(im)
	black = 0x000000
	white = 0xFFFFFF
	fill = white

	off_x = offset[0] - border
	off_y = offset[1] - border

	# create a continuous polygon from the separate outlines
	poly = list()
	poly.append(outlines[0].params['start'])
	poly.append(outlines[0].params['end'])
	del outlines[0]

	while len(outlines) > 0:
		i = 0
		while i < len(outlines):
			s = outlines[i].params['start']
			e = outlines[i].params['end']

			if s == poly[len(poly)-1]: # start matches
				poly.append(e)
				break
			elif e == poly[len(poly)-1]: # end matches
				poly.append(s)
				break	
			i = i + 1
		del outlines[i]	
	del poly[len(poly)-1]	

	poly_pix = list()
	for p in poly:
	  	x = mm2pix(p[0], ppi) - off_x
	  	y = mm2pix(p[1], ppi) - off_y
	  	poly_pix.append( tuple(( x, h-y )) )
	
	draw.polygon( poly_pix, white, None)


	for m in modules:
		for p in m.params['pads']:
			# no need to check for layer, only check for drill hole
			try:
				rotation = 360 - p.params['at'][2]
			except:
				rotation = 0	

			angle = math.radians(rotation)	
			rot_x = p.params['at'][0] * math.cos(angle) - p.params['at'][1] * math.sin(angle)
			rot_y = p.params['at'][0] * math.sin(angle) + p.params['at'][1] * math.cos(angle)

			center_x = mm2pix( rot_x + p.params['offset'][0], ppi) - off_x
			center_y = mm2pix( rot_y + p.params['offset'][1], ppi) - off_y

			# check for drill hole in pad
			if 'drill' in p.params:
				drill = mm2pix(p.params['drill'], ppi)
				# draw circle for drill hole
				x = center_x - int(round(drill / 2.0))
				y = h - (center_y + int(round(drill / 2.0)))
				draw.ellipse( [ x, y, x + drill, y + drill], black)


	for v in vias:
		center_x = mm2pix( v.params['at'][0], ppi) - off_x
		center_y = mm2pix( v.params['at'][1], ppi) - off_y	

		# check for drill hole in pad
		if 'drill' in v.params:
			drill = mm2pix(v.params['drill'], ppi)
			# draw circle for drill hole
			x = center_x - int(round(drill / 2.0))
			y = h - (center_y + int(round(drill / 2.0)))
			draw.ellipse( [ x, y, x + drill, y + drill], black)

	del draw

	print(' OK')
	print('Writing', filename, '...', end="", flush=True)
	im.save(filename, "PNG", dpi=(ppi,ppi))
	print(' OK')


#==============================================================================


def verifyLen(s,l,t):
    t = t[0]
    if t.len is not None:
        t1len = len(t[1])
        if t1len != t.len:
            raise ParseFatalException(s,l,\
                    "invalid data of length %d, expected %s" % (t1len, t.len))
    return t[1]

# define punctuation literals
LPAR, RPAR, LBRK, RBRK, LBRC, RBRC, VBAR = map(Suppress, "()[]{}|")
decimal = Regex(r'0|[1-9]\d*').setParseAction(lambda t: int(t[0]))
bytes = Word(printables)
raw = Group(decimal("len") + Suppress(":") + bytes).setParseAction(verifyLen)
token = Word(alphanums + "-./_:*+=")
qString = Group(Optional(decimal,default=None)("len") + 
                        dblQuotedString.setParseAction(removeQuotes)).setParseAction(verifyLen)

# extended definitions
decimal = Regex(r'-?0|[1-9]\d*').setParseAction(lambda t: int(t[0]))
real = Regex(r"[+-]?\d+\.\d*([eE][+-]?\d+)?").setParseAction(lambda tokens: float(tokens[0]))
token = Word(alphanums + "-./_:*+=!<>")
simpleString = real | raw | decimal | token | qString
display = LBRK + simpleString + RBRK
string_ = Optional(display) + simpleString
sexp = Forward()
sexpList = Group(LPAR + ZeroOrMore(sexp) + RPAR)
sexp << ( string_ | sexpList )


#==============================================================================


def parse_pcblist(pcblist):
	# map keys in the kicad_pcb file to objects that can parse the data
	supported_list = dict()
	supported_list['segment'] = Segment
	supported_list['via'] = Via
	supported_list['module'] = Module
	supported_list['zone'] = Zone
	supported_list['gr_line'] = Outline
	supported_list['gr_arc'] = Outline

	for i in pcblist:
		name = i[0]
		if name in supported_list:
			instance = supported_list[name](i)
			pcb_data[name].append(instance)		


def get_outline_boundingbox(outlines):
	if len(outlines) == 0:
		raise NameError('HiThere') # Error, no outlines in board

	max_x = outlines[0].params['start'][0]
	max_y = outlines[0].params['start'][1]
	min_x = max_x
	min_y = max_y

	for o in outlines:
		xmin = min( o.params['start'][0], o.params['end'][0] )
		xmax = max( o.params['start'][0], o.params['end'][0] )
		ymin = min( o.params['start'][1], o.params['end'][1] )
		ymax = max( o.params['start'][1], o.params['end'][1] )
		max_x = max( max_x, xmax)
		max_y = max( max_y, ymax)
		min_x = min( min_x, xmin)
		min_y = min( min_y, ymin)

	return (min_x, min_y, max_x, max_y)


#==============================================================================
#==============================================================================

SEGMENTS = list()
VIAS = list()
MODULES = list()
ZONES = list()
OUTLINES = list()

pcb_data = dict()
pcb_data['segment'] = SEGMENTS
pcb_data['via'] = VIAS
pcb_data['module'] = MODULES
pcb_data['zone'] = ZONES
pcb_data['gr_line'] = OUTLINES
pcb_data['gr_arc'] = OUTLINES


print("\nkicad_pcb2png.py ver. 2 may 2016\n")

current_dir = os.getcwd()
if len(sys.argv) > 1:
	project_name = sys.argv[1]
	pcbfile = project_name + ".kicad_pcb"
	if os.path.isfile(pcbfile):
		print("Board File Found:", pcbfile)
	else:
		print("ERR: No board file found!")
		exit()
else:
	print("ERR: Project name missing!")
	print("Usage: python3 kicad_pcb2png.py [project name]")
	exit()	


print('Reading...', end="", flush=True)
with open(pcbfile, 'r') as f:
    data="".join(line.rstrip() for line in f)
print(' OK')    


print('Parsing...', end="", flush=True)
try:
	sexpr = sexp.parseString(data, parseAll=True)
	pcblist = sexpr.asList()
	parse_pcblist(pcblist[0])
except ParseFatalException as pfe:
	print("ERR: Parse error!")
	#print("Error:", pfe.msg)
	#print(pfe.markInputline('^'))
print(' OK\n')    

# filter out all outlines that are not on the Edge.Cuts layer
OUTLINES = list(filter(lambda f: f.params['layer'] == 'Edge.Cuts', OUTLINES))

print('outlines:',len(OUTLINES))
print('zones:',len(ZONES))
print('segments:',len(SEGMENTS))
print('modules:',len(MODULES))
pad_count = 0
for m in MODULES:
	pad_count += len(m.params['pads'])
print('pads:',pad_count)
print('vias:',len(VIAS))

if len(OUTLINES) < 3:
	print("ERR: Less than 3 board outlines found!")
	exit()

try:
	bbox = get_outline_boundingbox(OUTLINES)
	width = bbox[2] - bbox[0]
	height = bbox[3] - bbox[1]
	dimensions = [ mm2pix(width, PPI), mm2pix(height, PPI) ]
	offset = [ mm2pix(bbox[0], PPI), mm2pix(bbox[1], PPI) ]

	print('\nBoard: {:.2f} x {:.2f} mm'.format(width, height))
	print('Border: {:.2f} mm'.format(BORDER_MM))
	border_pixels = int(round(BORDER_MM/25.4*PPI))
	print('Image:', dimensions[0]+border_pixels*2, 'x', dimensions[1]+border_pixels*2, '@', PPI, 'ppi\n')
except:
	print("ERR: No board outlines found!")
	exit()

create_image(project_name+"-B.Cu_MILL-TRACES.png", dimensions, offset, PPI, BORDER_MM, SEGMENTS, MODULES, ZONES, VIAS)

create_outline_image(project_name+"-MILL-OUTLINE.png", dimensions, offset, PPI, BORDER_MM, OUTLINES, MODULES, VIAS)

print("Done\n")