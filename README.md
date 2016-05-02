# kicad_pcb2png
Convert a Kicad PCB design to PNG for milling with Fab Modules

* Takes KiCad board files in .kicad_pcb format. Tested with version 3.?.? and 4.0.2 
* Produces PNG files in high resolution (2000 DPI)
* Outputs separate files for different milling stages. Top and bottom trace milling and holes and board cutout

This script helps me with PCB manufacturing with a specific workflow:
* I design the circuit boards in KiCad version 3.0 and 4.0
* board files are saved a *.kicad_pcb files and contain all data to recreate the design
* I mill my circuit boards on a Roland MDX-20 small milling machine.
* The mill is controlled by Fab Modules software from MIT. http://kokompe.cba.mit.edu/
* The Fab Modules software requires high resolution black and white PNG images as input
* KiCad can not export the kind of images I need directly, that's why I wrote this tool


