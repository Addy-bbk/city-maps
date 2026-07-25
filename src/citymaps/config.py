"""The central configurations for the city maps pipeline.

All decisions made during the processing phase that will affect the final dataset 
are recorded here, as well as all input parameters to ensure that the dataset 
is reproducible through a single file and to enable the report to reference 
the exact values used for each parameter."""

from pathlib import Path

# --- Paths -----------------------------------------------------------------
# The project_root directory is defined as the parent of this module
# __file__ + 2 * '..' (i.e., the 'config.py' file is located at:
#
# .../src/citymaps/
# .../citymaps/
# .../config.py)
PROJECT_ROOT = Path(__file__).resolve().parents[2]

# Define paths using the project_root.
DATA_DIR = PROJECT_ROOT / "data"
OUTPUT_DIR = PROJECT_ROOT / "output"
GRAPH_DIR = OUTPUT_DIR / "graphs"
FIGURE_DIR = OUTPUT_DIR / "figures"
LOG_DIR = OUTPUT_DIR / "logs"

CITY_LIST = DATA_DIR / "cities_pilot.csv"

# --- Extraction Parameters -------------------------------------------------

# What types of OSM way to extract. In this case,  all public roadways 
# that are drivable by a car ("drive").
NETWORK_TYPE = "drive"

# --- Simplification Parameters----------------------------------------------

# Within what radius (measured in meters), should be considered an acceptable 
# difference to merge two separate OSM nodes into one intersection. This can be 
# useful when dealing with dual-carriageways or other multi-laned intersections 
# where multiple nodes have been added in close proximity. If there was no 
# simplification, then every time an intersection was encountered, a new node 
# would be created for each lane-way -- greatly inflating the number of total 
# nodes and altering the expected degree distribution.
CONSOLIDATION_TOLERANCE_M = 10.0

# By setting CONSOLIDATE_DEAD_ENDS 
# to True, OSMnx is told to treat dead-ends like regular edges and simplify 
# accordingly. 
#Dead ends are topological features for example cul-de-sacs. So it is false to preserve them
#because dead ends could be delted by mergeing them into intersections
CONSOLIDATE_DEAD_ENDS = False

# --- Output Parameters -----------------------------------------------------

# How many decimal places should be included in our coordinate values?
COORD_PRECISION = 1

# Setting KEEP_LARGEST_COMPONENT to True means that we'll ignore any 
# disconnected components in our data and focus solely on the largest portion. 
KEEP_LARGEST_COMPONENT = True

#  Set RECENTRE_ON_CENTROID to True to achieve this effect.
RECENTRE_ON_CENTROID = True
