# PgSQL 2 OSM toolchain

pgsql2osm.sh is a piece of software intended to produce OSM XML format out of postgresql tables.  
EPSG4326 WGS84 geographical geometries are first of all converted into connected topological features with the help of toOsm.sql.  
A Python script then write them all to an OSM XML file.

OSM XML is used for several tools of OpenStreetMap ecosystem
<https://wiki.openstreetmap.org/wiki/OSM_XML>.

## Requirements

What you need to use this software:

- Postgresql + Postgis 3
- Python 3
- Jq

Common specs for regional area (1.5M ways with +7M nodes).  
Recommended on 16Go / 4 CPU server with 10Go dedicated to PgSQL.  
Best on 32 Go / 8 CPU with 20 Go dedicated to PgSQL.

## Installation

A python environment manager is recommended (ex: venv, pipenv).

```sh
pip3 install -r requirements.txt
```

## Configuration

A configuration file should be written in JSON prior to use pgsql2osm.sh:

```json
{
    "input_ways": Input table with ways,
    "input_nodes": Input table with nodes (optional),
    "output_ways": Output table for ways,
    "output_nodes": Output table for nodes,
    "output_waysnodes": Output table for ways / nodes linkage,
    "coordinates_resolution": Integer > 0 used to define how many decimals are kept in WGS84 coordinates to deduplicate nodes,
    "coordinates_prime": A prime number > 10^resolution to compute hashcode of nodes coordinates to give them usine ids
}
```

An example is available as `./config.json`.

## Usage

Conversion process is launched from pgsql2osm.sh script with following syntax:

```sh
pgsql2osm.sh -c <config file path> -o <output xml path> -d <database name>
```

To test it, use or customize the example `./config.json` and run:

```sh
pgsql2osm.sh -c config.json -o output.osm -d your_data_base
```

The output should be the same as `sample/output.osm`

## Inputs

Two tables may be processed by the software, mandatory for ways and optional for nodes.  
Those tables MUST conform to this structure to be correctly converted.

### Ways

| column   | Type     | Nullable |
| -------- | -------- | -------- |
| osm_id   | integer  | not_null |
| arc_uuid | uuid     |          |
| geom     | geometry |          |
| tags     | jsonb    |          |

It is recommended to index geom(gist) and tags(btree).

### Nodes

| column | Type     | Nullable |
| ------ | -------- | -------- |
| geom   | geometry |          |
| tags   | jsonb    |          |

It is recommended to index geom(gist) and tags(btree).

## Performances

This software is regularly used to convert 1.5M ways with +7M nodes and runs in 10 minutes on a 32Go / 8 CPU server.

All of this sounds more like a proof of concept than a completely industrial product.  
It currently misses several useful features

- pbf encoding of output xml
- xml production could be really improved through C++ implementation.
- Postgis logic to produce topological features may be improved as well

Feel free to help if you are interested.

## Background

Producing a connected topological dataset from geometries requires to make connections between adjacent ways under certain conditions.  
Ways are registered the first and their nodes are dumped with ST_dumpPoints help.  
Linkage between ways and newly dumped nodes are then created and each node receive a unique identifier based upon the process below.  
Nodes are finally registered with their geom and id.

## Nodes ids

Nodes ids are given according to their geometries as to mechanically remove overlapping duplicates.  
You are asked to set a resolution and a prime number as to group near nodes under the same id.  
Node ids are got with the following expression:

```
round((lattitude + (prime * longitude)) * layer)
```

You can add optional tags pgsql2osm:layer and pgsql2osm:layer:start on ways to change how they are connected to each others.  
pgsql2osm:layer defaults to 1, which means any overlapping nodes will be merged and attached ways connected, no exceptions.  
You can change the value of pgsql2osm:layer on each way to prevent connection with other features at different pgsql2osm layers.  
It's also possible to focus on the first node of a given way with more particular pgsql2osm:layer:start

## Ways connections

You may have notice a layer is involved in the node ids expression upside.
Doing so allow to manage ways connection and restrict them to ways having the same layer.  
Layer defaults to 1 and ways with overlapping nodes (according to their coordinates and thus their ids) will be connected and share the same node in the topological twin produced.  
You may be interested to define different layers to prevent ways to connect according to your own needs.
