# City Maps

A standardised repository of urban road networks represented as planar graphs.

MSc Data Science project, Birkbeck, University of London.
Data derived from OpenStreetMap, (c) OpenStreetMap contributors, ODbL.

## Setup

    conda env create -f environment.yml
    conda activate citymaps

## Use

    python scripts/run_pilot.py     # extract the pilot cities
    pytest -q                       # run the offline test suite

## Output format

Each city is one `.txt` file:

    # Nodes
    <id> <x> <y>        ... one per line, ids consecutive from 0, metres

    # Edges
    <u> <v>             ... one per line, undirected, u < v

Coordinates are metres in the local UTM zone, translated so the centroid of
the node set is at the origin. No street names, classifications, directions
or other attributes are retained.

## Layout

    src/citymaps/   pipeline modules
    scripts/        entry points
    data/           city lists
    output/graphs/  the dataset
    tests/          offline test suite
